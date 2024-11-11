import os
import json
from dotenv import load_dotenv
from docx import Document as DocxDocument
from PyPDF2 import PdfReader
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, File, UploadFile
from fastapi.responses import HTMLResponse
from autogen import AssistantAgent, UserProxyAgent
import autogen
import uvicorn
from contextlib import asynccontextmanager
import asyncio

# -------------------- Load Environment Variables --------------------
load_dotenv()

api_version = os.getenv("AZURE_OPENAI_API_VERSION")
endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
api_key = os.getenv("AZURE_OPENAI_API_KEY")
deployment_name = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
llm_model = os.getenv("LLM_MODEL")

if not all([api_version, endpoint, api_key, deployment_name, llm_model]):
    raise ValueError("Some environment variables are missing. Check your .env file.")

llm_config = {
    "timeout": 600,
    "config_list": autogen.config_list_from_json("OAI_CONFIG_LIST"),
    "temperature": 0,
}

# Initialize FastAPI app
app = FastAPI()

# -------------------- Initialize Autogen Agents --------------------
data_collection_agent = AssistantAgent(
    name="data_collection_agent",
    system_message="""You are a Technical architect. Your job is to arrive at the tech stack for a problem statement and also arrive at estimates for the application in scope. 
    You interact with the customer in a chat format and obtain information necessary to come up with estimates. 
    Ask a series of questions covering the application overview, tech stack involved, integration points, and develop a work breakdown of the complex problem statement. 
    Provide justifications for each estimate and list assumptions. If certain information is not provided, make assumptions and arrive at estimates. 
    Always suggest leading open-source frameworks wherever possible and call out the reasons for it. 
    Decide technologies and tech stacks based on volume. All infra hosting will incur cost, and while giving an estimate, take into account the cost of hosting as well.
    You should ask questions one by one as this will be the best experience for the user. Don't ask all your questions at once.""",
    llm_config=llm_config,
)

estimation_agent = AssistantAgent(
    name="estimation_agent",
    system_message="""You are a Technical architect. Your job is to generate high-level functionalities/modules, tech stack, volumetrics, feasibility, 
    convert conversation to high-level requirements, WBS, high-level functionalities, costing, assumptions, timeline, resources, and TCO based on the data 
    collected by the data collection agent.""",
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

async def read_uploaded_document(file: UploadFile):
    if file.filename.endswith(".txt"):
        return (await file.read()).decode("utf-8")
    elif file.filename.endswith(".docx"):
        with TemporaryDirectory() as temp_dir:
            temp_path = os.path.join(temp_dir, file.filename)
            with open(temp_path, "wb") as f:
                f.write(await file.read())
            return extract_text_from_docx(temp_path)
    elif file.filename.endswith(".pdf"):
        with TemporaryDirectory() as temp_dir:
            temp_path = os.path.join(temp_dir, file.filename)
            with open(temp_path, "wb") as f:
                f.write(await file.read())
            return extract_text_from_pdf(temp_path)
    else:
        return "Unsupported file format. Please upload TXT, DOCX, or PDF."

# HTML content for document upload
html_content = """
<!DOCTYPE html>
<html>
    <head>
        <title>Document Upload for Conversational Q&A</title>
    </head>
    <body>
        <h1>Upload Document or Enter Summary</h1>
        <form action="/upload" method="post" enctype="multipart/form-data">
            <label for="file">Choose document file:</label>
            <input type="file" id="file" name="file">
            <button type="submit">Upload</button>
        </form>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off" placeholder="Enter summary here"/>
            <button>Send</button>
        </form>
        <ul id='messages'></ul>
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

@app.get("/")
async def get_html():
    return HTMLResponse(html_content)

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    content = await read_uploaded_document(file)
    final_data = analyze_and_start_autogen_qa(content)
    return {"message": "Document processed successfully", "data": final_data}

def analyze_and_start_autogen_qa(content):
    """Use Autogen to analyze content and initiate Q&A."""
    user_input = content
    conversation_history = []  # Store the entire conversation

    # Start sequential chat between agents using initiate_chats
    chat_results = user_proxy.initiate_chats(
        [
            {
                "recipient": data_collection_agent,
                "message": user_input,
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
        final_data["data_collection_response"] = data_collection_messages[-1]["content"]  # Last meaningful message

    # Retrieve messages from estimation_agent
    estimation_messages = estimation_agent.chat_messages[user_proxy]
    if estimation_messages:
        final_data["estimation_response"] = estimation_messages[-1]["content"]  # Last meaningful message

    return final_data

# -------------------- WebSocket Connection Handling --------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            final_data = analyze_and_start_autogen_qa(data)
            await websocket.send_text(json.dumps(final_data))
    except WebSocketDisconnect:
        pass

# -------------------- Execution --------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
