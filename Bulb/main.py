import threading
import time
import random
import os
import traceback
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from network import send_arp, heartbeat, network_discovery
from bulb import app as control_app
from scenario import ALL_SCENARIOS

def run_random_scenarios():
    print("[THREAD] run_random_scenarios started")
    while True:
        try:
            scenario = random.choice(ALL_SCENARIOS)
            print(f"[SIMULATION] Executing scenario: {scenario.__name__}")
            scenario()
        except Exception:
            print("[ERROR] Scenario crashed:")
            traceback.print_exc()
        time.sleep(random.randint(60, 180))

if __name__ == "__main__":
    threading.Thread(
        target=lambda: control_app.run(host="172.18.106.182", port=5000, ssl_context=("./cert.pem", "./key.pem")),
        daemon=True
    ).start()
    #threading.Thread(target=send_arp, daemon=True).start() #keep alive
    threading.Thread(target=heartbeat, kwargs={"cloud_ip": "172.18.106.184"}, daemon=True).start() #heartbeat
    #threading.Thread(target=network_discovery, daemon=True).start() #udp broadcast
    threading.Thread(target=run_random_scenarios, daemon=True).start() #scenario

    while True:
        time.sleep(60)
