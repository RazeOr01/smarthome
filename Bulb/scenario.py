import requests
import time
import random

BULB_IP = "www.cesieat.ovh"
BASE_URL = f"https://{BULB_IP}"

#turn on bulb, brightness to 75, check status
def scenario_1():
    print("[SCENARIO 1] Turn on -> Brightness 75 -> Status",flush=True)
    try:
        requests.post(f"{BASE_URL}/cloud/on", verify=False)
        time.sleep(2)
        requests.post(f"{BASE_URL}/cloud/brightness", json={"level": 75}, verify=False)
        time.sleep(2)
        r = requests.get(f"{BASE_URL}/cloud/status", verify=False)
        print("[STATUS]", r.json())
    except Exception as e:
        print("Scenario 1 failed:", e)

# brightness to 30%, wait 2 minutes, then turn off
def scenario_2():
    print("[SCENARIO 2] Brightness 30 -> wait -> Off",flush=True)
    try:
        requests.post(f"{BASE_URL}/cloud/brightness", json={"level": 30}, verify=False)
        time.sleep(120)
        requests.post(f"{BASE_URL}/cloud/off", verify=False)
    except Exception as e:
        print("Scenario 2 failed:", e)

#Toggle power rapidly, simulating flickering.
def scenario_3():
    print("[SCENARIO 3] ON/OFF",flush=True)
    try:
        for _ in range(3):
            requests.post(f"{BASE_URL}/cloud/on", verify=False)
            time.sleep(1)
            requests.post(f"{BASE_URL}/cloud/off", verify=False)
            time.sleep(1)
        requests.post(f"{BASE_URL}/cloud/on", verify=False)
    except Exception as e:
        print("Scenario 3 failed:", e)

#gradually dim light from 100 to 0
def scenario_4():
    print("[SCENARIO 4] Dim from 100 → 0",flush=True)
    try:
        for level in range(100, -1, -25):
            requests.post(f"{BASE_URL}/cloud/brightness", json={"level": level}, verify=False)
            time.sleep(1)
    except Exception as e:
        print("Scenario 4 failed:", e)


ALL_SCENARIOS = [scenario_1, scenario_2, scenario_3, scenario_4]
