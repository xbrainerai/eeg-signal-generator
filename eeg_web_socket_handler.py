import time
import tornado
import numpy as np
import tornado.websocket
from eeg_signal_utils import sine_wave, gauss_noise, spike_artifact

class EegWebSocketHandler(tornado.websocket.WebSocketHandler):

    def initialize(self, port, freq, channels, artifacts, mode, rate):
        self.port = port
        self.freq = freq
        self.channels = channels
        self.artifacts = artifacts
        self.mode = mode
        self.rate = rate

    def open(self, *args, **kwargs):
        print("open success")
        self.t0 = time.time()
        self.timer = tornado.ioloop.PeriodicCallback(self.send_data, 1000/self.rate)
        self.timer.start()

    def on_close(self):
        self.timer.stop()

    def send_data(self):
        t = time.time() - self.t0
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

        self.write_message(packet)

    def on_message(self, message):
        pass
