from flask import Flask, request, jsonify
import urllib3
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class SmartBulb:
    def __init__(self):
        self.is_on = False
        self.brightness = 100  # 0-100
        self.color = "#FFFFFF"  # couleur par défaut : blanc

    def turn_on(self):
        self.is_on = True

    def turn_off(self):
        self.is_on = False

    def set_brightness(self, value):
        self.brightness = max(0, min(100, value))

    def set_color(self, hex_color):
        # validation rapide du format #RRGGBB
        if isinstance(hex_color, str) and re.fullmatch(r"^#[0-9A-Fa-f]{6}$", hex_color):
            self.color = hex_color.upper()
        else:
            raise ValueError("Invalid color format, expected '#RRGGBB'")

    def status(self):
        return {
            "is_on": self.is_on,
            "brightness": self.brightness,
            "color": self.color
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

@app.route("/color", methods=["POST"])
def color():
    data = request.get_json(silent=True) or {}
    hex_color = data.get("color")
    try:
        bulb.set_color(hex_color)
        return f"Color set to {hex_color.upper()}", 200
    except Exception as e:
        return str(e), 400

if __name__ == "__main__":
    app.run(host="192.168.0.209", port=5000)
