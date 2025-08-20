import requests
import time
import random

BULB_IP = "www.cesieat.ovh"
BASE_URL = f"https://{BULB_IP}"
VERIFY_SSL = False

#proportion of the time to do nothing, 11% / 89%
ACTIVE_RATIO = 0.11
IDLE_SLEEP_RANGE = (60, 300)
CYCLE_SLEEP = 1

COLOR_ENDPOINT = f"{BASE_URL}/cloud/color"

THEMES = {
    "party":   ["#FF0040", "#FF8000", "#FFD300", "#00E5FF", "#7D00FF", "#00FF85"],
    "neon":    ["#39FF14", "#FF073A", "#0FF0FC", "#FE53BB", "#F5F500"],
    "ocean":   ["#003F5C", "#2F4B7C", "#00B5C7", "#2EC4B6", "#A3EFFF"],
    "sunset":  ["#FF4500", "#FF7F50", "#FDB813", "#FF1493", "#8B00FF"],
    "forest":  ["#0B6623", "#2D6A4F", "#40916C", "#95D5B2", "#74C69D"],
    "pastel":  ["#FFADAD", "#FFD6A5", "#FDFFB6", "#CAFFBF", "#A0C4FF", "#BDB2FF"],
    "halloween": ["#FF7518", "#000000", "#6A0DAD", "#9B870C", "#8A0303"],
    "xmas":    ["#FF0000", "#008000", "#FFFFFF", "#006400", "#C41E3A"]
}

PARTY_STEPS_RANGE = (5, 15)
PARTY_WAIT_RANGE = (0.4, 1.5)


is_on = False
brightness = 0
color = "#000000"

def get_status():
    global is_on, brightness, color
    try:
        r = requests.get(f"{BASE_URL}/cloud/status", verify=VERIFY_SSL)
        data = r.json()
        is_on = data.get("is_on", False)
        brightness = data.get("brightness", 0)
        color = data.get("color", color)
        print(f"[STATUS] ON={is_on}, Brightness={brightness}, Color={color}")
    except Exception as e:
        print("[ERROR] Failed to get status:", e)

def turn_on():
    global is_on
    if not is_on:
        print("[ACTION] Turning ON")
        requests.post(f"{BASE_URL}/cloud/on", verify=VERIFY_SSL)
        is_on = True
        wait_between_actions()
    else:
        print("[SKIPPED] Already ON")

def turn_off():
    global is_on
    if is_on:
        print("[ACTION] Turning OFF")
        requests.post(f"{BASE_URL}/cloud/off", verify=VERIFY_SSL)
        is_on = False
        wait_between_actions()
    else:
        print("[SKIPPED] Already OFF")

def increase_brightness():
    global brightness
    if brightness < 100:
        increment = random.randint(10, 30)
        brightness = min(100, brightness + increment)
        print(f"[ACTION] Increasing brightness to {brightness}")
        requests.post(f"{BASE_URL}/cloud/brightness", json={"level": brightness}, verify=VERIFY_SSL)
        wait_between_actions()
    else:
        print("Brightness already at 100%")

def decrease_brightness():
    global brightness
    if brightness > 0:
        decrement = random.randint(10, 30)
        brightness = max(0, brightness - decrement)
        print(f"[ACTION] Decreasing brightness to {brightness}")
        requests.post(f"{BASE_URL}/cloud/brightness", json={"level": brightness}, verify=VERIFY_SSL)
        wait_between_actions()
    else:
        print("Brightness already at 0%")

def set_color(hex_color: str):
    global color
    hex_color = hex_color.upper()
    if not hex_color.startswith("#") or len(hex_color) != 7:
        print(f"[WARN] Invalid color '{hex_color}', expected format #RRGGBB")
        return
    print(f"[ACTION] Setting color to {hex_color}")
    try:
        requests.post(COLOR_ENDPOINT, json={"color": hex_color}, verify=VERIFY_SSL)
        color = hex_color
    except Exception as e:
        print("[ERROR] Failed to set color:", e)
    wait_between_actions()

def change_color(theme: str = "party"):
    if not is_on:
        print("[INFO] Bulb is OFF, turning on for color change.")
        turn_on()
    palette = THEMES.get(theme.lower(), THEMES["party"])
    chosen = random.choice(palette)
    print(f"[SCENARIO] Theme '{theme}' -> color {chosen}")
    set_color(chosen)

def party_mode(theme: str = "party"):
    if not is_on:
        print("[INFO] Bulb is OFF, turning on for party mode.")
        turn_on()

    current_theme = theme.lower()
    steps = random.randint(*PARTY_STEPS_RANGE)
    wait_min, wait_max = PARTY_WAIT_RANGE
    print(f"[PARTY] Start theme='{current_theme}', steps={steps}, wait={wait_min:.2f}-{wait_max:.2f}s")

    for _ in range(steps):
        palette = THEMES[current_theme]
        set_color(random.choice(palette))
        pause = random.uniform(wait_min, wait_max)
        time.sleep(pause)

    # Option: petit fade-out lumineux à la fin du party
    if brightness > 30 and random.random() < 0.5:
        print("[PARTY] Cooling down: dimming a bit.")
        decrease_brightness()

def wait_between_actions():
    delay = random.randint(2, 10)
    print(f"[WAIT] Waiting {delay} seconds before next action...\n")
    time.sleep(delay)

def run_random_scenario():
    get_status()

    for _ in range(random.randint(2, 4)):
        possible_actions = []

        if not is_on:
            possible_actions.append(turn_on)
        else:
            possible_actions.append(turn_off)
            if brightness < 100:
                possible_actions.append(increase_brightness)
            if brightness > 0:
                possible_actions.append(decrease_brightness)
            possible_actions.append(lambda: change_color(random.choice(list(THEMES.keys()))))


        if possible_actions:
            action = random.choice(possible_actions)
            print(f"[SCENARIO] Executing: {getattr(action, '__name__', 'anonymous')}")
            try:
                action()
            except Exception as e:
                print(f"[ERROR] action failed: {e}")

def main():
    print("[SIM] Smart bulb simulator starting with ~11% active time + party color features (sans évolution).")
    while True:
        if random.random() < ACTIVE_RATIO:
            print("[SCHEDULE] Active window: running scenario")
            run_random_scenario()
        else:
            idle_for = random.randint(*IDLE_SLEEP_RANGE)
