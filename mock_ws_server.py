import asyncio
import json
import random
import time
from websockets.server import serve
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError

PORT = 8001
ENDPOINT_PATH = "/ws"
PACKET_RATE_HZ = 256
CHANNEL_COUNT = 2

def generate_packet(seq: int) -> dict:
    return {
        "timestamp": time.time(),
        "channel_count": CHANNEL_COUNT,
        "sampling_rate": PACKET_RATE_HZ,
        "signal_type": "EEG",
        "packet_id": f"mock-{seq}",
        "data": [random.uniform(-0.1, 0.1) for _ in range(CHANNEL_COUNT)],
        "meta": {
            "source": "mock_ws_server",
            "device_id": "mock-01"
        }
    }

async def stream_packets(websocket, path):
    if path != ENDPOINT_PATH:
        print(f"Rejected connection on unexpected path: {path}")
        await websocket.close()
        return

    print(f"Client connected at {path}")
    seq = 0
    interval = 1.0 / PACKET_RATE_HZ
    try:
        while True:
            packet = generate_packet(seq)
            await websocket.send(json.dumps(packet))
            await asyncio.sleep(interval)
            seq += 1
    except (ConnectionClosedOK, ConnectionClosedError):
        print("Client disconnected.")
    except Exception as e:
        print(f"Unexpected error: {e}")

async def main():
    print(f"Mock EEG WebSocket server running on ws://localhost:{PORT}{ENDPOINT_PATH}")
    async with serve(stream_packets, "localhost", PORT):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
