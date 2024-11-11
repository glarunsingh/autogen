import os
import json
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import asyncio
from tempfile import TemporaryDirectory
from autogen import AssistantAgent, UserProxyAgent
from websockets.sync.client import connect as ws_connect
from autogen.io.websockets import IOWebsockets
import autogen
from dotenv import load_dotenv
from docx import Document as DocxDocument
from PyPDF2 import PdfReader
import uvicorn

from contextlib import asynccontextmanager  # noqa: E402
from pathlib import Path  # noqa: E402
PORT = 8000


# -------------------- Load Environment Variables --------------------
load_dotenv()

api_version = os.getenv("AZURE_OPENAI_API_VERSION")
endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
api_key = os.getenv("AZURE_OPENAI_API_KEY")
deployment_name = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
llm_model = os.getenv("LLM_MODEL")

# Verify environment variables
if not all([api_version, endpoint, api_key, deployment_name, llm_model]):
    raise ValueError("Some environment variables are missing. Check your .env file.")

# Configure Autogen LLM
llm_config = {
    "timeout": 600,
    "config_list": autogen.config_list_from_json("OAI_CONFIG_LIST"),
    "temperature": 0,
}

# -------------------- Define Agents --------------------
data_collection_agent = AssistantAgent(
    name="data_collection_agent",
    system_message="""You are a Technical architect responsible for collecting the tech stack and estimating application requirements based on a problem statement.
    Ask questions sequentially about the application overview, tech stack, integration points, and develop a work breakdown for the complex problem.
    Justify each estimate and list assumptions. Use open-source frameworks where possible and consider infra hosting costs.""",
    llm_config=llm_config,
)

estimation_agent = AssistantAgent(
    name="estimation_agent",
    system_message="""You are responsible for generating high-level functionalities, tech stack, volumetrics, requirements, WBS, costing, assumptions, timeline, and TCO based on the data collected by the data collection agent.""",
    llm_config=llm_config,
    human_input_mode="NEVER",
)

user_proxy = UserProxyAgent(
    name="user_proxy",
    human_input_mode="ALWAYS",
    llm_config=llm_config,
    code_execution_config=False,
    system_message="You are a helpful assistant."
)

# -------------------- Helper Functions --------------------
def extract_text_from_docx(docx_path):
    doc = DocxDocument(docx_path)
    return "\n".join([para.text for para in doc.paragraphs])

def extract_text_from_pdf(pdf_path):
    reader = PdfReader(pdf_path)
    return "\n".join(page.extract_text() for page in reader.pages)

def read_document(file_path):
    if not file_path or not os.path.exists(file_path):
        return None
    if file_path.endswith(".txt"):
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    elif file_path.endswith(".docx"):
        return extract_text_from_docx(file_path)
    elif file_path.endswith(".pdf"):
        return extract_text_from_pdf(file_path)
    else:
        return "Unsupported file format. Please provide a valid TXT, DOCX, or PDF file."

# -------------------- Main Logic --------------------
def analyze_and_start_autogen_qa(content):
    """Use Autogen to analyze content and initiate Q&A."""
    conversation_history = []  # Store the entire conversation

    # Start sequential chat between agents using `initiate_chats`
    chat_results = user_proxy.initiate_chats(
        [
            {
                "recipient": data_collection_agent,
                "message": content,
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

    # Extract specific messages from each agent
    final_data = {}

    # Retrieve messages from data_collection_agent
    data_collection_messages = data_collection_agent.chat_messages[user_proxy]
    if data_collection_messages:
        final_data["data_collection_response"] = data_collection_messages[-1]["content"]

    # Retrieve messages from estimation_agent
    estimation_messages = estimation_agent.chat_messages[user_proxy]
    if estimation_messages:
        final_data["estimation_response"] = estimation_messages[-1]["content"]

    return final_data

def process_document_or_summary(doc_path=None):
    """Process document or initiate with user-provided summary."""
    content = read_document(doc_path)

    if content:
        print(f"\nExtracted Content from '{doc_path}':\n{content}\n")
    else:
        print("No document provided. Please enter a summary.\n")
        content = input("Enter a summary of the process: ")

    final_data = analyze_and_start_autogen_qa(content)

    # Display final collected data
    print("\nFinal Collected Data:\n", json.dumps(final_data, indent=2))
    return final_data

# -------------------- WebSocket Setup for Real-time Chat --------------------
PORT = 8000
html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Autogen WebSocket Test</title>
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

@asynccontextmanager
async def run_websocket_server(app):
    with IOWebsockets.run_server_in_thread(on_connect=on_connect, port=8080) as uri:
        print(f"Websocket server started at {uri}.", flush=True)

        yield


async def main():
    config = uvicorn.Config(app)
    server = uvicorn.Server(config)
    await server.serve()

# app = FastAPI()
app = FastAPI(lifespan=run_websocket_server)

@app.get("/")
async def get():
    return HTMLResponse(html)

asyncio.run(main())