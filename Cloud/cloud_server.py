from flask import Flask, request
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


app = Flask(__name__)


BULB_IP = "simulation-bicycle-will-apply.trycloudflare.com"

# recept heartbeat
@app.route("/heartbeat", methods=["POST"])
def heartbeat():
    data = request.json
    print(f"[CLOUD] Heartbeat received: {data}", flush=True)
    return "OK", 200

# Command to control smart bulb
@app.route("/cloud/on", methods=["POST"])
def cloud_turn_on():
    try:
        r = requests.post(f"https://{BULB_IP}/on", verify=False)
        return f"[CLOUD] Sent ON to bulb, response: {r.text}", 200
    except Exception as e:
        return f"[CLOUD] Error: {e}", 500

@app.route("/cloud/off", methods=["POST"])
def cloud_turn_off():
    try:
        r = requests.post(f"https://{BULB_IP}/off", verify=False)
        return f"[CLOUD] Sent off to bulb, response: {r.text}", 200
    except Exception as e:
        return f"[CLOUD] Error: {e}", 500

@app.route("/cloud/brightness", methods=["POST"])
def cloud_brightness():
    level = request.json.get("level", 100)
    try:
        r = requests.post(f"https://{BULB_IP}/brightness", json={"level": level}, verify=False)
        return f"[CLOUD] Set brightness to {level}, response: {r.text}", 200
    except Exception as e:
        return f"[CLOUD] Error: {e}", 500
@app.route("/cloud/status", methods=["GET"])
def cloud_status():
    try:
        r = requests.get(f"https://{BULB_IP}/status", verify=False)
        return r.json(), 200
    except Exception as e:
        return {"error": str(e)}, 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6000, ssl_context=("cert.pem", "ke