import math
import time
import statistics
import threading
from collections import deque
from pynput import mouse

SAMPLE_GAP = 0.01
MIN_POINTS = 10
VELOCITY_VARIANCE_THRESHOLD = 200
ANGULAR_VARIANCE_THRESHOLD = 0.15
FITTS_R2_THRESHOLD = 0.92
OVERSHOOT_RATIO_THRESHOLD = 0.08
LOG_NORMAL_CHI_THRESHOLD = 0.25

_trace = []
_click_delays = []
_last_move_time = [0.0]
_last_pos = [None]
_move_end_time = [0.0]
_recording = [False]


def _dist(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _velocity_profile(pts):
    speeds = []
    for i in range(1, len(pts)):
        dx = pts[i][0] - pts[i-1][0]
        dy = pts[i][1] - pts[i-1][1]
        dt = pts[i][2] - pts[i-1][2]
        if dt > 0:
            speeds.append(math.hypot(dx, dy) / dt)
    return speeds


def _angular_variance(pts):
    angles = []
    for i in range(1, len(pts) - 1):
        ax = pts[i][0] - pts[i-1][0]
        ay = pts[i][1] - pts[i-1][1]
        bx = pts[i+1][0] - pts[i][0]
        by = pts[i+1][1] - pts[i][1]
        if math.hypot(ax, ay) < 1 or math.hypot(bx, by) < 1:
            continue
        dot = ax * bx + ay * by
        mag = math.hypot(ax, ay) * math.hypot(bx, by)
        cos_a = max(-1, min(1, dot / mag))
        angles.append(math.acos(cos_a))
    return statistics.variance(angles) if len(angles) > 2 else 0.0


def _straightness(pts):
    if len(pts) < 2:
        return 1.0
    direct = _dist(pts[0], pts[-1])
    total = sum(_dist(pts[i], pts[i+1]) for i in range(len(pts) - 1))
    return direct / total if total > 0 else 1.0


def _overshoot_ratio(pts, target):
    tx, ty = target
    max_d = max(_dist(p, (tx, ty)) for p in pts)
    final_d = _dist(pts[-1], (tx, ty))
    direct = _dist(pts[0], (tx, ty))
    if direct < 5:
        return 0.0
    return (max_d - final_d) / direct


def _log_normal_score(delays):
    if len(delays) < 5:
        return 0.5
    log_vals = [math.log(d) for d in delays if d > 0]
    mean = statistics.mean(log_vals)
    std = statistics.stdev(log_vals)
    expected_mean = -2.8
    expected_std = 0.35
    mean_dev = abs(mean - expected_mean)
    std_dev = abs(std - expected_std)
    score = 1.0 - min(1.0, mean_dev / 1.5 + std_dev / 1.0)
    return score


def _bell_curve_score(speeds):
    if len(speeds) < 5:
        return 0.0
    n = len(speeds)
    peak_i = speeds.index(max(speeds))
    peak_ratio = peak_i / n
    symmetry = 1.0 - abs(peak_ratio - 0.5) * 2
    return symmetry


def score_trace(pts, click_delay, target):
    if len(pts) < MIN_POINTS:
        return None

    report = {}

    speeds = _velocity_profile(pts)
    vel_var = statistics.variance(speeds) if len(speeds) > 2 else 0
    report["velocity_variance"] = vel_var
    report["vel_bell_curve"] = _bell_curve_score(speeds)

    ang_var = _angular_variance(pts)
    report["angular_variance"] = ang_var

    straight = _straightness(pts)
    report["straightness"] = straight

    overshoot = _overshoot_ratio(pts, target)
    report["overshoot"] = overshoot

    report["click_delay_ms"] = click_delay * 1000

    human_score = 0.0
    human_score += min(1.0, vel_var / VELOCITY_VARIANCE_THRESHOLD) * 0.25
    human_score += report["vel_bell_curve"] * 0.20
    human_score += min(1.0, ang_var / ANGULAR_VARIANCE_THRESHOLD) * 0.20
    human_score += (1.0 - straight) * 0.15
    human_score += min(1.0, overshoot / OVERSHOOT_RATIO_THRESHOLD) * 0.15
    delay_score = 1.0 if 0.04 < click_delay < 0.25 else 0.0
    human_score += delay_score * 0.05

    report["human_score"] = round(human_score, 3)
    report["verdict"] = "HUMAN" if human_score > 0.55 else ("AMBIGUOUS" if human_score > 0.35 else "BOT")
    return report


_move_start_pos = [None]
_click_target = [None]


def _on_move(x, y):
    now = time.time()
    if _move_start_pos[0] is None:
        _move_start_pos[0] = (x, y)
    _trace.append((x, y, now))
    _last_move_time[0] = now
    _last_pos[0] = (x, y)


def _on_click(x, y, button, pressed):
    if button != mouse.Button.left:
        return
    if pressed:
        _move_end_time[0] = time.time()
        _click_target[0] = (x, y)
    else:
        hold_duration = time.time() - _move_end_time[0]
        trace_copy = list(_trace)
        target = _click_target[0] or (x, y)

        _trace.clear()
        _move_start_pos[0] = None

        if len(trace_copy) >= MIN_POINTS:
            report = score_trace(trace_copy, hold_duration, target)
            if report:
                _print_report(report)


def _print_report(r):
    print("\n--- Movement Analysis ---")
    print(f"  Verdict         : {r['verdict']}")
    print(f"  Human score     : {r['human_score']:.3f}  (>0.55 = human, <0.35 = bot)")
    print(f"  Velocity var    : {r['velocity_variance']:.1f}  (low = linear = bot)")
    print(f"  Bell curve fit  : {r['vel_bell_curve']:.3f}  (1.0 = perfect human speed arc)")
    print(f"  Angular var     : {r['angular_variance']:.4f}  (low = too straight = bot)")
    print(f"  Straightness    : {r['straightness']:.4f}  (1.0 = perfectly straight = bot)")
    print(f"  Overshoot       : {r['overshoot']:.4f}  (0 = no overshoot = suspicious)")
    print(f"  Click hold (ms) : {r['click_delay_ms']:.1f}")
    print("-------------------------")


def run_session_analysis(n_movements=30):
    print(f"Recording {n_movements} movements. Click anywhere to analyze each one. Ctrl+C to stop.")
    count = [0]

    def on_click_counted(x, y, button, pressed):
        if button == mouse.Button.left and not pressed:
            count[0] += 1
            if count[0] >= n_movements:
                return False

    listener = mouse.Listener(on_move=_on_move, on_click=_on_click)
    listener.start()
    try:
        while count[0] < n_movements:
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        listener.stop()
    print(f"\nSession complete. {count[0]} movements analyzed.")


if __name__ == "__main__":
    run_session_analysis(n_movements=20)
