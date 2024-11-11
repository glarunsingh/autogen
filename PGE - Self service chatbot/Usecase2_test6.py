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

# -------------------- Initialize Autogen Agents --------------------
agents = {
    "wbs_effort_agent": AssistantAgent(
        name="wbs_effort_agent",
        system_message="Analyze the provided information and produce a detailed work breakdown structure (WBS) and effort estimation for the project without asking further questions.",
        llm_config=llm_config,
    ),
    "assumptions_agent": AssistantAgent(
        name="assumptions_agent",
        system_message="Based on the collected information, list all assumptions made in the project as a text format. Do not ask any additional questions.",
        llm_config=llm_config,
    ),
    "resource_cost_agent": AssistantAgent(
        name="resource_cost_agent",
        system_message="Using the collected data, provide an estimation of the resource costs required for the project. Avoid asking any further questions.",
        llm_config=llm_config,
    ),
    "tech_stack_cost_agent": AssistantAgent(
        name="tech_stack_cost_agent",
        system_message="Calculate the estimated costs associated with the tech stack involved in the project using only the provided data. Do not initiate further questions.",
        llm_config=llm_config,
    ),
    "infra_cost_agent": AssistantAgent(
        name="infra_cost_agent",
        system_message="Estimate the infrastructure costs required for the project based solely on the collected information. Do not ask any questions.",
        llm_config=llm_config,
    ),
    "tco_agent": AssistantAgent(
        name="tco_agent",
        system_message="Using the collected data, provide the total cost of ownership for three years, covering all expenses. Avoid asking any further questions.",
        llm_config=llm_config,
    ),
    "cost_estimation_agent": AssistantAgent(
        name="cost_estimation_agent",
        system_message="Generate a detailed cost estimation artifact as an Excel document for the project based on the information collected. Do not ask any additional questions.",
        llm_config=llm_config,
    ),
    "resource_type_agent": AssistantAgent(
        name="resource_type_agent",
        system_message="Specify the types of resources required for the project using only the provided data. Avoid further questioning.",
        llm_config=llm_config,
    ),
    "usage_volume_agent": AssistantAgent(
        name="usage_volume_agent",
        system_message="Based on the collected information, determine the intended user base and estimated usage volume for the deployment of the project. Do not ask any additional questions.",
        llm_config=llm_config,
    ),
}

user_proxy = UserProxyAgent(
    "user_proxy",
    human_input_mode="ALWAYS",
    llm_config=llm_config,
    code_execution_config=False,
    system_message="You are a helpful assistant."
)

data_collection_agent = AssistantAgent(
    name="data_collection_agent",
    system_message="""You are a Technical architect responsible for gathering all necessary information for project estimation.
    Your task is to interact with the user to ask detailed, relevant questions based on the following topics:
    - Work Breakdown Structure (WBS) and effort estimation
    - Assumptions about the project
    - Resource cost estimation
    - Tech stack costs
    - Infrastructure costs
    - Total cost of ownership for up to three years
    - Detailed cost estimation as an artifact (Excel)
    - Types of resources required
    - Expected user volume and deployment scope

    Ask one question at a time to ensure clarity. Collect all information on these topics before concluding. Use responses from the user to form follow-up questions when needed.""",
    llm_config=llm_config,
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
def collect_data_with_data_collection_agent(content):
    """Use data collection agent to ask sequential questions and gather responses."""
    collected_data = {}
    conversation_history = []

    # Start with initial content
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

def process_with_agents(collected_data):
    """Send collected data to each agent and gather their responses."""
    results = {}

    for key, agent in agents.items():
        input_message = collected_data.get(data_collection_agent.name, "")
        if input_message:
            response = agent.initiate_chat(
                recipient=agent,
                message=input_message,
                silent=True,
            )
            # Capture the response and add to results dictionary
            agent_response = agent.chat_messages[user_proxy][-2]["content"]
            results[key] = agent_response
            print(f"\nResponse from {agent.name}: {agent_response}")

    return results

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
    
    # Pass the data to each agent and gather responses
    agent_responses = process_with_agents(collected_data)

    # Display final collected and processed data
    final_data = {
        "summary": content,
        "collected_data": collected_data,
        "agent_responses": agent_responses,
    }
    print("\nFinal Collected Data:\n", json.dumps(final_data, indent=2))
    return final_data

# -------------------- Execution --------------------
if __name__ == "__main__":
    doc_path = input("Enter the document path (or press Enter to skip): ").strip()
    process_document_or_summary(doc_path)