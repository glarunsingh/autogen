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

# -------------------- Initialize Single Data Collection Agent --------------------
data_collection_agent = AssistantAgent(
    name="data_collection_agent",
    system_message="""You are a Technical Architect responsible for gathering comprehensive project information.
    Start by analyzing the document provided. If no valid document is available, begin by asking relevant questions to gather project details.
    Topics to cover include:
    - Work Breakdown Structure (WBS) and effort estimation
    - Assumptions
    - Resource costs and types
    - Tech stack costs
    - Infrastructure costs
    - Total cost of ownership for three years
    - Cost estimation as an artifact (Excel)
    - User volume and deployment information

    Ask one question at a time, and confirm responses as you proceed. Summarize the final information for each topic as you complete the questions.""",
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
    """Use data collection agent to ask sequential questions and gather responses."""
    collected_data = {}
    conversation_history = []

    # Start with initial content, either from document or initial prompt
    user_proxy_result = user_proxy.initiate_chat(
        recipient=data_collection_agent,
        message=content,

    )
    conversation_history.append({"role": "user", "message": content})

    while True:
        # Get response from data_collection_agent
        data_collection_response = data_collection_agent.chat_messages[user_proxy][-1]["content"]
        print(f"\nData Collection Agent: {data_collection_response}")
        
        # Break if agent indicates completion
        if "TERMINATE" in data_collection_response:
            print("\nData Collection Completed.")
            break

        # Collect user response for the next question
        user_response = input("User: ")
        collected_data[data_collection_agent.name] = user_response
        user_proxy_result = user_proxy.initiate_chat(
            recipient=data_collection_agent,
            message=user_response,
        )
        conversation_history.append({"role": "user", "message": user_response})

    return collected_data

# -------------------- Specialized Prompts for Each Section --------------------
def generate_wbs(data):
    prompt = f"Based on the following project details, generate a detailed Work Breakdown Structure (WBS):\n\n{data}"
    response = data_collection_agent.initiate_chat(
        recipient=data_collection_agent,
        message=prompt,
        silent=True,
        human_input_mode="NEVER",
    )
    return response.chat_messages[user_proxy][-1]["content"]

def generate_cost_estimation(data):
    prompt = f"Using the project information provided, estimate the costs including resource costs, tech stack costs, infrastructure costs, and provide a total cost of ownership for three years:\n\n{data}"
    response = data_collection_agent.initiate_chat(
        recipient=data_collection_agent,
        message=prompt,
        silent=True,
        human_input_mode="NEVER",
    )
    return response.chat_messages[user_proxy][-1]["content"]

def generate_assumptions(data):
    prompt = f"List any assumptions made in the project planning based on the provided information:\n\n{data}"
    response = data_collection_agent.initiate_chat(
        recipient=data_collection_agent,
        message=prompt,
        silent=True,
        human_input_mode="NEVER",
    )
    return response.chat_messages[user_proxy][-1]["content"]

def generate_resource_types(data):
    prompt = f"Based on the provided project data, specify the types of resources required:\n\n{data}"
    response = data_collection_agent.initiate_chat(
        recipient=data_collection_agent,
        message=prompt,
        silent=True,
        human_input_mode="NEVER",
    )
    return response.chat_messages[user_proxy][-1]["content"]

def generate_usage_volume(data):
    prompt = f"Determine the estimated user volume and expected deployment requirements from the following data:\n\n{data}"
    response = data_collection_agent.initiate_chat(
        recipient=data_collection_agent,
        message=prompt,
        silent=True,
        human_input_mode="NEVER",
    )
    return response.chat_messages[user_proxy][-1]["content"]

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
    
    # Use collected data to generate responses for each topic
    wbs = generate_wbs(collected_data)
    cost_estimation = generate_cost_estimation(collected_data)
    assumptions = generate_assumptions(collected_data)
    resource_types = generate_resource_types(collected_data)
    usage_volume = generate_usage_volume(collected_data)

    # Display final collected and processed data
    final_data = {
        "summary": content,
        "collected_data": collected_data,
        "WBS": wbs,
        "Cost Estimation": cost_estimation,
        "Assumptions": assumptions,
        "Resource Types": resource_types,
        "Usage Volume": usage_volume,
    }
    print("\nFinal Project Estimation:\n", json.dumps(final_data, indent=2))
    return final_data

# -------------------- Execution --------------------
if __name__ == "__main__":
    doc_path = input("Enter the document path (or press Enter to skip): ").strip()
    process_document_or_summary(doc_path)
