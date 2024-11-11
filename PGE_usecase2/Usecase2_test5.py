import os
import json
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from docx import Document as DocxDocument
from PyPDF2 import PdfReader
from dotenv import load_dotenv
from autogen import AssistantAgent, UserProxyAgent
import autogen

# -------------------- Load Environment Variables --------------------
load_dotenv()

api_version = os.getenv("AZURE_OPENAI_API_VERSION")
endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
api_key = os.getenv("AZURE_OPENAI_API_KEY")
deployment_name = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
llm_model = os.getenv("LLM_MODEL")

if not all([api_version, endpoint, api_key, deployment_name, llm_model]):
    raise ValueError("Some environment variables are missing. Check your .env file.")

# Configure Autogen LLM
llm_config = {
    "timeout": 600,
    "config_list": autogen.config_list_from_json("OAI_CONFIG_LIST"),
    "temperature": 0,
}

# Initialize Autogen Agents
data_collection_agent = AssistantAgent(
    name="data_collection_agent",
    system_message="""You are a Technical architect. Your job is to arrive at the tech stack for a problem statement and also arrive at estimates for the application in scope. 
    You interact with the customer in a chat format and obtain information necessary to come up with estimates. 
    Ask a series of questions covering the application overview, tech stack involved, integration points, and develop a work breakdown of the complex problem statement. 
    Provide justifications for each estimate and list assumptions. If certain information is not provided, make assumptions and arrive at estimates. 
    Always suggest leading open source frameworks wherever possible and call out the reasons for it. 
    Decide technologies and tech stacks based on volume. All infra hosting will incur cost and while giving an estimate take into account the cost of hosting as well.
    You should ask questions one by one as this will be best experience for the user.Don't ask all your questions at once.""",
    llm_config=llm_config,
)

estimation_agent = AssistantAgent(
    name="estimation_agent",
    system_message="""You are a Technical architect. Your job is to generate high-level functionalities/modules, tech stack, volumetrics, feasibility, convert conversation to high-level requirements, WBS, high-level functionalities, costing, assumptions, timeline, resources, and TCO based on the data collected by the data collection agent.
    """,
    llm_config=llm_config,
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
    user_input = content
    conversation_history = []  # Store the entire conversation

    # Start sequential chat between agents using `initiate_chats`
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
        final_data["data_collection_response"] = data_collection_messages[-2]["content"]  # Last meaningful message

    # Retrieve messages from estimation_agent
    estimation_messages = estimation_agent.chat_messages[user_proxy]
    if estimation_messages:
        final_data["estimation_response"] = estimation_messages[-2]["content"]  # Last meaningful message

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

# -------------------- Execution --------------------
if __name__ == "__main__":
    doc_path = input("Enter the document path (or press Enter to skip): ").strip()
    process_document_or_summary(doc_path)