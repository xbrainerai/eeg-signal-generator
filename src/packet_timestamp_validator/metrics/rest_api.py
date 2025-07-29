import asyncio
import logging
import sys
from fastapi import FastAPI
from fastapi.responses import Response, JSONResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import os, yaml

from ..timestamp_validator import DefaultTimestampValidator
from .metrics_definitions import REGISTRY, setup_metrics, METRICS

app = FastAPI()

config_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "verification_config.yaml")
with open(config_path, "r") as f:
    config = yaml.safe_load(f)

setup_metrics()

cli_ch = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
cli_ch.setFormatter(formatter)
file_ch = logging.FileHandler("timestamp_validator.log")
file_ch.setFormatter(formatter)

logger = logging.getLogger("validator_api")
logger.setLevel(logging.DEBUG)
logger.addHandler(file_ch)
logger.addHandler(cli_ch)
logger.debug(f"Validator API started")
logger.debug(f"METRICS keys after setup = {list(METRICS.keys())}")
state = {
    "validator": DefaultTimestampValidator(config=config, metrics=METRICS.copy())
}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)

@app.get("/simulate")
async def simulate_stream():
    try:
        logger.debug("Simulating clean stream (no anomalies)")
        sampling_rate = config.get("sampling_rate", 250)
        delta_ms = int(1000 / sampling_rate)

        # ✅ Reset validator state before simulating new stream
        validator = state["validator"]
        validator.prev_ts = None
        validator.prev_seq = None
        validator.warn_count = 0
        validator.reset_count = 0

        for i in range(60):
            ts = i * delta_ms  # smooth stream, no jitter/regression/gap
            frame = {"timestamp": ts, "channel_id": "eeg1", "sequence_id": i}
            result = validator.validate(frame)
            logger.debug(f"Frame {i}: {result.status.name} ({result.reason})")
            await asyncio.sleep(0)

        return {"message": "Clean stream simulated"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/reset")
def reset_metrics():
    logger.debug("Clearing and rebuilding Prometheus metrics & validator")
    for collector in list(REGISTRY._collector_to_names.keys()):
        REGISTRY.unregister(collector)
    METRICS.clear()
    setup_metrics()
    state["validator"] = DefaultTimestampValidator(config=config, metrics=METRICS.copy())
    return {"message": "Validator and metrics reset"}
