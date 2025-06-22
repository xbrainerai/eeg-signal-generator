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
from eeg_web_socket_handler import EegWebSocketHandler
from eeg_signal_generator import EegSignalGenerator
from eeg_tcp_server import EegTcpServer

def load_config(path):
    if path:
        with open(path) as f: return yaml.safe_load(f)
    return {}

ap = argparse.ArgumentParser()
ap.add_argument("--cfg", default="stream_config.yaml")
ap.add_argument("--channels", type=int)
ap.add_argument("--rate", type=int)
ap.add_argument("--mode", choices=["sine","noise","mixed"])
ap.add_argument("--ws_port", type=int, default=8765)
ap.add_argument("--tcp_port", type=int, default=8766)

args = vars(ap.parse_args())
cfg = {"host":"localhost","ws_port":8765,"tcp_port":8766,"channels":8,"rate":256,"freq":10,"mode":"mixed","artifacts":True}
cfg.update(load_config(args["cfg"]))
cfg.update({k:v for k,v in args.items() if v})

rate      = cfg['rate']
channels  = cfg['channels']
freq      = cfg['freq']
mode      = cfg['mode']
artifacts = cfg['artifacts']
interval  = 1.0 / rate
ws_port = cfg['ws_port']
tcp_port = cfg['tcp_port']
uri       = f"ws://{cfg['host']}:{ws_port}"
t0 = time.time()
signal_generator = EegSignalGenerator(freq, channels, artifacts, mode, rate)

if __name__ == "__main__":
    if ws_port == tcp_port:
        raise argparse.ArgumentError(None, message="TCP port and WebSocket port must be different")

    web_socket_server = tornado.web.Application([(r'/', EegWebSocketHandler, {'port': ws_port, 'eeg_signal_generator': signal_generator })])
    web_socket_server.listen(ws_port)
    print(f'Mock EEG WebSocket stream running at ws://localhost:{ws_port}')

    tcp_server = EegTcpServer(signal_generator)
    tcp_server.listen(tcp_port)
    print(f'Mock EEG TCP stream running at localhost:{tcp_port}')

    tornado.ioloop.IOLoop.current().start()
