import sys
import os
# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import asyncio
import json
import random
import time
import argparse
import urllib.parse
from websockets import ServerConnection, serve
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError
from auth.mock_authenticator import MockAuthenticator

# ────────────────────────────────
# Configuration
# ────────────────────────────────
def parse_arguments():
    parser = argparse.ArgumentParser(description='Mock EEG WebSocket Server')
    parser.add_argument('--port', type=int, default=8001, help='Port to run the server on (default: 8001)')
    parser.add_argument('--packet-rate', type=int, default=256, help='Packet rate in Hz (default: 512)')
    parser.add_argument('--channel-count', type=int, default=8, help='Number of EEG channels (default: 8)')
    parser.add_argument('--no-auth', action='store_true', help='Disable authentication (default: authentication required)')
    parser.add_argument('--simulate-out-of-range', action='store_true', help='Simulate out-of-range values (default: False)')
    parser.add_argument('--simulate-missing-timestamp', action='store_true', help='Simulate missing timestamp (default: False)')
    return parser.parse_args()

args = parse_arguments()
authenticator = MockAuthenticator()

PORT = args.port
PACKET_RATE_HZ = args.packet_rate
CHANNEL_COUNT = args.channel_count  # Match validation rule
REQUIRE_AUTH = not args.no_auth
SIMULATE_OUT_OF_RANGE = args.simulate_out_of_range
SIMULATE_MISSING_TIMESTAMP = args.simulate_missing_timestamp
ENDPOINT_PATH = "/ws"
CLOCK_RESOLUTION = 0.015 # 15ms
INTERVAL = 1.0 / PACKET_RATE_HZ

# ────────────────────────────────
# Authentication Logic
# ────────────────────────────────
def extract_token_from_request(request) -> str | None:
    """Extract authentication token from WebSocket request query parameters."""
    if not request or not request.path:
        return None

    # Parse query parameters
    if '?' in request.path:
        path, query = request.path.split('?', 1)
        params = urllib.parse.parse_qs(query)
        return params.get('token', [None])[0]

    return None

def authenticate_connection(websocket: ServerConnection) -> bool:
    """Authenticate the WebSocket connection during handshake."""
    if not REQUIRE_AUTH:
        return True

    if websocket.request is None:
        print("❌ Authentication failed: No request object")
        return False

    token = extract_token_from_request(websocket.request)

    if not token:
        print("❌ Authentication failed: No token provided")
        return False

    if not authenticator.authenticate(token):
        print("❌ Authentication failed: Invalid token")
        return False

    print("✅ Authentication successful")
    return True

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

    # Inject malformed packet every 50th
    if SIMULATE_MISSING_TIMESTAMP and seq % 50 == 0:
        packet.pop("timestamp")

    # TODO add a boolean flag for simulating out of range values.
    # Inject out-of-range values every 120th
    if SIMULATE_OUT_OF_RANGE and seq % 120 == 0:
        packet["values"][0] = 9999.0

    return packet


async def generate_packets(packet_queue: asyncio.Queue, websocket: ServerConnection):
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
                await websocket.recv()
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
             # ACKNOWLEDGEMENT RECEIVED HERE

# ────────────────────────────────
# WebSocket Streaming Logic
# ────────────────────────────────
async def run_packet_server(websocket: ServerConnection):
    # Authenticate during handshake
    if not authenticate_connection(websocket):
        await websocket.close(1008, "Authentication failed")
        return

    # Validate endpoint path
    if websocket.request is None or websocket.request.path is None:
        print("❌ Rejected connection on unexpected path: None")
        await websocket.close(1008, "Invalid endpoint")
        return

    # Extract path without query parameters for validation
    path = websocket.request.path.split('?')[0]
    if path != ENDPOINT_PATH:
        print(f"❌ Rejected connection on unexpected path: {path}")
        await websocket.close(1008, "Invalid endpoint")
        return

    print(f"✅ Client connected at {path}")

    packet_queue = asyncio.Queue(2)

    try:
        await asyncio.gather(generate_packets(packet_queue, websocket), send_packets(websocket, packet_queue))
    except (ConnectionClosedOK, ConnectionClosedError):
        print("Client disconnected.")
    except Exception as e:
        print(f"Unexpected error: {e}")

# ────────────────────────────────
# Entry Point
# ────────────────────────────────
async def main():
    auth_status = "with authentication" if REQUIRE_AUTH else "without authentication"
    print(f"✅ Mock EEG WebSocket server running at ws://localhost:{PORT}{ENDPOINT_PATH} ({auth_status})")
    if REQUIRE_AUTH:
        print(f"🔑 Use token: {MockAuthenticator.SECRET_KEY}")
        print(f"📡 Connect with: ws://localhost:{PORT}{ENDPOINT_PATH}?token={MockAuthenticator.SECRET_KEY}")

    async with serve(run_packet_server, "localhost", PORT):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
