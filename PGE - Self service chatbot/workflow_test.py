import autogen
import json
from autogen import AssistantAgent, UserProxyAgent
from pypdf import PdfReader
from autogen import register_function
from bing_search import bing_search
import convertor as convertor   
from task import *


llm_config = {
    "timeout": 600,
    "config_list": autogen.config_list_from_json(
        "OAI_CONFIG_LIST"
    ),
    "temperature": 0,
}

input_assistant = AssistantAgent(
    name = "input_assistant",
    # human_input_mode="NEVER",
    system_message = """You are a helpful AI assistant. 
    User is planning to buy a car.
    You have to collect the car model, brand, manufacturing year etc from the user by asking series of questions.
    You have find the details of the car like eg: downpayment, Insurance provider, tax details etc., 
    Reply 'TERMINATE' in the end when everything is done.
""",
    llm_config=llm_config,
    )

user_proxy = UserProxyAgent("user_proxy",
                            human_input_mode="ALWAYS",
                            llm_config=llm_config,    
                            code_execution_config=False,
                            system_message = "You are a helpful assistant." 
                            )
user_input = "Hi"

user_proxy.initiate_chat(
    input_assistant,
    message=user_input,
)