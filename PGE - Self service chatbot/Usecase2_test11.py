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

# -------------------- Define Helper Functions --------------------
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

# -------------------- Define Individual Agents for Each Section --------------------
wbs_agent = AssistantAgent(
    name="wbs_agent",
    system_message="You are gathering details for Work Breakdown Structure (WBS) and effort estimation. Please ask questions to clarify and gather all relevant data.",
    llm_config=llm_config,
)

assumptions_agent = AssistantAgent(
    name="assumptions_agent",
    system_message="You are gathering assumptions related to the project. Ask detailed questions to clarify and collect all assumptions that will affect project planning.",
    llm_config=llm_config,
)

resource_cost_agent = AssistantAgent(
    name="resource_cost_agent",
    system_message="You are gathering resource cost estimation. Ask detailed questions about the resources required, their costs, and relevant financial details.",
    llm_config=llm_config,
)

tech_stack_cost_agent = AssistantAgent(
    name="tech_stack_cost_agent",
    system_message="You are gathering details on tech stack costs. Ask questions about the technologies planned for this project and their associated costs.",
    llm_config=llm_config,
)

infrastructure_cost_agent = AssistantAgent(
    name="infrastructure_cost_agent",
    system_message="You are gathering infrastructure cost details. Ask questions to clarify the infrastructure needed and the associated costs.",
    llm_config=llm_config,
)

total_ownership_cost_agent = AssistantAgent(
    name="total_ownership_cost_agent",
    system_message="You are gathering total cost of ownership over three years. Ask questions on maintenance, support, and any recurring costs.",
    llm_config=llm_config,
)

excel_cost_estimation_agent = AssistantAgent(
    name="excel_cost_estimation_agent",
    system_message="You are gathering detailed cost estimation information to create an Excel artifact. Ask questions to gather specific financial details.",
    llm_config=llm_config,
)

resource_types_agent = AssistantAgent(
    name="resource_types_agent",
    system_message="You are identifying types of resources required for the project. Ask questions to specify the necessary resources.",
    llm_config=llm_config,
)

user_volume_agent = AssistantAgent(
    name="user_volume_agent",
    system_message="You are estimating user volume and deployment scope. Ask questions to determine expected user demand and deployment requirements.",
    llm_config=llm_config,
)

# -------------------- Define User Proxy Agent --------------------
user_proxy = UserProxyAgent(
    name="user_proxy",
    human_input_mode="ALWAYS",
    llm_config=llm_config,
    system_message="You are a helpful assistant.",
    code_execution_config={
        "last_n_messages": 1,
        "work_dir": "tasks",
        "use_docker": False,
    },
)

# -------------------- Main Logic --------------------
def process_document_or_summary(doc_path=None):
    """Process document or initiate with user-provided summary."""
    content = read_document(doc_path)

    if content:
        print(f"\nExtracted Content from '{doc_path}':\n{content}\n")
    else:
        print("No document provided. Please enter a summary.\n")
        content = input("Enter a summary of the process: ")

    # Define initial task messages for each agent, passing `content` to `wbs_agent`
    tasks = [
        {
            "recipient": wbs_agent,
            "message": content,
            "summary_method": "reflection_with_llm",
        },
        {
            "recipient": assumptions_agent,
            "message": "Please gather project assumptions based on this data.",
            "summary_method": "reflection_with_llm",
        },
    ]

    # Initiate chats sequentially with each agent
    chat_results = user_proxy.initiate_chats(tasks)

    # Display final collected and processed data
    final_data = {}
    
    # Collect responses from each agent's chat messages
    #final_data["summary"] = content  # Add the initial content summary

    # Retrieve the final response messages from each agent and store them in the final data dictionary
    test = wbs_agent.chat_messages
    print(test)

    test2 = chat_results
    print(test2)

    test3 = chat_results.summary
    print(test3)
    
    # final_data["WBS"] = wbs_agent.chat_messages#[user_proxy][-2]["content"]
    # final_data["Assumptions"] = assumptions_agent.chat_messages[user_proxy][-2]["content"]
    # final_data["Resource Cost"] = resource_cost_agent.chat_messages[user_proxy][-2]["content"]
    # final_data["Tech Stack Cost"] = tech_stack_cost_agent.chat_messages[user_proxy][-2]["content"]
    # final_data["Infrastructure Cost"] = infrastructure_cost_agent.chat_messages[user_proxy][-2]["content"]
    # final_data["Total Ownership Cost"] = total_ownership_cost_agent.chat_messages[user_proxy][-2]["content"]
    # final_data["Excel Cost Estimation"] = excel_cost_estimation_agent.chat_messages[user_proxy][-2]["content"]
    # final_data["Resource Types"] = resource_types_agent.chat_messages[user_proxy][-2]["content"]
    # final_data["User Volume"] = user_volume_agent.chat_messages[user_proxy][-2]["content"]

    # Print the final data for verification
    print("\n*************************Final Project Estimation*****************************")

    print(json.dumps(final_data, indent=2))


# -------------------- Execution --------------------
if __name__ == "__main__":
    doc_path = input("Enter the document path (or press Enter to skip): ").strip()
    process_document_or_summary(doc_path)