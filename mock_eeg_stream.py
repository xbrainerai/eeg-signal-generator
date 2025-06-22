import tornado.ioloop
import tornado.web
import tornado.websocket
from tornado.options import options
import time
import numpy as np
from eeg_signal_utils import sine_wave, gauss_noise, spike_artifact
import tornado.web
import argparse, yaml, asyncio, time
from eeg_signal_utils import sine_wave, gauss_noise, spike_artifact
# from eeg_web_socket_handler import EegWebSocketHandler





def load_config(path):
    if path:
        with open(path) as f: return yaml.safe_load(f)
    return {}

ap = argparse.ArgumentParser()
ap.add_argument("--cfg", default="stream_config.yaml")
ap.add_argument("--channels", type=int)
ap.add_argument("--rate", type=int)
ap.add_argument("--mode", choices=["sine","noise","mixed"])
args = vars(ap.parse_args())
cfg = {"host":"localhost","port":8765,"channels":8,"rate":256,"freq":10,"mode":"mixed","artifacts":True}
cfg.update(load_config(args["cfg"]))
cfg.update({k:v for k,v in args.items() if v})
print("Config:", cfg)

rate      = cfg["rate"]
channels  = cfg["channels"]
freq      = cfg["freq"]
mode      = cfg["mode"]
interval  = 1.0 / rate
uri       = f"ws://{cfg['host']}:{cfg['port']}"
t0 = time.time()

class EegWebSocketHandler(tornado.websocket.WebSocketHandler):

    def open(self, *args, **kwargs):
        print("open success")
        self.t0 = time.time()
        self.timer = tornado.ioloop.PeriodicCallback(self.send_data, 1000/rate)
        self.timer.start()

    def on_close(self):
        self.timer.stop()

    def send_data(self):
        t = time.time() - t0
        base = sine_wave(freq + np.random.uniform(-0.3,0.3), t)
        noise = gauss_noise(channels, 0.2)
        spike = spike_artifact(channels) if cfg["artifacts"] and int(t*1000)%2000<50 else 0
        if mode == "sine":     payload = np.full(channels, base)
        elif mode == "noise":  payload = noise
        elif mode == "mixed":  payload = base + noise + spike
        packet = {
            "timestamp": time.time(),
            "sampling_rate": rate,
            "channel_count": channels,
            "channels": payload.tolist(), # type: ignore
            "mode": mode
        }
        self.write_message(packet)

    def on_message(self, message):
        print(message)

async def start_web_socket():
    port = cfg['port']
    application = tornado.web.Application([(r'/', EegWebSocketHandler)])
    application.listen(port)
    print(f'Mock EEG stream running at ws://localhost:{port}')
    tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
    asyncio.run(start_web_socket())
    # port = cfg['port']
    # application = tornado.web.Application([(r'/', EegWebSocketHandler)])
    # application.listen(port)
    # print(f'Mock EEG stream running at ws://localhost:{port}')
    # tornado.ioloop.IOLoop.instance().start()
