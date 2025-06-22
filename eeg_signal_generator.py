import time
import numpy as np
import tornado
from eeg_signal_utils import sine_wave, gauss_noise, spike_artifact

class EegSignalGenerator:
    def __init__(self, freq, channels, artifacts, mode, rate):
        self.server_actions = []
        self.freq = freq
        self.channels = channels
        self.artifacts = artifacts
        self.mode = mode
        self.rate = rate

    def start_generating_signals(self, server_output):
        t0 = time.time()
        timer = tornado.ioloop.PeriodicCallback(lambda: self.generate_signal(server_output, t0), 1000/self.rate)
        timer.start()

        return timer

    def generate_signal(self, server_output, t0):
        t = time.time() - t0
        base = sine_wave(self.freq + np.random.uniform(-0.3,0.3), t)
        noise = gauss_noise(self.channels, 0.2)
        spike = spike_artifact(self.channels) if self.artifacts and int(t*1000)%2000<50 else 0
        if self.mode == "sine":     payload = np.full(self.channels, base)
        elif self.mode == "noise":  payload = noise
        elif self.mode == "mixed":  payload = base + noise + spike
        packet = {
            "timestamp": time.time(),
            "sampling_rate": self.rate,
            "channel_count": self.channels,
            "channels": payload.tolist(), # type: ignore
            "mode": self.mode
        }

        server_output(packet)
