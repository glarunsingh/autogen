import os
import json
from datetime import datetime
from tempfile import TemporaryDirectory
from websockets.sync.client import connect as ws_connect
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn
import asyncio

import autogen
from autogen import AssistantAgent, UserProxyAgent
from autogen.io.websockets import IOWebsockets
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from docx import Document as DocxDocument
from PyPDF2 import PdfReader
from dotenv import load_dotenv

# WebSocket Server Port
PORT = 8080

# LLM Configuration
llm_config = {
    "timeout": 600,
    "config_list": autogen.config_list_from_json("OAI_CONFIG_LIST"),
    "temperature": 0,
}

# Connection Handler Function
def on_connect(iostream: IOWebsockets) -> None:
    """
    Handles a new WebSocket connection, receives the initial message,
    and starts the chat interaction with Autogen agents.
    """
    print(f" - on_connect(): Connected to client using IOWebsockets {iostream}", flush=True)
    print(" - on_connect(): Receiving message from client.", flush=True)
    
    # 1. Receive Initial Message
    initial_msg = iostream.input()
    
    # 2. Instantiate Autogen Agents
    
    # Data Collection Agent for technical details and estimations
    data_collection_agent = AssistantAgent(
        name="data_collection_agent",
        system_message="""You are a Technical architect. Your job is to arrive at the tech stack for a problem statement and also arrive at estimates for the application in scope.
        You interact with the customer in a chat format and obtain information necessary to come up with estimates. 
        Ask a series of questions covering the application overview, tech stack involved, integration points, and develop a work breakdown of the complex problem statement. 
        Provide justifications for each estimate and list assumptions. If certain information is not provided, make assumptions and arrive at estimates.
        Always suggest leading open source frameworks wherever possible and call out the reasons for it. 
        Decide technologies and tech stacks based on volume. All infra hosting will incur cost and while giving an estimate take into account the cost of hosting as well.
        You should ask questions one by one as this will be best experience for the user. Don't ask all your questions at once.""",
        llm_config=llm_config,
    )
    
    # Estimation Agent to process collected data and generate estimates
    estimation_agent = AssistantAgent(
        name="estimation_agent",
        system_message="""You are a Technical architect. Your job is to generate high-level functionalities/modules, tech stack, volumetrics, feasibility, convert conversation to high-level requirements, WBS, high-level functionalities, costing, assumptions, timeline, resources, and TCO based on the data collected by the data collection agent.""",
        llm_config=llm_config,
        human_input_mode="NEVER",
    )
    
    # 3. Define User Proxy Agent for managing the chat interface
    user_proxy = UserProxyAgent(
        name="user_proxy",
        human_input_mode="ALWAYS",
        llm_config=llm_config,
        code_execution_config=False,
        system_message="You are a helpful assistant."
    )

    # 4. Initiate conversation
    print(
        f" - on_connect(): Initiating chat with agent {data_collection_agent} using message '{initial_msg}'",
        flush=True,
    )

    # Start sequential chat between agents using `initiate_chats`
    chat_results = user_proxy.initiate_chats(
        [
            {
                "recipient": data_collection_agent,
                "message": "You are a Technical architect. Your job is to arrive at the tech stack for a problem statement and also arrive at estimates for the application in scope.",
                "clear_history": True,
                "silent": False,
                "summary_method": "last_msg",
            },
            {
                "recipient": estimation_agent,
                "message": "Please generate estimates based on the collected information.",
                "summary_method": "reflection_with_llm",
            },
        ]
    )

# HTML Client for WebSocket Communication
html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Autogen WebSocket Test</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 0;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                background-color: #f4f6f8;
            }
            .chat-container {
                display: flex;
                flex-direction: column;
                justify-content: flex-end;
                width: 100%;
                max-width: 800px;
                background-color: white;
                padding: 16px;
                border-radius: 8px;
                box-shadow: 0px 4px 10px rgba(0, 0, 0, 0.1);
            }
            .chat-title {
                font-size: 1.8em;
                color: #333;
                text-align: center;
                margin-bottom: 10px;
                padding-bottom: 10px;
                border-bottom: 1px solid #ddd;
            }
            #messages {
                list-style-type: none;
                padding: 0;
                margin: 0;
                max-height: 400px;
                overflow-y: auto;
                flex-grow: 1;
            }
            #messages li {
                background-color: #e8f0fe;
                color: #333;
                padding: 8px 12px;
                margin: 8px 0;
                border-radius: 15px;
                max-width: 80%;
                word-wrap: break-word;
            }
            #messages li.user-message {
                background-color: #dcf8c6;
                align-self: flex-end;
                text-align: right;
            }
            .chat-input {
                display: flex;
                align-items: center;
                padding-top: 12px;
                border-top: 1px solid #ddd;
            }
            #messageText {
                width: 85%; /* Wider text box */
                padding: 10px;
                border-radius: 20px;
                border: 1px solid #ccc;
                outline: none;
                font-size: 1em;
                box-sizing: border-box;
            }
            button {
                padding: 10px 20px;
                margin-left: 10px;
                border-radius: 20px;
                border: none;
                background-color: #4CAF50;
                color: white;
                cursor: pointer;
                font-size: 1em;
            }
            button:hover {
                background-color: #45a049;
            }
        </style>
    </head>
    <body>
        <div class="chat-container">
            <h1 class="chat-title">AI Chat Assistant</h1>
            <ul id="messages"></ul>
            <div class="chat-input">
                <form action="" onsubmit="sendMessage(event)">
                    <input type="text" id="messageText" autocomplete="off" placeholder="Type your message..." />
                    <button>Send</button>
                </form>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/gh/MarketingPipeline/Markdown-Tag/markdown-tag.js"></script>
        <script>
            var ws = new WebSocket("ws://localhost:8080/ws");
            ws.onmessage = function(event) {
            if
            (event.data.includes(">>>>") || 
            event.data.includes("***") ||
            event.data.includes("---------------") ||
            event.data.includes("Starting a new chat....") ||
            event.data.includes("user_proxy")|| 
            event.data.includes("Replying as"))
            {
            return
            }
                var messages = document.getElementById('messages');
                var message = document.createElement('github-md');
                var content = document.createTextNode(event.data);
                message.appendChild(content);
                messages.appendChild(message);
                messages.scrollTop = messages.scrollHeight;  // Scroll to latest message
                renderMarkdown();
            };
            
            function sendMessage(event) {
                var input = document.getElementById("messageText");
                if (input.value.trim() !== "") {
                    var userMessage = document.createElement('li');
                    userMessage.classList.add('user-message');
                    userMessage.textContent = input.value;
                    document.getElementById('messages').appendChild(userMessage);
                    ws.send(input.value);
                    input.value = '';
                }
                event.preventDefault();
            }
        </script>
    </body>
</html>
"""

# WebSocket Server Manager
@asynccontextmanager
async def run_websocket_server(app):
    """
    Asynchronously runs the WebSocket server for handling chat communication
    using FastAPI.
    """
    with IOWebsockets.run_server_in_thread(on_connect=on_connect, port=8080) as uri:
        print(f"Websocket server started at {uri}.", flush=True)
        yield

# FastAPI App Configuration
app = FastAPI(lifespan=run_websocket_server)

# Route to Serve HTML Client
@app.get("/")
async def get():
    return HTMLResponse(html)

# Main Function to Run FastAPI Server
async def main():
    """
    Configures and starts the FastAPI WebSocket server.
    """
    config = uvicorn.Config(app)
    server = uvicorn.Server(config)
    await server.serve()

# Start the WebSocket Server
asyncio.run(main())
