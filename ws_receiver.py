import asyncio, websockets, json
async def recv():
    async with websockets.connect("ws://localhost:8765") as ws:
        while True:
            print(json.loads(await ws.recv())["channels"][:3])
asyncio.run(recv())
