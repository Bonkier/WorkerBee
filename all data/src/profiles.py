import random
import threading

PROFILES = {
    "SAFE": {
        "mouse_velocity":      0.58,
        "noise":               3.2,
        "arc_strength":        0.12,
        "overshoot_prob":      0.10,
        "variance":            0.12,
        "endpoint_jitter_px":  6,
        "move_duration":       (0.07, 0.16),
        "step_delay_jitter":   (0.90, 1.15),
        "lognorm_pre_move_mu":  -3.5,
        "lognorm_pre_move_sig":  0.30,
        "lognorm_pre_click_mu": -3.2,
        "lognorm_pre_click_sig": 0.30,
        "rhythm_every":        (7, 12),
        "rhythm_pause":        (0.06, 0.20),
        "neutral_drift_px":    3,
        "neutral_drift_chance": 0.35,
    },
    "FAST": {
        "mouse_velocity":      0.78,
        "noise":               2.0,
        "arc_strength":        0.07,
        "overshoot_prob":      0.05,
        "variance":            0.08,
        "endpoint_jitter_px":  4,
        "move_duration":       (0.04, 0.10),
        "step_delay_jitter":   (0.92, 1.08),
        "lognorm_pre_move_mu":  -3.8,
        "lognorm_pre_move_sig":  0.25,
        "lognorm_pre_click_mu": -3.5,
        "lognorm_pre_click_sig": 0.25,
        "rhythm_every":        (10, 16),
        "rhythm_pause":        (0.04, 0.12),
        "neutral_drift_px":    2,
        "neutral_drift_chance": 0.25,
    },
    "CHAOTIC": {
        "mouse_velocity":      0.50,
        "noise":               4.2,
        "arc_strength":        0.20,
        "overshoot_prob":      0.20,
        "variance":            0.18,
        "endpoint_jitter_px":  9,
        "move_duration":       (0.09, 0.22),
        "step_delay_jitter":   (0.80, 1.25),
        "lognorm_pre_move_mu":  -3.0,
        "lognorm_pre_move_sig":  0.35,
        "lognorm_pre_click_mu": -2.8,
        "lognorm_pre_click_sig": 0.40,
        "rhythm_every":        (5, 10),
        "rhythm_pause":        (0.08, 0.30),
        "neutral_drift_px":    5,
        "neutral_drift_chance": 0.50,
    },
}

_DEFAULT = "SAFE"
_rhythm_lock = threading.Lock()
_rhythm_counter = 0
_rhythm_next = random.randint(*PROFILES[_DEFAULT]["rhythm_every"])

def get_profile(name=None):
    try:
        import shared_vars
        key = (name or getattr(shared_vars, "macro_profile", _DEFAULT)).upper()
    except Exception:
        key = _DEFAULT
    return PROFILES.get(key, PROFILES[_DEFAULT])

def rhythm_tick():
    global _rhythm_counter, _rhythm_next
    profile = get_profile()

    with _rhythm_lock:
        _rhythm_counter += 1
        if _rhythm_counter < _rhythm_next:
            return 0.0, (0, 0)
        _rhythm_counter = 0
        lo, hi = profile["rhythm_every"]
        _rhythm_next = random.randint(lo, hi)

    pause_lo, pause_hi = profile["rhythm_pause"]
    pause = random.uniform(pause_lo, pause_hi)

    drift = (0, 0)
    if random.random() < profile["neutral_drift_chance"]:
        d = profile["neutral_drift_px"]
        drift = (random.randint(-d, d), random.randint(-d, d))

    return pause, drift
