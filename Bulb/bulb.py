from flask import Flask, request, jsonify
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class SmartBulb:
    def __init__(self):
        self.is_on = False
        self.brightness = 100  # 0-100

    def turn_on(self):
        self.is_on = True

    def turn_off(self):
        self.is_on = False

    def set_brightness(self, value):
        self.brightness = max(0, min(100, value))

    def status(self):
        return {
            "is_on": self.is_on,
            "brightness": self.brightness
        }

bulb = SmartBulb()
app = Flask(__name__)

@app.route("/status", methods=["GET"])
def get_status():
    return jsonify(bulb.status())

@app.route("/on", methods=["POST"])
def turn_on():
    bulb.turn_on()
    return "Bulb turned ON", 200

@app.route("/off", methods=["POST"])
def turn_off():
    bulb.turn_off()
    return "Bulb turned OFF", 200

@app.route("/brightness", methods=["POST"])
def brightness():
    level = request.json.get("level", 100)
    bulb.set_brightness(level)
    return f"Brightness set to {level}", 200

if __name__ == "__main__":
    app.run(host="192.168.0.209", port=5000)
