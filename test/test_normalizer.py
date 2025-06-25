# tests/test_normalizer.py
"""
Unit tests for signal_normalizer.py
Run with:  pytest -q
"""

import json
from pathlib import Path

import numpy as np
import pytest
import sys
import os
# Import the functions directly from the source module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.signal_normalizer import dc_offset, process_window

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def toy_window():
    """
    Returns a tiny 4-sample × 2-channel window with a known DC component.
    Channel-0 baseline = 10 µV, Channel-1 baseline = -5 µV.
    """
    mu_v = np.array([
        [12.0, -3.0],
        [ 8.0, -7.0],
        [11.0, -6.0],
        [ 9.0, -4.0],
    ]) * 1e-6   # convert to Volts so it matches pipeline units
    return mu_v

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_dc_offset_removal(toy_window):
    """
    After dc_offset(), each channel mean should be ~0.
    """
    adjusted = dc_offset(toy_window)
    col_means = np.mean(adjusted, axis=0)
    assert np.allclose(col_means, [0.0, 0.0], atol=1e-9), col_means


def test_process_window_output_structure(toy_window, tmp_path: Path):
    """
    process_window() must return JSON with mandatory keys.
    """
    json_str = process_window(
        win=toy_window,
        rate=256,
        seq=42,
        t0="2025-06-22T00:00:00Z",
        t1="2025-06-22T00:00:00.250Z",
    )
    frame = json.loads(json_str)

    # Required keys
    for key in ("ts_start", "ts_end", "frame_seq", "rate", "channels", "data"):
        assert key in frame, f"Missing key {key}"

    # Frame sequence and rate should match input
    assert frame["frame_seq"] == 42
    assert frame["rate"] == 256

    # Channels list length should match data's inner length
    assert len(frame["channels"]) == len(frame["data"][0])

    # Data shape must equal toy_window shape
    assert len(frame["data"]) == toy_window.shape[0]
    assert len(frame["data"][0]) == toy_window.shape[1]
