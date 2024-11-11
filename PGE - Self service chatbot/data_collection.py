import os
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from docx import Document as DocxDocument
from PyPDF2 import PdfReader
from dotenv import load_dotenv

# -------------------- Load Environment Variables --------------------
load_dotenv()

api_version = os.getenv("AZURE_OPENAI_API_VERSION")
endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
api_key = os.getenv("AZURE_OPENAI_API_KEY")
deployment_name = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
llm_model = os.getenv("LLM_MODEL")

if not all([api_version, endpoint, api_key, deployment_name, llm_model]):
    raise ValueError("Some environment variables are missing. Check your .env file.")

# Initialize AzureChatOpenAI model
llm = AzureChatOpenAI(
    azure_deployment=deployment_name,
    api_version=api_version,
    temperature=0.7,
    max_tokens=500,
    max_retries=2,
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

# -------------------- Chat Prompt Setup --------------------
prompt_text = """
You are a Technical Architect. Your task is to gather the necessary requirements to suggest 
a tech stack and provide project estimates. Ask questions one-by-one to understand the scope, 
integration points, tech stack, and the complexity of the application. Justify your estimates, 
make reasonable assumptions if details are missing, and provide work breakdowns for each task.
"""

prompt = ChatPromptTemplate.from_messages([("system", prompt_text)])

# -------------------- Q&A Logic --------------------
def ask_questions_one_by_one(questions):
    responses = {}  # Store responses with questions as keys

    for i, question in enumerate(questions):
        print(f"\nAssistant: {question}")
        user_response = input("User: ")
        responses[question] = user_response

        if user_response.lower() in ['exit', 'quit']:
            print("Exiting the conversation.")
            break

    print("\nCollected Responses:")
    for q, r in responses.items():
        print(f"{q}: {r}")

    return responses  # Return collected responses for further use

# -------------------- Main Logic --------------------
def analyze_and_start_qa(content):
    """Analyze the content and extract relevant questions."""
    response = llm.invoke([("system", prompt_text), ("human", content)])
    print("\nAnalysis Report:\n")
    print(response.content)  # Display the analysis to the user

    questions = extract_questions_from_response(response.content)
    print("\nStarting Q&A based on the analysis...\n")
    return ask_questions_one_by_one(questions)

def extract_questions_from_response(response_text):
    """Extract questions from LLM's response."""
    lines = response_text.split("\n")
    questions = [line.strip() for line in lines if line.endswith('?')]
    return questions

def process_document_or_questions(doc_path=None):
    """Process document content or start with a user-provided summary."""
    content = read_document(doc_path)

    if content:
        print(f"\nExtracted Content from '{doc_path}':\n{content}\n")
        analyze_and_start_qa(content)
    else:
        print("No valid document provided. Please provide a summary.\n")
        user_summary = input("Enter a summary of the process: ")
        analyze_and_start_qa(user_summary)

# -------------------- Execution --------------------
if __name__ == "__main__":
    doc_path = input("Enter the document path (or press Enter to skip): ").strip()
    process_document_or_questions(doc_path)