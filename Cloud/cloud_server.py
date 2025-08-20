from flask import Flask, request
import requests
import urllib3
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

BULB_IP = "pros-we-centres-subtle.trycloudflare.com"

# ---- Helpers ----
HEX_COLOR_RE = re.compile(r"^#([0-9a-fA-F]{6})$")

def is_valid_hex_color(value: str) -> bool:
    return isinstance(value, str) and HEX_COLOR_RE.fullmatch(value) is not None

# ---- Endpoints ----

# receive heartbeat
@app.route("/heartbeat", methods=["POST"])
def heartbeat():
    data = request.json
    print(f"[CLOUD] Heartbeat received: {data}", flush=True)
    return "OK", 200

# Commands to control smart bulb
@app.route("/cloud/on", methods=["POST"])
def cloud_turn_on():
    try:
        r = requests.post(f"https://{BULB_IP}/on", verify=False, timeout=5)
        return f"[CLOUD] Sent ON to bulb, response: {r.text}", 200
    except Exception as e:
        return f"[CLOUD] Error: {e}", 500

@app.route("/cloud/off", methods=["POST"])
def cloud_turn_off():
    try:
        r = requests.post(f"https://{BULB_IP}/off", verify=False, timeout=5)
        return f"[CLOUD] Sent OFF to bulb, response: {r.text}", 200
    except Exception as e:
        return f"[CLOUD] Error: {e}", 500

@app.route("/cloud/brightness", methods=["POST"])
def cloud_brightness():
    payload = request.get_json(silent=True) or {}
    level = int(payload.get("level", 100))
    try:
        r = requests.post(
            f"https://{BULB_IP}/brightness",
            json={"level": level},
            verify=False,
            timeout=5,
        )
        return f"[CLOUD] Set brightness to {level}, response: {r.text}", 200
    except Exception as e:
        return f"[CLOUD] Error: {e}", 500

# NEW: set color
@app.route("/cloud/color", methods=["POST"])
def cloud_color():
    payload = request.get_json(silent=True) or {}
    color = payload.get("color")

    if not is_valid_hex_color(color):
        return (
            "[CLOUD] Invalid 'color'. Expected hex string like '#RRGGBB'.",
            400,
        )

    try:
        r = requests.post(
            f"https://{BULB_IP}/color",
            json={"color": color.upper()},
            verify=False,
            timeout=5,
        )
        return f"[CLOUD] Set color to {color.upper()}, response: {r.text}", 200
    except Exception as e:
        return f"[CLOUD] Error: {e}", 500

@app.route("/cloud/status", methods=["GET"])
def cloud_status():
    try:
        r = requests.get(f"https://{BULB_IP}/status", verify=False, timeout=5)
        return r.json(), 200
    except Exception as e:
        return {"error": str(e)}, 500

if __name__ == "__main__":
    # host/port inchangés
    app.run(host="0.0.0.0", port=6000)
