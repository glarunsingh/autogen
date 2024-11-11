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

from prompt import data_collection_prompt, estimation_prompt

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
        system_message=data_collection_prompt,
        llm_config=llm_config,
    )
    
    # Estimation Agent to process collected data and generate estimates
    estimation_agent = AssistantAgent(
        name="estimation_agent",
        system_message=estimation_prompt,
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
<html lang="en">  
  
<head>  
    <meta charset="UTF-8">  
    <meta name="viewport" content="width=device-width, initial-scale=1.0">  
    <title>Chat App</title>  
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.3/css/all.min.css" rel="stylesheet">  
    <style>  
        body, html {  
            height: 100%;  
            margin: 0;  
            font-family: Arial, Helvetica, sans-serif;  
        }  
  
        .chat-container {  
            display: flex;  
            flex-direction: column;  
            height: 100vh;  
            width: 100%;  
        }  
  
        .chat-messages {  
            flex: 1;  
            overflow-y: auto;  
            padding: 20px;  
            background: #f7f7f7;  
        }  
  
        .message {  
            display: flex;  
            align-items: flex-start;  
            margin-bottom: 10px;  
        }  
  
        .message.user {  
            justify-content: flex-end;  
        }  
  
        .message.user .message-content {  
            background-color: #dcf8c6;  
        }  
  
        .message.system .message-content {  
            background-color: #a5cef7;  
        }  
  
        .message-content {  
            max-width: 60%;  
            padding: 10px;  
            border-radius: 10px;  
            position: relative;  
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);  
        }  
  
        .message-icon {  
            margin-right: 10px;  
            font-size: 20px;  
            color: #1a0357;  
        }  
  
        .message.user .message-icon {  
            margin-left: 10px;  
            margin-right: 0;  
        }  
  
        .chat-input {  
            display: flex;  
            padding: 10px;  
            background: #ffffff;  
            border-top: 1px solid #ddd;  
        }  
  
        .chat-input textarea {  
            flex: 1;  
            padding: 10px;  
            border: 1px solid #ddd;  
            border-radius: 5px;  
            resize: none;  
            height: 50px;  
        }  
  
        .chat-input button {  
            margin-left: 10px;  
            padding: 0 15px;  
            border: none;  
            border-radius: 5px;  
            background: #007bff;  
            color: white;  
            cursor: pointer;  
        }  
  
        .chat-input button.clear {  
            background: #dc3545;  
        }  
    </style>  
</head>  
  
<body>  
    <div class="chat-container">  
        <div class="chat-messages" id="chat-messages"></div>  
        <div class="chat-input">  
            <textarea id="chat-input" placeholder="Type a message..."></textarea>  
            <button onclick="sendMessage()">Send</button>  
            <button class="clear" onclick="clearMessages()">Clear</button>  
        </div>  
    </div>  
    <script src="https://cdn.jsdelivr.net/gh/MarketingPipeline/Markdown-Tag/markdown-tag.js"></script>

    <script>  
        const chatMessages = document.getElementById('chat-messages');  
        const chatInput = document.getElementById('chat-input');  
        const ws = new WebSocket('ws://localhost:8080');  
        const userIcon = '<i class="fas fa-user message-icon"></i>';  
        const systemIcon = '<i class="fas fa-robot message-icon"></i>';  
        sendmess  = ""
        ws.onmessage = function(event) {  
            // const data = JSON.parse(event.data);
            message = event.data
            console.log( `----${message.trim()}------${sendmess}-----`)
            console.log("comp  -- ",message==sendmess)
            if(
            message.includes("********************************************************************************") ||
             message.includes("user_proxy")||
            //  message.includes("--------------------------------------------------------------------------------") ||
             message.includes("Starting a new chat....")||
             message.includes("Replying as") 
             || message.trim()===sendmess.trim()
        ){
                console.log("message", message)

                return
            } 
            // console.log(event.data)
            displayMessage(event.data,"system");  
        };  
  
        ws.onopen = function() {  
            displayMessage('Connected to the server', 'system');  
        };  
  
        ws.onclose = function() {  
            displayMessage('Disconnected from the server', 'system');  
        };  
  
        function sendMessage() {  
            const message = chatInput.value.trim();  
            if (message) {  
                ws.send(message);  
                displayMessage(message, 'user');  
                chatInput.value = '';  
                saveMessage(message, 'user');  
                sendmess=message
            }  
        }  
  
        function displayMessage(message, type) {  
            const messageElement = document.createElement('div');  
            messageElement.classList.add('message', type);  
            messageElement.innerHTML = `  
                ${type === 'user' ? userIcon : systemIcon}  
                <github-md class="message-content">${message}</github-md>  
            `;  
            chatMessages.appendChild(messageElement);  
            chatMessages.scrollTop = chatMessages.scrollHeight;
            renderMarkdown();

        }  
  
        function clearMessages() {  
            chatMessages.innerHTML = '';  
            localStorage.removeItem('chatMessages');  
        }  
  
        function saveMessage(message, type) {  
            const messages = JSON.parse(localStorage.getItem('chatMessages')) || [];  
            messages.push({ message, type });  
            localStorage.setItem('chatMessages', JSON.stringify(messages));  
        }  
  
        function loadMessages() {  
            const messages = JSON.parse(localStorage.getItem('chatMessages')) || [];  
            messages.forEach(msg => displayMessage(msg.message, msg.type));  
        }  
  
        chatInput.addEventListener('keypress', function (e) {  
            if (e.key === 'Enter') {  
                e.preventDefault();  
                sendMessage();  
            }  
        });  
  
        loadMessages();  
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
