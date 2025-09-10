import os
import re
import json
import uuid
import logging
from typing import Any, Dict, Optional, Tuple
from datetime import datetime, timedelta

import requests
from flask import Flask, Blueprint, request, jsonify, g
from urllib3.util import Retry
from requests.adapters import HTTPAdapter


BULB_HOST = os.getenv("BULB_HOST", "pros-we-centres-subtle.trycloudflare.com")
BULB_BASE_URL = f"https://{BULB_HOST}"
VERIFY_TLS = os.getenv("VERIFY_TLS", "true").lower() != "false"  #  override for testing
API_KEY = os.getenv("API_KEY")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "5"))
MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", "2048"))  # bytes
IDEMPOTENCY_TTL_SECONDS = int(os.getenv("IDEMPOTENCY_TTL_SECONDS", "60"))


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s req=%(request_id)s %(message)s",
)
logger = logging.getLogger(__name__)


session = requests.Session()
retries = Retry(
    total=3,
    backoff_factor=0.25,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods={"GET", "POST"},
)
session.mount("https://", HTTPAdapter(max_retries=retries))


HEX_COLOR_RE = re.compile(r"^#([0-9a-fA-F]{6})$")

def is_valid_hex_color(value: Any) -> bool:
    return isinstance(value, str) and HEX_COLOR_RE.fullmatch(value) is not None

def parse_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.lower() in {"true", "1", "yes", "on"}:
            return True
        if value.lower() in {"false", "0", "no", "off"}:
            return False
    return None

_idempo: Dict[str, Tuple[datetime, Dict[str, Any], int]] = {}


def idempotency_lookup(key: str) -> Optional[Tuple[Dict[str, Any], int]]:
    now = datetime.utcnow()
    entry = _idempo.get(key)
    if not entry:
        return None
    ts, body, status = entry
    if now - ts > timedelta(seconds=IDEMPOTENCY_TTL_SECONDS):
        _idempo.pop(key, None)
        return None
    return body, status


def idempotency_store(key: str, body: Dict[str, Any], status: int) -> None:
    _idempo[key] = (datetime.utcnow(), body, status)



@app.before_request
def before_request():
    g.request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
    logging.LoggerAdapter(logger, {"request_id": g.request_id})

    if API_KEY:
        provided = request.headers.get("X-API-Key")
        if not provided or provided != API_KEY:
            return jsonify({
                "error": "unauthorized",
                "message": "Missing or invalid API key",
                "request_id": g.request_id,
            }), 401


@app.after_request
def after_request(resp):
    resp.headers["X-Request-Id"] = g.get("request_id", "-")
    return resp


@app.errorhandler(400)
def bad_request(e):
    return jsonify({"error": "bad_request", "message": str(e), "request_id": g.request_id}), 400


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "not_found", "message": "Route not found", "request_id": g.request_id}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "server_error", "message": str(e), "request_id": g.request_id}), 500




def bulb_post(path: str, json_body: Optional[Dict[str, Any]] = None) -> requests.Response:
    url = f"{BULB_BASE_URL}{path}"
    return session.post(url, json=json_body, verify=VERIFY_TLS, timeout=REQUEST_TIMEOUT)


def bulb_get(path: str) -> requests.Response:
    url = f"{BULB_BASE_URL}{path}"
    return session.get(url, verify=VERIFY_TLS, timeout=REQUEST_TIMEOUT)


cloud = Blueprint("cloud", __name__, url_prefix="/cloud")


@cloud.route("/heartbeat", methods=["POST"])
def heartbeat():
    data = request.get_json(silent=True) or {}
    logger.info("Heartbeat received", extra={"request_id": g.request_id})
    return jsonify({"status": "ok", "received": data, "request_id": g.request_id})


@cloud.route("", methods=["GET"])  # GET /cloud -> current status (proxy)
def get_status():
    try:
        r = bulb_get("/status")
        r.raise_for_status()
        body = r.json()
        return jsonify({"request_id": g.request_id, **body}), 200
    except Exception as e:
        logger.exception("Failed to fetch status")
        return jsonify({"error": "upstream_error", "message": str(e), "request_id": g.request_id}), 502


@cloud.route("", methods=["PATCH"])  # PATCH /cloud -> set enabled/brightness/color
def patch_cloud():
    idem_key = request.headers.get("Idempotency-Key")
    if idem_key:
        cached = idempotency_lookup(idem_key)
        if cached:
            body, status = cached
            body = dict(body)
            body["idempotent"] = True
            body["request_id"] = g.request_id
            return jsonify(body), status

    payload = request.get_json(silent=True) or {}

    enabled = payload.get("enabled")
    brightness = payload.get("brightness")
    color = payload.get("color")

    if enabled is not None and parse_bool(enabled) is None:
        return jsonify({"error": "validation", "message": "'enabled' must be boolean"}), 400
    if brightness is not None:
        try:
            brightness = int(brightness)
        except (TypeError, ValueError):
            return jsonify({"error": "validation", "message": "'brightness' must be integer"}), 400
        if not (0 <= brightness <= 100):
            return jsonify({"error": "validation", "message": "'brightness' must be between 0 and 100"}), 400
    if color is not None and not is_valid_hex_color(color):
        return jsonify({"error": "validation", "message": "'color' must be hex like '#RRGGBB'"}), 400

    if enabled is None and brightness is None and color is None:
        return jsonify({"error": "validation", "message": "Provide at least one of: enabled, brightness, color"}), 400

    results = {}
    try:
        if enabled is not None:
            if parse_bool(enabled):
                r = bulb_post("/on")
            else:
                r = bulb_post("/off")
            r.raise_for_status()
            results["enabled"] = parse_bool(enabled)

        if brightness is not None:
            r = bulb_post("/brightness", json_body={"level": brightness})
            r.raise_for_status()
            results["brightness"] = brightness

        if color is not None:
            color_up = color.upper()
            r = bulb_post("/color", json_body={"color": color_up})
            r.raise_for_status()
            results["color"] = color_up

        body = {"status": "ok", "applied": results, "request_id": g.request_id}
        status = 200
        if idem_key:
            idempotency_store(idem_key, body, status)
        return jsonify(body), status

    except requests.HTTPError as e:
        logger.exception("Upstream returned error")
        return jsonify({
            "error": "upstream_http_error",
            "message": str(e),
            "request_id": g.request_id,
        }), 502
    except Exception as e:
        logger.exception("Failed to apply changes")
        return jsonify({
            "error": "upstream_error",
            "message": str(e),
            "request_id": g.request_id,
        }), 502


app.register_blueprint(cloud)


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "6000"))
    app.run(host=host, port=port)
