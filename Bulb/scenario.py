import requests
import time
import random

BULB_IP = "www.cesieat.ovh"
BASE_URL = f"https://{BULB_IP}"
VERIFY_SSL = False  


is_on = False
brightness = 0

def get_status():
    global is_on, brightness
    try:
        r = requests.get(f"{BASE_URL}/cloud/status", verify=VERIFY_SSL)
        data = r.json()
        is_on = data.get("is_on", False)
        brightness = data.get("brightness", 0)
        print(f"[STATUS] ON={is_on}, Brightness={brightness}")
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
        print("[SKIPPED] Brightness already at 100%")

def decrease_brightness():
    global brightness
    if brightness > 0:
        decrement = random.randint(10, 30)
        brightness = max(0, brightness - decrement)
        print(f"[ACTION] Decreasing brightness to {brightness}")
        requests.post(f"{BASE_URL}/cloud/brightness", json={"level": brightness}, verify=VERIFY_SSL)
        wait_between_actions()
    else:
        print("[SKIPPED] Brightness already at 0%")

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

        if possible_actions:
            action = random.choice(possible_actions)
            print(f"[SCENARIO] Executing: {action.__name__}")
            try:
                action()
            except Exception as e:
                print(f"[ERROR] {action.__name__} failed: {e}")
