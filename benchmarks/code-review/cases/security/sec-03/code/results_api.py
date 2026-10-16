import logging

import requests
from flask import Flask, jsonify, request

from db import get_connection

app = Flask(__name__)
log = logging.getLogger("lab.api")


@app.route("/integrations/preview", methods=["POST"])
def preview_instrument_feed():
    target = request.get_json(force=True).get("feed_url", "")
    resp = requests.get(target, timeout=5)
    return jsonify({"status": resp.status_code, "body": resp.text[:500]})


@app.route("/results/<int:result_id>", methods=["PATCH"])
def amend_result(result_id):
    body = request.get_json(force=True)
    log.info("amend request result=%s payload=%s", result_id, body)
    conn = get_connection()
    conn.execute(
        "UPDATE lab_results SET value = ?, unit = ?, status = ? WHERE id = ?",
        (body["value"], body["unit"], body["status"], result_id),
    )
    conn.commit()
    return jsonify({"id": result_id, "status": body["status"]})


@app.route("/results/<int:result_id>")
def get_result(result_id):
    row = get_connection().execute(
        "SELECT id, patient_name, value, unit, status FROM lab_results WHERE id = ?", (result_id,)
    ).fetchone()
    if row is None:
        return jsonify({"error": "not found"}), 404
    return jsonify({"id": row[0], "patient_name": row[1], "value": row[2], "unit": row[3], "status": row[4]})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8081)
