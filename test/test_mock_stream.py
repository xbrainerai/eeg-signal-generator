import asyncio, json, os, websockets, pytest, subprocess, sys, time

@pytest.mark.asyncio
async def test_first_packet():
    proc = subprocess.Popen([sys.executable, "-m", "src.mock_eeg_stream"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    await asyncio.sleep(1)
    async with websockets.connect("ws://localhost:8765") as ws:
        msg = await ws.recv()
        pkt = json.loads(msg)
        assert "ts" in pkt and "data" in pkt
    proc.terminate()
