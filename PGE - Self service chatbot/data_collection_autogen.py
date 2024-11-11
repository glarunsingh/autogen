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
input_assistant = AssistantAgent(
    name="input_assistant",
    system_message="""You are a helpful AI assistant. 
    Your task is to analyze the content provided by the user, ask clarifying questions, and collect responses one by one. 
    Use follow-up questions to understand requirements thoroughly. Type 'TERMINATE' when the data collection is complete.
    """,
    llm_config=llm_config,
)

user_proxy = UserProxyAgent(
    "user_proxy",
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

    # Start Autogen Q&A loop
    user_proxy_agent_result = user_proxy.initiate_chat(
        recipient=input_assistant,
        message=user_input,
    )
    conversation_history.append({"role": "user", "message": user_input})

    # Collect the conversation history from the user_proxy_agent_result
    for message in user_proxy_agent_result.messages:
        conversation_history.append({
            "role": message["role"],
            "message": message["content"]
        })

    return conversation_history, user_proxy_agent_result

def process_document_or_summary(doc_path=None):
    """Process document or initiate with user-provided summary."""
    content = read_document(doc_path)

    if content:
        print(f"\nExtracted Content from '{doc_path}':\n{content}\n")
    else:
        print("No document provided. Please enter a summary.\n")
        content = input("Enter a summary of the process: ")

    conversation_history, user_proxy_agent_result = analyze_and_start_autogen_qa(content)

    # Pass the collected data to the next module or store it
    collected_data = {
        "summary": content,
        "conversation_history": conversation_history
    }
    print("\nFinal Collected Data:\n", json.dumps(collected_data, indent=2))
    print("\nUser Proxy Agent Result:\n", user_proxy_agent_result)
    return collected_data

# -------------------- Execution --------------------
if __name__ == "__main__":
    doc_path = input("Enter the document path (or press Enter to skip): ").strip()
    process_document_or_summary(doc_path)
