from fastapi import FastAPI
from eeg_signal_utils import sine_wave, gauss_noise
import numpy as np, time
app = FastAPI()
@app.get("/snapshot")
def snap():
    t = time.time()
    payload = sine_wave(10, t)+gauss_noise(8,0.1)
    return {"ts":t,"channels":payload.tolist()}
