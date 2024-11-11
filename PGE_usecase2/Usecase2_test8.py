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

# -------------------- Initialize Data Collection Agent --------------------
data_collection_agent = AssistantAgent(
    name="data_collection_agent",
    system_message="""You are a Technical Architect responsible for gathering comprehensive project information.
    Start by analyzing the document provided. If no valid document is available, begin by asking relevant questions to gather project details.
    Topics to cover include:
    - Work Breakdown Structure (WBS) 
    - Effort estimation for each     

    Ask one question at a time, and confirm responses as you proceed. 
    Summarize the final information for each topic as you complete the questions.
    Don't share your answers with the estimates, effort analysis etc. 
    Reply 'TERMINATE' in the end when everything is done.""",
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

# -------------------- Data Collection Process --------------------
def collect_data_with_data_collection_agent(content):
    """Use data collection agent to ask initial questions and gather responses."""
    collected_data = {}

    # Start conversation with initial content, either from document or user-provided summary
    chat_results = user_proxy.initiate_chat(
        recipient=data_collection_agent,
        message=content,
        summary_method="reflection_with_llm",
    )

    # Process chat results
    print(chat_results.summary)
    collected_data = chat_results.summary

    return collected_data

# -------------------- Main Logic --------------------
def process_document_or_summary(doc_path=None):
    """Process document or initiate with user-provided summary."""
    content = read_document(doc_path)

    if content:
        print(f"\nExtracted Content from '{doc_path}':\n{content}\n")
    else:
        print("No document provided. Please enter a summary.\n")
        content = input("Enter a summary of the process: ")

    # Collect data through data collection module
    collected_data = collect_data_with_data_collection_agent(content)
    
    # Display final collected data
    final_data = {
        "summary": content,
        "collected_data": collected_data,
    }
    print("\nFinal Project Estimation:\n", json.dumps(final_data, indent=2))
    return final_data

# -------------------- Execution --------------------
if __name__ == "__main__":
    doc_path = input("Enter the document path (or press Enter to skip): ").strip()
    process_document_or_summary(doc_path)
