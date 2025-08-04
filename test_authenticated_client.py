#!/usr/bin/env python3
"""
Test client for the authenticated EEG WebSocket server.
This script demonstrates how to connect to the server with proper authentication.
"""

import asyncio
import json
import websockets
from auth.mock_authenticator import MockAuthenticator

async def test_authenticated_connection():
    """Test connection to the EEG server with authentication."""

    # Server configuration
    host = "localhost"
    port = 8001
    endpoint = "/ws"
    token = MockAuthenticator.SECRET_KEY

    # Build WebSocket URL with authentication token
    ws_url = f"ws://{host}:{port}{endpoint}?token={token}"

    print(f"🔗 Connecting to: {ws_url}")

    try:
        async with websockets.connect(ws_url) as websocket:
            print("✅ Successfully connected to EEG server!")

            # Receive and display a few packets
            packet_count = 0
            max_packets = 5

            while packet_count < max_packets:
                try:
                    message = await websocket.recv()
                    packet = json.loads(message)

                    print(f"📦 Received packet {packet_count + 1}:")
                    print(f"   Timestamp: {packet.get('timestamp')}")
                    print(f"   Packet ID: {packet.get('packet_id')}")
                    print(f"   Values: {len(packet.get('values', []))} channels")
                    print(f"   Frequency: {packet.get('frequency')} Hz")
                    print()

                    # Send acknowledgment
                    await websocket.send("ack")

                    packet_count += 1

                except websockets.exceptions.ConnectionClosed:
                    print("❌ Connection closed by server")
                    break
                except Exception as e:
                    print(f"❌ Error receiving packet: {e}")
                    break

    except websockets.exceptions.InvalidURI:
        print("❌ Invalid WebSocket URI")
    except websockets.exceptions.ConnectionRefused:
        print("❌ Connection refused. Is the server running?")
    except Exception as e:
        print(f"❌ Connection error: {e}")

async def test_unauthenticated_connection():
    """Test connection without authentication (should fail)."""

    host = "localhost"
    port = 8001
    endpoint = "/ws"

    # Connect without token
    ws_url = f"ws://{host}:{port}{endpoint}"

    print(f"\n🔗 Testing unauthenticated connection to: {ws_url}")

    try:
        async with websockets.connect(ws_url) as websocket:
            print("❌ Unexpected: Connection succeeded without authentication!")
            await websocket.close()
    except websockets.exceptions.ConnectionClosed as e:
        print(f"✅ Expected: Connection rejected - {e}")
    except Exception as e:
        print(f"✅ Expected: Connection failed - {e}")

async def test_invalid_token():
    """Test connection with invalid token (should fail)."""

    host = "localhost"
    port = 8001
    endpoint = "/ws"
    invalid_token = "invalid-token"

    # Connect with invalid token
    ws_url = f"ws://{host}:{port}{endpoint}?token={invalid_token}"

    print(f"\n🔗 Testing invalid token connection to: {ws_url}")

    try:
        async with websockets.connect(ws_url) as websocket:
            print("❌ Unexpected: Connection succeeded with invalid token!")
            await websocket.close()
    except websockets.exceptions.ConnectionClosed as e:
        print(f"✅ Expected: Connection rejected - {e}")
    except Exception as e:
        print(f"✅ Expected: Connection failed - {e}")

async def main():
    """Run all authentication tests."""
    print("🧪 Testing EEG Server Authentication")
    print("=" * 50)

    # Test 1: Valid authentication
    await test_authenticated_connection()

    # Test 2: No authentication
    await test_unauthenticated_connection()

    # Test 3: Invalid token
    await test_invalid_token()

    print("\n✅ Authentication tests completed!")

if __name__ == "__main__":
    asyncio.run(main())
