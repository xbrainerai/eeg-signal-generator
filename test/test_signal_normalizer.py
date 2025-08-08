import json, subprocess, sys, tempfile, time, os, asyncio, websockets, threading

def test_normalizer_smoke(tmp_path):
    # Start mock server
    mock = subprocess.Popen([sys.executable,"-m","src.mock_eeg_stream"])
    time.sleep(1)
    # Start adapter and pipe into normalizer
    adapter = subprocess.Popen([sys.executable,"-m","src.ingestion_adapter"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    norm = subprocess.Popen([sys.executable, "-m", "src.signal_normalizer"],
                            stdin=adapter.stdout, stdout=subprocess.PIPE, text=True)
    if norm.stdout is not None:
        line = norm.stdout.readline()
        frame = json.loads(line)
        assert frame["rate"] >= 256
    else:
        raise RuntimeError("Failed to capture stdout from signal_normalizer process")
    adapter.terminate()
    norm.terminate()
    mock.terminate()
