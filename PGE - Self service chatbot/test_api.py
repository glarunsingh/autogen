import autogen
from datetime import datetime
from tempfile import TemporaryDirectory

from websockets.sync.client import connect as ws_connect

import autogen
from autogen.io.websockets import IOWebsockets



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
    agent = autogen.ConversableAgent(
        name="chatbot",
        system_message="""You are a helpful AI assistant. 
    User is planning to buy a car.
    You have to collect the car model, brand, manufacturing year etc from the user by asking series of questions.
    You have find the details of the car like eg: downpayment, Insurance provider, tax details etc., 
    Reply 'TERMINATE' in the end when everything is done.
""",
        llm_config=llm_config,
    )

    # 3. Define UserProxyAgent
    user_proxy = autogen.UserProxyAgent(
        name="user_proxy",
        llm_config=llm_config,
        system_message="You are a helpful assistant.",
        # is_termination_msg=lambda x: x.get("content", "") and x.get("content", "").rstrip().endswith("TERMINATE"),
        human_input_mode="ALWAYS",
        # max_consecutive_auto_reply=10,
        code_execution_config=False,
    )

    # 4. Define Agent-specific Functions
    # def weather_forecast(city: str) -> str:
    #     return f"The weather forecast for {city} at {datetime.now()} is sunny."

    # autogen.register_function(
    #     weather_forecast, caller=agent, executor=user_proxy, description="Weather forecast for a city"
    # )

    # 5. Initiate conversation
    print(
        f" - on_connect(): Initiating chat with agent {agent} using message '{initial_msg}'",
        flush=True,
    )
    user_proxy.initiate_chat(  # noqa: F704
        agent,
        message=initial_msg,
    )




from contextlib import asynccontextmanager  # noqa: E402
from pathlib import Path  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.responses import HTMLResponse  # noqa: E402
import uvicorn  # noqa: E402
import asyncio
PORT = 8080

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