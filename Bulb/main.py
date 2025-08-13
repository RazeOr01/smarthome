import threading
import time
import random
import os
import traceback
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from network import send_arp, heartbeat, network_discovery
from bulb import app as control_app
from scenario import run_random_scenario  

def scenario_loop():
    print("[THREAD] scenario_loop started")
    while True:
        try:
            run_random_scenario()  
        except Exception:
            print("[ERROR] Scenario crashed:")
            traceback.print_exc()
        time.sleep(random.randint(60, 180))

if __name__ == "__main__":
    threading.Thread(
        target=lambda: control_app.run(host="0.0.0.0", port=5000),
        daemon=True
    ).start()

    threading.Thread(target=send_arp, daemon=True).start()
    threading.Thread(target=heartbeat, daemon=True).start()
    threading.Thread(target=network_discovery, daemon=True).start()
    threading.Thread(target=scenario_loop, daemon=True).start()

    while True:
        time.sleep(60)
