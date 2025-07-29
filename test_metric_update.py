from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST, CollectorRegistry
from fastapi import FastAPI
from fastapi.responses import Response
import uvicorn

# Shared registry and metrics
REGISTRY = CollectorRegistry()

test_counter = Counter("test_counter", "Just a test counter", registry=REGISTRY)
test_gauge = Gauge("test_gauge", "Test gauge", registry=REGISTRY)

# FastAPI app
app = FastAPI()

@app.get("/metrics")
def metrics():
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)

@app.get("/update")
def update():
    test_counter.inc()
    test_gauge.set(42)
    return {"message": "Updated metrics"}
