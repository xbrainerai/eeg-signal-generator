
import asyncio
import json
from typing import Set
from websockets import ServerConnection, serve
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError
from metrics.metric_output import MetricOutput
from metrics.metric import Metric


class MetricLoggerWS(MetricOutput):
    def __init__(self):
        super().__init__()
        self.clients: Set[ServerConnection] = set()
        self.server_task = None
        self._start_server()

    def _start_server(self):
        """Start the WebSocket server in a background task"""
        async def run_server():
            async with serve(self._handle_client, "localhost", 8766):
                print("✅ Metric WebSocket server running at ws://localhost:8766")
                await asyncio.Future()  # run forever

        # Start the server in a new event loop if one doesn't exist
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an event loop, create a task
                self.server_task = asyncio.create_task(run_server())
            else:
                # If no event loop is running, start one
                asyncio.run(run_server())
        except RuntimeError:
            # No event loop in current thread, create a new one
            self.server_task = asyncio.create_task(run_server())

    async def _handle_client(self, websocket: ServerConnection):
        """Handle new WebSocket client connections"""
        self.clients.add(websocket)
        print(f"Client connected. Total clients: {len(self.clients)}")

        try:
            # Keep connection alive
            async for message in websocket:
                pass  # We don't expect messages from clients
        except (ConnectionClosedOK, ConnectionClosedError):
            pass
        finally:
            self.clients.discard(websocket)
            print(f"Client disconnected. Total clients: {len(self.clients)}")

    async def _send_to_clients(self, metric: Metric):
        """Send metric to all connected clients"""
        if not self.clients:
            return

        # Convert metric to JSON-serializable format
        metric_data = {
            "timestamp": metric.ts.isoformat() if hasattr(metric, 'ts') else None,
            "buffer": metric.buf if hasattr(metric, 'buf') else None,
            "latency": metric.lat if hasattr(metric, 'lat') else None,
            "dropped": metric.drop if hasattr(metric, 'drop') else None,
            "anomaly": metric.anomaly if hasattr(metric, 'anomaly') else None
        }

        message = json.dumps(metric_data)

        # Send to all connected clients
        disconnected_clients = set()
        for client in self.clients:
            try:
                await client.send(message)
            except (ConnectionClosedOK, ConnectionClosedError):
                disconnected_clients.add(client)
            except Exception as e:
                print(f"Error sending to client: {e}")
                disconnected_clients.add(client)

        # Remove disconnected clients
        self.clients -= disconnected_clients

    def output(self, metric: Metric):
        """Send metric to all connected WebSocket clients"""
        # Schedule the async send operation
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're in an event loop, create a task
                asyncio.create_task(self._send_to_clients(metric))
            else:
                # If no event loop is running, we need to handle this differently
                # For now, we'll just print a warning
                print("Warning: No event loop running, cannot send metric via WebSocket")
        except RuntimeError:
            print("Warning: No event loop in current thread, cannot send metric via WebSocket")
