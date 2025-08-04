import asyncio
import json
import random
import time
import argparse
from websockets import ServerConnection, serve
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError

# ────────────────────────────────
# Configuration
# ────────────────────────────────
def parse_arguments():
    parser = argparse.ArgumentParser(description='Mock EEG WebSocket Server')
    parser.add_argument('--port', type=int, default=8001, help='Port to run the server on (default: 8001)')
    parser.add_argument('--packet-rate', type=int, default=256, help='Packet rate in Hz (default: 512)')
    parser.add_argument('--channel-count', type=int, default=8, help='Number of EEG channels (default: 8)')
    return parser.parse_args()

args = parse_arguments()
PORT = args.port
PACKET_RATE_HZ = args.packet_rate
CHANNEL_COUNT = args.channel_count  # Match validation rule

ENDPOINT_PATH = "/ws"
CLOCK_RESOLUTION = 0.015 # 15ms
INTERVAL = 1.0 / PACKET_RATE_HZ
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


async def generate_packets(packet_queue: asyncio.Queue):
    seq = 0
    try:
        next_time = time.perf_counter()
        while True:
            now = time.perf_counter()
            if now >= next_time:
                timestamp = time.time()
                packet = generate_packet(seq, timestamp)
                await packet_queue.put(packet)
                seq += 1
                next_time += INTERVAL
                continue

            sleep_duration = max(0, next_time - now)
            if (sleep_duration > CLOCK_RESOLUTION):
                await asyncio.sleep(sleep_duration)

    except (ConnectionClosedOK, ConnectionClosedError):
        print("Client disconnected.")
    except Exception as e:
        print(f"Unexpected error: {e}")

async def send_packets(websocket: ServerConnection, packet_queue: asyncio.Queue):
        while True:
            packet = await packet_queue.get()
            await websocket.send(json.dumps(packet))
            #await websocket.recv() # ACKNOWLEDGEMENT RECEIVED HERE

# ────────────────────────────────
# WebSocket Streaming Logic
# ────────────────────────────────
async def run_packet_server(websocket: ServerConnection):
    packet_queue = asyncio.Queue(1)

    if websocket.request is None or websocket.request.path is None:
        print("Rejected connection on unexpected path: None")
        await websocket.close()
        return

    if websocket.request.path != ENDPOINT_PATH:
        print(f"Rejected connection on unexpected path: {websocket.request.path}")
        await websocket.close()
        return

    print(f"Client connected at {websocket.request.path}")

    try:
        await asyncio.gather(generate_packets(packet_queue), send_packets(websocket, packet_queue))
    except (ConnectionClosedOK, ConnectionClosedError):
        print("Client disconnected.")
    except Exception as e:
        print(f"Unexpected error: {e}")

# ────────────────────────────────
# Entry Point
# ────────────────────────────────
async def main():
    print(f"✅ Mock EEG WebSocket server running at ws://localhost:{PORT}{ENDPOINT_PATH}")
    async with serve(run_packet_server, "localhost", PORT):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
