from flask import Blueprint, request, jsonify
from envelope import Envelope, EnvelopeError

http_transport = Blueprint('http_transport', __name__)

_daemon = None
_shared_key = None


def init_http_transport(daemon, key: str) -> None:
    global _daemon, _shared_key
    _daemon = daemon
    _shared_key = key


@http_transport.route('/f42bbs/inbound', methods=['POST'])
def inbound():
    try:
        data = request.get_json()
        if data is None:
            return jsonify({"error": "bad json"}), 400
    except Exception:
        return jsonify({"error": "bad json"}), 400

    try:
        env = Envelope.parse(data, _shared_key)
    except EnvelopeError as e:
        return jsonify({"error": "invalid signature"}), 403

    try:
        result = _daemon.inbound(env)
        return jsonify({"status": "ok", "result": result}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
