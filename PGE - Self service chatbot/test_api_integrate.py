import autogen
from datetime import datetime
from tempfile import TemporaryDirectory
from websockets.sync.client import connect as ws_connect
import autogen
from autogen.io.websockets import IOWebsockets
import os
import json
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from docx import Document as DocxDocument
from PyPDF2 import PdfReader
from dotenv import load_dotenv
from autogen import AssistantAgent, UserProxyAgent
import autogen

from contextlib import asynccontextmanager  # noqa: E402
from pathlib import Path  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.responses import HTMLResponse  # noqa: E402
import uvicorn  # noqa: E402
import asyncio
PORT = 8080


llm_config = {
    "timeout": 600,
    "config_list": autogen.config_list_from_json(
        "OAI_CONFIG_LIST"
    ),
    "temperature": 0,
}

def on_connect(iostream: IOWebsockets) -> None:
    print(f" - on_connect(): Connected to client using IOWebsockets {iostream}", flush=True)
    print(" - on_connect(): Receiving message from client.", flush=True)

    # 1. Receive Initial Message
    initial_msg = iostream.input()

    # 2. Instantiate ConversableAgent

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
    human_input_mode="NEVER",
    )



# -------------------------------------------------------------------------------------------------

#     agent = autogen.ConversableAgent(
#         name="chatbot",
#         system_message="""You are a helpful AI assistant. 
#     User is planning to buy a car.
#     You have to collect the car model, brand, manufacturing year etc from the user by asking series of questions.
#     You have find the details of the car like eg: downpayment, Insurance provider, tax details etc., 
#     Reply 'TERMINATE' in the end when everything is done.
# """,
#         llm_config=llm_config,
#     )

    # 3. Define UserProxyAgent

    user_proxy = UserProxyAgent(
        name="user_proxy",
        human_input_mode="ALWAYS",
        llm_config=llm_config,
        code_execution_config=False,
        system_message="You are a helpful assistant."
    )

    # user_proxy = autogen.UserProxyAgent(
    #     name="user_proxy",
    #     llm_config=llm_config,
    #     system_message="You are a helpful assistant.",
    #     # is_termination_msg=lambda x: x.get("content", "") and x.get("content", "").rstrip().endswith("TERMINATE"),
    #     human_input_mode="ALWAYS",
    #     # max_consecutive_auto_reply=10,
    #     code_execution_config=False,
    # )

    # 4. Define Agent-specific Functions
    # def weather_forecast(city: str) -> str:
    #     return f"The weather forecast for {city} at {datetime.now()} is sunny."

    # autogen.register_function(
    #     weather_forecast, caller=agent, executor=user_proxy, description="Weather forecast for a city"
    # )

    # 5. Initiate conversation
    print(
        f" - on_connect(): Initiating chat with agent {data_collection_agent} using message '{initial_msg}'",
        flush=True,
    )
    # Start sequential chat between agents using `initiate_chats`
    chat_results = user_proxy.initiate_chats(
        [
            {
                "recipient": data_collection_agent,
                "message": "You are a Technical architect. Your job is to arrive at the tech stack for a problem statement and also arrive at estimates for the application in scope.",
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

    # ---------------------------------------------------------------------------------
    # user_proxy.initiate_chat(  # noqa: F704
    #     agent,
    #     message=initial_msg,
    # )






html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Autogen websocket test</title>
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


app = FastAPI(lifespan=run_websocket_server)


@app.get("/")
async def get():
    return HTMLResponse(html)


async def main():
    config = uvicorn.Config(app)
    server = uvicorn.Server(config)
    await server.serve()  # noqa: F704

asyncio.run(main())