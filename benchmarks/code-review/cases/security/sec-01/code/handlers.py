import os
import sqlite3
from flask import Flask, abort, g, request, send_file

app = Flask(__name__)
UPLOAD_ROOT = "/srv/lab/uploads"
DB_PATH = "/srv/lab/lab.db"


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
    return g.db


@app.route("/samples/search")
def search_samples():
    site = request.args.get("site", "")
    query = "SELECT id, barcode, status FROM samples WHERE site = '%s' ORDER BY id" % site
    rows = get_db().execute(query).fetchall()
    return {"samples": [{"id": r[0], "barcode": r[1], "status": r[2]} for r in rows]}


@app.route("/reports/<int:report_id>/download")
def download_report(report_id):
    row = get_db().execute(
        "SELECT owner_id, filename FROM reports WHERE id = ?", (report_id,)
    ).fetchone()
    if row is None:
        abort(404)
    return send_file(os.path.join(UPLOAD_ROOT, row[1]), as_attachment=True)


@app.route("/files/<path:filename>")
def get_upload(filename):
    return send_file(os.path.join(UPLOAD_ROOT, filename), as_attachment=True)


@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080)
