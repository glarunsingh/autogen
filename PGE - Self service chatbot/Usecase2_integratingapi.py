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
        <title>Autogen websocket test</title>
    </head>
    <body>
        <h1>WebSocket Chat</h1>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        <ul id='messages'>
        </ul>
        <script>
            var ws = new WebSocket("ws://localhost:8080/ws");
            ws.onmessage = function(event) {
                var messages = document.getElementById('messages')
                var message = document.createElement('li')
                var content = document.createTextNode(event.data)
                message.appendChild(content)
                messages.appendChild(message)
            };
            function sendMessage(event) {
                var input = document.getElementById("messageText")
                ws.send(input.value)
                input.value = ''
                event.preventDefault()
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
