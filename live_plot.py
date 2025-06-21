import matplotlib.pyplot as plt, numpy as np, asyncio, websockets, json
plt.ion(); fig,ax=plt.subplots(); line,=ax.plot(np.zeros(200))
async def stream():
    ys = np.zeros(200)
    async with websockets.connect("ws://localhost:8765") as ws:
        while True:
            pkt=json.loads(await ws.recv()); ys=np.roll(ys,-1); ys[-1]=pkt["channels"][0]
            line.set_ydata(ys); ax.relim(); ax.autoscale_view(); plt.pause(0.001)
asyncio.run(stream())
