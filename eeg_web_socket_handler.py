import time
import tornado
import numpy as np
import tornado.websocket
from eeg_signal_generator import EegSignalGenerator
from eeg_signal_utils import sine_wave, gauss_noise, spike_artifact

class EegWebSocketHandler(tornado.websocket.WebSocketHandler):

    def initialize(self, port: int, eeg_signal_generator: EegSignalGenerator):
        self.port = port
        self.eeg_signal_generator = eeg_signal_generator

    def open(self, *args, **kwargs):
        print("open success")
        self.t0 = time.time()
        self.timer = self.eeg_signal_generator.start_generating_signals(self.send_data)

    def on_close(self):
        self.timer.stop()

    def send_data(self, packet):
        self.write_message(packet)

    def on_message(self, message):
        pass
