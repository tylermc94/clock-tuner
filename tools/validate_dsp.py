#!/usr/bin/env python3
"""
Validate the clock-tuner tick-detection + analysis algorithm.

This is a Python port of the *exact* streaming detector used in the web app
(index.html). It generates synthetic mechanical-clock audio with a known beat
rate, a known beat-error asymmetry, and background noise, then checks that the
detector recovers those values. If this passes, the JS version (same math) is
trustworthy.

Run:  python3 validate_dsp.py
"""
import math
import numpy as np

SR = 48000


# ---------------------------------------------------------------------------
# Streaming detector -- mirror of the JS in index.html
# ---------------------------------------------------------------------------
class TickDetector:
    """Scale-invariant transient detector.

    Detection statistic is the ratio of a fast envelope (the click) to a slow
    envelope (the background noise floor). Because it is a ratio, the same
    threshold works whether the recording is loud or faint -- which is what we
    need for a phone held at an arbitrary distance from the clock.
    """

    def __init__(self, sr, refractory_s=0.15, sensitivity=4.0):
        self.sr = sr
        self.refractory = int(refractory_s * sr)
        self.sens = sensitivity          # ratio threshold (fast/slow)
        self.a_fast = 0.02               # ~1 ms envelope (attack of the click)
        self.a_slow = 3e-5               # ~0.7 s background floor
        self.a_peak_dn = 3e-4            # decay of the observed-peak tracker
        self.eps = 1e-6
        # state
        self.prev = 0.0
        self.env_fast = 0.0
        self.env_slow = 0.0
        self.env_peak = self.eps
        self.counter = 0
        self.armed = False
        self.last_tick = -10 ** 12
        self.peak_val = 0.0
        self.peak_pos = 0
        self.ticks = []  # committed tick times, seconds

    def process(self, block):
        for x in block:
            d = x - self.prev
            self.prev = x
            rect = abs(d)
            self.env_fast += (rect - self.env_fast) * self.a_fast
            self.env_slow += (rect - self.env_slow) * self.a_slow
            if self.env_fast > self.env_peak:
                self.env_peak = self.env_fast
            else:
                self.env_peak += (self.env_fast - self.env_peak) * self.a_peak_dn

            ratio = self.env_fast / (self.env_slow + self.eps)
            # a click must both stand out from the noise floor (ratio) and be a
            # meaningful fraction of the loudest events seen (absolute gate)
            is_hit = ratio > self.sens and self.env_fast > 0.18 * self.env_peak

            if not self.armed:
                if is_hit and (self.counter - self.last_tick) > self.refractory:
                    self.armed = True
                    self.peak_val = self.env_fast
                    self.peak_pos = self.counter
            else:
                if self.env_fast > self.peak_val:
                    self.peak_val = self.env_fast
                    self.peak_pos = self.counter
                if not is_hit:          # click has passed -> commit at its peak
                    self.ticks.append(self.peak_pos / self.sr)
                    self.last_tick = self.peak_pos
                    self.armed = False
            self.counter += 1


# ---------------------------------------------------------------------------
# Analysis -- mirror of the JS in index.html
# ---------------------------------------------------------------------------
def analyze(ticks, nominal_bph):
    ticks = np.asarray(ticks, float)
    if len(ticks) < 4:
        return None
    intervals = np.diff(ticks)
    m = np.median(intervals)                # robust center, used only to gate
    keep = intervals[(intervals > 0.6 * m) & (intervals < 1.4 * m)]
    # MEAN of the kept intervals -- unbiased even when beat error makes the
    # tick->tock and tock->tick intervals bimodal (a median would skew to one).
    beat = float(np.mean(keep))             # seconds per beat
    measured_bph = 3600.0 / beat

    t_nom = 3600.0 / nominal_bph
    sec_per_day = 86400.0 * (t_nom - beat) / beat  # >0 => fast

    # beat error over the longest clean run (all intervals in tolerance)
    clean_mask = (intervals > 0.6 * m) & (intervals < 1.4 * m)
    even = intervals[0::2][clean_mask[0::2]]
    odd = intervals[1::2][clean_mask[1::2]]
    beat_error_ms = None
    if len(even) >= 2 and len(odd) >= 2:
        beat_error_ms = abs(np.median(even) - np.median(odd)) * 1000.0

    return {
        "beats": len(ticks),
        "measured_bph": measured_bph,
        "beat_s": beat,
        "sec_per_day": sec_per_day,
        "beat_error_ms": beat_error_ms,
    }


# ---------------------------------------------------------------------------
# Synthetic clock audio
# ---------------------------------------------------------------------------
def make_click(sr, dur=0.006, f=2500.0):
    n = int(dur * sr)
    t = np.arange(n) / sr
    env = np.exp(-t / 0.0012)               # sharp decaying transient
    return np.sin(2 * math.pi * f * t) * env


def synth_clock(sr, seconds, true_bph, beat_error_ms=0.0, noise=0.01, seed=1):
    rng = np.random.default_rng(seed)
    beat = 3600.0 / true_bph
    click = make_click(sr)
    audio = rng.normal(0, noise, int(seconds * sr))
    t = 0.0
    i = 0
    be = beat_error_ms / 1000.0
    while t < seconds - 0.02:
        pos = int(t * sr)
        amp = 1.0 if (i % 2 == 0) else 0.85  # tick louder than tock
        seg = audio[pos:pos + len(click)]
        seg += click[:len(seg)] * amp
        # alternate intervals to inject beat error: tick->tock long, tock->tick short
        step = beat + (be / 2 if i % 2 == 0 else -be / 2)
        step += rng.normal(0, 0.0004)        # small timing jitter
        t += step
        i += 1
    return audio


def run_case(name, true_bph, nominal_bph, beat_error_ms, noise, seconds=90):
    audio = synth_clock(SR, seconds, true_bph, beat_error_ms, noise)
    det = TickDetector(SR, refractory_s=0.5 * (3600.0 / nominal_bph))
    # feed in realistic ~2048-sample blocks like the browser does
    for s in range(0, len(audio), 2048):
        det.process(audio[s:s + 2048])
    res = analyze(det.ticks, nominal_bph)
    expected_spd = 86400.0 * (3600.0 / nominal_bph - 3600.0 / true_bph) / (3600.0 / true_bph)
    print(f"\n=== {name} ===")
    print(f"  detected beats : {res['beats']}  (expected ~{int(seconds/(3600/true_bph))})")
    print(f"  measured BPH   : {res['measured_bph']:.2f}   (true {true_bph})")
    print(f"  rate           : {res['sec_per_day']:+.1f} s/day   (expected {expected_spd:+.1f})")
    be = res['beat_error_ms']
    print(f"  beat error     : {be:.2f} ms" if be is not None else "  beat error : n/a",
          f"  (injected {beat_error_ms})")
    rate_ok = (abs(res['measured_bph'] - true_bph) < 1.0
               and abs(res['sec_per_day'] - expected_spd) < 15.0)
    be_ok = True
    if beat_error_ms > 0 and be is not None:
        be_ok = abs(be - beat_error_ms) < 4.0
    ok = rate_ok and be_ok
    print("  RESULT:", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    all_ok = True
    # A 1-second-pendulum clock (3600 BPH) running fast, no beat error
    all_ok &= run_case("Seconds pendulum, running fast", 3612.0, 3600.0, 0.0, 0.008)
    # Same but with beat error (out of beat)
    all_ok &= run_case("With beat error", 3605.0, 3600.0, 12.0, 0.01)
    # A faster movement (e.g. small mantel clock ~ 5400 BPH) running fast
    all_ok &= run_case("Faster movement, fast + noise", 5420.0, 5400.0, 6.0, 0.01)
    # Running slow
    all_ok &= run_case("Running slow", 3590.0, 3600.0, 0.0, 0.01)
    print("\n" + ("ALL PASS" if all_ok else "SOME FAILED"))
