import asyncio
import json
import random
import time
from websockets import ServerConnection, serve
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError

# ────────────────────────────────
# Configuration
# ────────────────────────────────
PORT = 8001
ENDPOINT_PATH = "/ws"
PACKET_RATE_HZ = 512
CHANNEL_COUNT = 8  # Match validation rule

# ────────────────────────────────
# Generate Valid + Optional Faulty Packets
# ────────────────────────────────
def generate_packet(seq: int, time: float) -> dict:
    packet = {
        "timestamp": time,
        "values": [random.uniform(-50.0, 50.0) for _ in range(CHANNEL_COUNT)],
        "packet_id": f"mock-{seq}",
        "meta": {
            "source": "mock_ws_server",
            "device_id": "mock-01"
        },
        "frequency": PACKET_RATE_HZ
    }

    # TODO add a boolean flag for simulating out of range values.
    # Inject malformed packet every 50th
    # if seq % 50 == 0:
    #     packet.pop("timestamp")

    # TODO add a boolean flag for simulating out of range values.
    # Inject out-of-range values every 120th
    # if seq % 120 == 0:
    #     packet["values"][0] = 9999.0

    return packet

# ────────────────────────────────
# WebSocket Streaming Logic
# ────────────────────────────────
async def stream_packets(websocket: ServerConnection):

    if websocket.request is None or websocket.request.path is None:
        print("Rejected connection on unexpected path: None")
        await websocket.close()
        return

    if websocket.request.path != ENDPOINT_PATH:
        print(f"Rejected connection on unexpected path: {websocket.request.path}")
        await websocket.close()
        return
    path = websocket.request.path
    print(f"Client connected at {path}")
    seq = 0
    interval = 1.0 / PACKET_RATE_HZ

    try:
        next_time = time.perf_counter()
        previous_send = next_time
        while True:
            now = time.perf_counter()
            if now >= next_time:
                timestamp = time.time()
                packet = generate_packet(seq, timestamp)
                await websocket.send(json.dumps(packet))
                seq += 1
                next_time += interval
                try:
                    received_packet = await websocket.recv()
                except Exception as exc:
                    print(f"Error receiving packet: {exc}")
                continue

            sleep_duration = max(0, next_time - now)
            if (sleep_duration > 0.015):
                await asyncio.sleep(sleep_duration)

    except (ConnectionClosedOK, ConnectionClosedError):
        print("Client disconnected.")
    except Exception as e:
        print(f"Unexpected error: {e}")

# ────────────────────────────────
# Entry Point
# ────────────────────────────────
async def main():
    print(f"✅ Mock EEG WebSocket server running at ws://localhost:{PORT}{ENDPOINT_PATH}")
    async with serve(stream_packets, "localhost", PORT):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
