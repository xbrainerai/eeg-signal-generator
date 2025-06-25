import asyncio
import websockets
import json
import random

async def send_fake_data(websocket, path):
    while True:
        message = {
            "timestamp": asyncio.get_event_loop().time(),
            "signal": [random.random() for _ in range(8)]
        }
        await websocket.send(json.dumps(message))
        await asyncio.sleep(0.05)  # simulate 20 Hz stream

start_server = websockets.serve(send_fake_data, "localhost", 8001)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
