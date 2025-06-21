import numpy as np
def sine_wave(freq, t):            # pure sine
    return np.sin(2 * np.pi * freq * t)
def gauss_noise(ch, sigma=0.1):    # white noise
    return np.random.normal(0, sigma, ch)
def spike_artifact(ch, magnitude=1.5):
    spike = np.zeros(ch)
    spike[np.random.randint(0, ch)] = magnitude
    return spike
