import os
import time
import random
import uuid
from typing import Optional, Dict, Any

import requests
from urllib3.util import Retry
from requests.adapters import HTTPAdapter


CLOUD_HOST = os.getenv("CLOUD_HOST", "www.cesieat.ovh")
BASE_URL = f"https://{CLOUD_HOST}"
VERIFY_TLS = os.getenv("VERIFY_TLS", "true").lower() != "false"
API_KEY = os.getenv("API_KEY")  
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "5"))

ACTIVE_RATIO = 0.11
IDLE_SLEEP_RANGE = (60, 300)
CYCLE_SLEEP = 1

PARTY_STEPS_RANGE = (5, 15)
PARTY_WAIT_RANGE = (0.4, 1.5)

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



def turn_on():
    print("[ACTION] Turning ON")
    patch_cloud(enabled=True)


def turn_off():
    print("[ACTION] Turning OFF")
    patch_cloud(enabled=False)


def increase_brightness(cur: Optional[int] = None):
    if cur is None:
        cur = int(get_status().get("brightness", 0))
    if cur < 100:
        inc = random.randint(10, 30)
        new_val = min(100, cur + inc)
        print(f"[ACTION] Increasing brightness to {new_val}")
        patch_cloud(brightness=new_val)
    else:
        print("[SKIP] Brightness already at 100%")


def decrease_brightness(cur: Optional[int] = None):
    if cur is None:
        cur = int(get_status().get("brightness", 0))
    if cur > 0:
        dec = random.randint(10, 30)
        new_val = max(0, cur - dec)
        print(f"[ACTION] Decreasing brightness to {new_val}")
        patch_cloud(brightness=new_val)
    else:
        print("[SKIP] Brightness already at 0%")


def set_color(hex_color: str):
    hex_color = hex_color.upper()
    print(f"[ACTION] Setting color to {hex_color}")
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
    print("[SIM] User-like controller using PATCH /cloud")
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
    except KeyboardInterrupt:
        print("\n[SIM] Stopped by user")
