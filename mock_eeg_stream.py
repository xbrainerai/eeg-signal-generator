import asyncio, json, time, argparse, yaml
import numpy as np, websockets
from eeg_signal_utils import sine_wave, gauss_noise, spike_artifact
def load_config(path):
    if path:
        with open(path) as f: return yaml.safe_load(f)
    return {}
async def stream(cfg):
    rate      = cfg["rate"]
    channels  = cfg["channels"]
    freq      = cfg["freq"]
    mode      = cfg["mode"]
    interval  = 1.0 / rate
    uri       = f"ws://{cfg['host']}:{cfg['port']}"
    async with websockets.connect(uri) as ws:
        print(f"▶ Sending to {uri} …")
        t0 = time.time()
        while True:
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
            await ws.send(json.dumps(packet))
            await asyncio.sleep(interval)
def main():
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
    asyncio.run(stream(cfg))
if __name__ == "__main__":
    main()
