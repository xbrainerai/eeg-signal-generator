import asyncio
import websockets
import json
import random
from websockets.asyncio.server import serve

async def send_fake_data(websocket):
    while True:
        message = {
            "timestamp": asyncio.get_event_loop().time(),
            "signal": [random.random() for _ in range(8)]
        }
        print(message)
        await websocket.send(json.dumps(message))
        await asyncio.sleep(0.05)  # simulate 20 Hz stream


async def main():
    async with serve(send_fake_data, "localhost", 8001) as server:
        await server.serve_forever()

asyncio.run(main())
