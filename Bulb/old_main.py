import threading
from network import send_arp, heartbeat, network_discovery
import time
from bulb import app as control_app

#Thread

if __name__ == "__main__":
    threading.Thread(target=lambda: control_app.run(host="0.0.0.0", port=5000), daemon=True).start()
    threading.Thread(target=send_arp, daemon=True).start()
    threading.Thread(target=heartbeat, kwargs={"cloud_ip": "192.168.0.205"}, daemon=True).start()
    threading.Thread(target=network_discovery, daemon=True).start()

    while True:
        time.sleep(1)
