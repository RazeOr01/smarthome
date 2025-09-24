#!/usr/bin/env python3
import os
import re
import time
import random
import uuid
import subprocess
from typing import Optional, Dict, Any

import requests
from urllib3.util import Retry
from requests.adapters import HTTPAdapter

CLOUD_HOST = os.getenv("CLOUD_HOST", "www.cesieat.ovh")
BASE_URL = f"https://{CLOUD_HOST}"
VERIFY_TLS = os.getenv("VERIFY_TLS", "true").lower() != "false"
API_KEY = os.getenv("API_KEY")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "5"))

BACKEND = os.getenv("BACKEND", "mixed").lower()
MIXED_MATTER_RATIO = float(os.getenv("MIXED_MATTER_RATIO", "0.3"))
MIXED_STRICT_ALTERNATE = os.getenv("MIXED_STRICT_ALTERNATE", "false").lower() == "true"

CHIP_TOOL = os.getenv("CHIP_TOOL", "/opt/chip/chip-tool")
NODE_ID   = os.getenv("NODE_ID", "1")
ENDPOINT  = os.getenv("ENDPOINT", "3")

ACTIVE_RATIO = float(os.getenv("ACTIVE_RATIO", "0.11"))
IDLE_SLEEP_RANGE = (
    int(os.getenv("IDLE_SLEEP_MIN", "60")),
    int(os.getenv("IDLE_SLEEP_MAX", "300")),
)
CYCLE_SLEEP = float(os.getenv("CYCLE_SLEEP", "1"))

PARTY_STEPS_RANGE = (
    int(os.getenv("PARTY_STEPS_MIN", "5")),
    int(os.getenv("PARTY_STEPS_MAX", "15")),
)
PARTY_WAIT_RANGE = (
    float(os.getenv("PARTY_WAIT_MIN", "0.4")),
    float(os.getenv("PARTY_WAIT_MAX", "1.5")),
)

ONE_SHOT = os.getenv("ONE_SHOT", "false").lower() == "true"

THEMES = {
    "party":   ["#FF0040", "#FF8000", "#FFD300", "#00E5FF", "#7D00FF", "#00FF85"],
    "neon":    ["#39FF14", "#FF073A", "#0FF0FC", "#FE53BB", "#F5F500"],
    "ocean":   ["#003F5C", "#2F4B7C", "#00B5C7", "#2EC4B6", "#A3EFFF"],
    "sunset":  ["#FF4500", "#FF7F50", "#FDB813", "#FF1493", "#8B00FF"],
    "forest":  ["#0B6623", "#2D6A4F", "#40916C", "#95D5B2", "#74C69D"],
    "pastel":  ["#FFADAD", "#FFD6A5", "#FDFFB6", "#CAFFBF", "#A0C4FF", "#BDB2FF"],
    "halloween": ["#FF7518", "#000000", "#6A0DAD", "#9B870C", "#8A0303"],
    "xmas":    ["#FF0000", "#008000", "#FFFFFF", "#006400", "#C41E3A"],
}

session = requests.Session()
retries = Retry(
    total=3,
    backoff_factor=0.25,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods={"GET", "PATCH"},
)
session.mount("https://", HTTPAdapter(max_retries=retries))

def _headers(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    h = {"Content-Type": "application/json"}
    if API_KEY:
        h["X-API-Key"] = API_KEY
    if extra:
        h.update(extra)
    return h

def get_status() -> Dict[str, Any]:
    r = session.get(f"{BASE_URL}/cloud", verify=VERIFY_TLS, timeout=REQUEST_TIMEOUT, headers=_headers())
    r.raise_for_status()
    data = r.json()
    print(f"[STATUS] enabled={data.get('enabled')} brightness={data.get('brightness')} color={data.get('color')}")
    return data

def patch_cloud(enabled: Optional[bool] = None,
                brightness: Optional[int] = None,
                color: Optional[str] = None,
                idempotency_key: Optional[str] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    if enabled is not None:
        payload["enabled"] = bool(enabled)
    if brightness is not None:
        payload["brightness"] = int(brightness)
    if color is not None:
        color = color.upper()
        if not (isinstance(color, str) and len(color) == 7 and color.startswith('#')):
            raise ValueError("color must be in format #RRGGBB")
        payload["color"] = color

    if not payload:
        return {"noop": True}

    headers = _headers({})
    if idempotency_key is None:
        idempotency_key = str(uuid.uuid4())
    headers["Idempotency-Key"] = idempotency_key

    r = session.patch(f"{BASE_URL}/cloud", json=payload, verify=VERIFY_TLS, timeout=REQUEST_TIMEOUT, headers=headers)
    r.raise_for_status()
    data = r.json()
    print(f"[PATCH] payload={payload} → applied={data.get('applied')}")
    return data

class MatterError(RuntimeError):
    pass

def _run_chiptool(args: list[str], timeout: float = 6.0) -> str:
    cmd = [CHIP_TOOL] + args
    print(f"[MATTER] $ {' '.join(cmd)}")
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise MatterError(f"chip-tool introuvable à {CHIP_TOOL}")
    except subprocess.TimeoutExpired:
        raise MatterError("chip-tool timeout")

    if cp.returncode != 0:
        out = (cp.stdout or "") + (cp.stderr or "")
        raise MatterError(f"chip-tool failed (rc={cp.returncode}):\n{out}")
    return cp.stdout or ""

def _matter_on() -> None:
    _run_chiptool(["onoff", "on", NODE_ID, ENDPOINT])

def _matter_off() -> None:
    _run_chiptool(["onoff", "off", NODE_ID, ENDPOINT])

def _matter_set_brightness_0_100(level_percent: int) -> None:
    lvl_254 = int(round(max(0, min(100, level_percent)) * 254 / 100))
    _run_chiptool([
        "levelcontrol", "move-to-level-with-on-off",
        str(lvl_254), "0", "0", "0", NODE_ID, ENDPOINT
    ])

_last_backend = ["cloud"]

def _pick_backend(for_capability: str) -> str:
    if for_capability == "color":
        return "cloud"

    if BACKEND == "mixed":
        if MIXED_STRICT_ALTERNATE:
            _last_backend[0] = "matter" if _last_backend[0] == "cloud" else "cloud"
            return _last_backend[0]
        return "matter" if random.random() < MIXED_MATTER_RATIO else "cloud"

    return BACKEND

def turn_on():
    backend = _pick_backend("onoff")
    print(f"[ACTION] Turning ON via {backend.upper()}")
    if backend == "cloud":
        patch_cloud(enabled=True)
    else:
        _matter_on()

def turn_off():
    backend = _pick_backend("onoff")
    print(f"[ACTION] Turning OFF via {backend.upper()}")
    if backend == "cloud":
        patch_cloud(enabled=False)
    else:
        _matter_off()

def increase_brightness(cur: Optional[int] = None):
    if cur is None:
        cur = int(get_status().get("brightness", 0))
    if cur < 100:
        inc = random.randint(10, 30)
        new_val = min(100, cur + inc)
        set_brightness(new_val)
    else:
        print("[SKIP] Brightness already at 100%")

def decrease_brightness(cur: Optional[int] = None):
    if cur is None:
        cur = int(get_status().get("brightness", 0))
    if cur > 0:
        dec = random.randint(10, 30)
        new_val = max(0, cur - dec)
        set_brightness(new_val)
    else:
        print("[SKIP] Brightness already at 0%")

def set_brightness(level_percent: int):
    level_percent = max(0, min(100, int(level_percent)))
    backend = _pick_backend("brightness")
    print(f"[ACTION] Set brightness {level_percent}% via {backend.upper()}")
    if backend == "cloud":
        patch_cloud(brightness=level_percent)
    else:
        _matter_set_brightness_0_100(level_percent)

def set_color(hex_color: str):
    hex_color = hex_color.upper()
    print(f"[ACTION] Setting color to {hex_color} via CLOUD")
    patch_cloud(color=hex_color)

def change_color(theme: str = "party"):
    state = get_status()
    if not state.get("enabled"):
        print("[INFO] Bulb is OFF, turning on for color change.")
        turn_on()
    palette = THEMES.get(theme.lower(), THEMES["party"])
    chosen = random.choice(palette)
    print(f"[SCENARIO] Theme '{theme}' -> color {chosen}")
    set_color(chosen)

def party_mode(theme: str = "party"):
    state = get_status()
    if not state.get("enabled"):
        print("[INFO] Bulb is OFF, turning on for party mode.")
        turn_on()

    current_theme = theme.lower()
    steps = random.randint(*PARTY_STEPS_RANGE)
    wait_min, wait_max = PARTY_WAIT_RANGE
    print(f"[PARTY] Start theme='{current_theme}', steps={steps}, wait={wait_min:.2f}-{wait_max:.2f}s")

    for _ in range(steps):
        palette = THEMES[current_theme]
        set_color(random.choice(palette))
        time.sleep(random.uniform(wait_min, wait_max))

    st = get_status()
    if st.get("brightness", 0) > 30 and random.random() < 0.5:
        print("[PARTY] Cooling down: dimming a bit.")
        decrease_brightness(st.get("brightness", 0))

def wait_between_actions():
    delay = random.randint(2, 10)
    print(f"[WAIT] Waiting {delay} seconds before next action...\n")
    time.sleep(delay)

def run_random_scenario():
    st = get_status()
    enabled = bool(st.get("enabled"))
    bright = int(st.get("brightness", 0))

    for _ in range(random.randint(2, 4)):
        possible = []
        if not enabled:
            possible.append(lambda: (turn_on(), "turn_on"))
        else:
            possible.append(lambda: (turn_off(), "turn_off"))
            if bright < 100:
                possible.append(lambda: (increase_brightness(bright), "inc_brightness"))
            if bright > 0:
                possible.append(lambda: (decrease_brightness(bright), "dec_brightness"))
            possible.append(lambda: (change_color(random.choice(list(THEMES.keys()))), "change_color"))

        if possible:
            action_fn = random.choice(possible)
            _, name = action_fn()
            print(f"[SCENARIO] Executed: {name}")
            wait_between_actions()
            st = get_status()
            enabled = bool(st.get("enabled"))
            bright = int(st.get("brightness", 0))

def main():
    print(f"[SIM] Mixed controller (BACKEND={BACKEND}, MIXED_STRICT_ALTERNATE={MIXED_STRICT_ALTERNATE}, RATIO={MIXED_MATTER_RATIO})")
    if ONE_SHOT:
        print("[SIM] ONE_SHOT enabled → running a single scenario and exiting.")
        run_random_scenario()
        return

    while True:
        if random.random() < ACTIVE_RATIO:
            print("[SCHEDULE] Active window: running scenario")
            run_random_scenario()
        else:
            idle_for = random.randint(*IDLE_SLEEP_RANGE)
            print(f"[SCHEDULE] Idle for {idle_for}s")
            time.sleep(idle_for)
        time.sleep(CYCLE_SLEEP)

if __name__ == "__main__":
    try:
        main()
    except MatterError as e:
        print(f"[ERROR] Matter backend: {e}")
    except requests.HTTPError as e:
        print(f"[ERROR] Cloud backend HTTP: {e}")
    except KeyboardInterrupt:
        print("\n[SIM] Stopped by user")
