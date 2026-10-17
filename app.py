import os
import re
import json
import time
import secrets
from datetime import datetime, timedelta, timezone
import sqlite3
from flask import Flask, request, jsonify, send_from_directory, Response
from werkzeug.middleware.proxy_fix import ProxyFix
from qr import qr_svg

# ---------------------------------------------------------------------------
# AMR Health Care - Clinic Management (server)
# Software khud browser mein (static/index.html) chalta hai aur offline bhi kaam
# karta hai. Ye server sirf sabhi computers/mobile ka data sync aur safe rakhta hai.
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _web_dir():
    # index.html "static" folder mein ho ya app.py ke saath same folder mein - dono chalega
    for d in (os.path.join(BASE_DIR, "static"), BASE_DIR):
        if os.path.exists(os.path.join(d, "index.html")):
            return d
    return BASE_DIR


WEB_DIR = _web_dir()
app = Flask(__name__, static_folder=None)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
IST = timezone(timedelta(hours=5, minutes=30))

DATABASE_URL = os.environ.get("DATABASE_URL")
SQLITE_FILE = os.environ.get("SQLITE_FILE", "amr.db")
TABLE = re.sub(r"\W", "", os.environ.get("RECORDS_TABLE", "amr_records")) or "records"

if DATABASE_URL:
    import psycopg2
    PH = "%s"
else:
    PH = "?"


class _Cur:
    def __init__(self, c):
        self._c = c

    def execute(self, sql, args=None):
        sql = re.sub(r"\brecords_updated_idx\b", TABLE + "_updated_idx", sql)
        sql = re.sub(r"\brecords\b", TABLE, sql)
        return self._c.execute(sql) if args is None else self._c.execute(sql, args)

    def __getattr__(self, n):
        return getattr(self._c, n)


class _Conn:
    def __init__(self, c):
        self._c = c

    def cursor(self):
        return _Cur(self._c.cursor())

    def __getattr__(self, n):
        return getattr(self._c, n)


def get_db():
    if DATABASE_URL:
        return _Conn(psycopg2.connect(DATABASE_URL))
    return _Conn(sqlite3.connect(SQLITE_FILE, timeout=20))


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS records (
            store TEXT NOT NULL,
            id TEXT NOT NULL,
            data TEXT NOT NULL,
            updated_at BIGINT NOT NULL,
            PRIMARY KEY (store, id)
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS records_updated_idx ON records (updated_at)")
    conn.commit()
    conn.close()


init_db()


# ------------------------------- pages --------------------------------------
@app.route("/")
def home():
    resp = send_from_directory(WEB_DIR, "index.html")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.route("/sw.js")
def service_worker():
    resp = send_from_directory(WEB_DIR, "sw.js", mimetype="application/javascript")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.route("/manifest.json")
def manifest():
    return send_from_directory(WEB_DIR, "manifest.json", mimetype="application/manifest+json")


@app.route("/icon.svg")
def icon():
    return send_from_directory(WEB_DIR, "icon.svg", mimetype="image/svg+xml")


# -------------------------------- API ---------------------------------------
@app.route("/api/ping")
def ping():
    return jsonify({"ok": True})


@app.route("/api/records", methods=["GET"])
def get_records():
    since = int(request.args.get("since", 0) or 0)
    limit = min(int(request.args.get("limit", 500) or 500), 1000)
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT store, id, data, updated_at FROM records WHERE updated_at > "
        + PH + " ORDER BY updated_at ASC LIMIT " + PH,
        (since, limit),
    )
    rows = [
        {"store": r[0], "id": r[1], "data": json.loads(r[2]), "updated_at": int(r[3])}
        for r in cur.fetchall()
    ]
    conn.close()
    return jsonify(rows)


def _lock(cur):
    # ek time par ek hi write - taaki updated_at hamesha badhta rahe
    if DATABASE_URL:
        cur.execute("SELECT pg_advisory_xact_lock(7001)")
    else:
        cur.execute("BEGIN IMMEDIATE")


def _next_ts(cur):
    # server ki apni ghadi: kisi device ki ghadi aage-peeche ho to bhi sync nahi ruktaa
    cur.execute("SELECT COALESCE(MAX(updated_at), 0) FROM records")
    mx = int(cur.fetchone()[0] or 0)
    return max(int(time.time() * 1000), mx + 1)


@app.route("/api/records", methods=["POST"])
def post_records():
    rows = request.get_json(force=True, silent=True) or []
    if not isinstance(rows, list):
        return jsonify({"error": "list expected"}), 400
    conn = get_db()
    cur = conn.cursor()
    n = 0
    try:
        _lock(cur)
        ts = _next_ts(cur)
        for r in rows:
            try:
                store, rid, data = str(r["store"]), str(r["id"]), r["data"]
                cu = int(data.get("_u") or r.get("updated_at") or 0)
            except (KeyError, ValueError, TypeError, AttributeError):
                continue
            data["_u"] = cu
            cur.execute("SELECT data FROM records WHERE store = " + PH + " AND id = " + PH, (store, rid))
            old = cur.fetchone()
            if old:
                try:
                    ou = int(json.loads(old[0]).get("_u") or 0)
                except (ValueError, TypeError):
                    ou = 0
                if cu < ou:
                    continue  # server par isse naya version pehle se hai
                cur.execute(
                    "UPDATE records SET data = " + PH + ", updated_at = " + PH + " WHERE store = " + PH + " AND id = " + PH,
                    (json.dumps(data), ts, store, rid),
                )
            else:
                cur.execute(
                    "INSERT INTO records (store, id, data, updated_at) VALUES (" + ",".join([PH] * 4) + ")",
                    (store, rid, json.dumps(data), ts),
                )
            ts += 1
            n += 1
        conn.commit()
    finally:
        conn.close()
    return jsonify({"saved": n})


@app.route("/api/summary")
def summary():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT store, COUNT(*), MAX(updated_at) FROM records GROUP BY store")
    out = {r[0]: {"count": int(r[1]), "max": int(r[2])} for r in cur.fetchall()}
    conn.close()
    return jsonify(out)


@app.route("/api/export")
def export_all():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT store, id, data, updated_at FROM records")
    data = {}
    for store, rid, raw, ts in cur.fetchall():
        data.setdefault(store, []).append(json.loads(raw))
    conn.close()
    body = json.dumps({"app": "amr-clinic", "v": 1, "ts": 0, "counters": {}, "data": data})
    return Response(
        body,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=AMR_Server_Backup.json"},
    )


# ------------------- patient self-booking (public, no login) -----------------
_hits = {}


def _throttle(ip, limit=15, window=3600):
    now = time.time()
    lst = [t for t in _hits.get(ip, []) if now - t < window]
    if len(lst) >= limit:
        _hits[ip] = lst
        return False
    lst.append(now)
    _hits[ip] = lst
    return True


def _load(cur, store, like=None):
    sql = "SELECT data FROM records WHERE store = " + PH
    args = [store]
    if like:
        sql += " AND data LIKE " + PH
        args.append(like)
    cur.execute(sql, tuple(args))
    return [json.loads(r[0]) for r in cur.fetchall()]


def _visits(d, now):
    if d.get("active") is False:
        return False
    if (now.weekday() + 1) % 7 not in (d.get("dow") or []):
        return False
    weeks = d.get("weeks") or []
    if weeks:
        return ((now.day - 1) // 7 + 1) in weeks
    return True


def _start_minutes(timing):
    if not timing or "," in timing or re.search(r"(mon|tue|wed|thu|fri|sat|sun)", timing, re.I):
        return None
    m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(AM|PM)", timing, re.I)
    if not m:
        return None
    h = int(m.group(1)) % 12
    if m.group(3).upper() == "PM":
        h += 12
    return h * 60 + int(m.group(2) or 0)


def _fmt_time(mins):
    h, mi = (mins // 60) % 24, mins % 60
    return "%d:%02d %s" % (h % 12 or 12, mi, "AM" if h < 12 else "PM")


@app.route("/book")
def book_page():
    resp = send_from_directory(WEB_DIR, "book.html")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.route("/qr.svg")
def qr_image():
    url = request.host_url.rstrip("/") + "/book"
    return Response(qr_svg(url), mimetype="image/svg+xml", headers={"Cache-Control": "public, max-age=3600"})


@app.route("/api/public/doctors")
def public_doctors():
    now = datetime.now(IST)
    conn = get_db()
    cur = conn.cursor()
    docs = _load(cur, "doctors")
    conn.close()
    out = [
        {"id": d["id"], "name": d.get("name", ""), "spec": d.get("spec", ""), "deg": d.get("deg", ""),
         "fee": d.get("fee", 0), "timing": d.get("timing", "")}
        for d in docs if _visits(d, now)
    ]
    return jsonify({"date": now.strftime("%Y-%m-%d"), "doctors": out, "loaded": len(docs) > 0})


@app.route("/api/public/book", methods=["POST"])
def public_book():
    ip = request.remote_addr or "?"
    if not _throttle(ip):
        return jsonify({"error": "Too many tries. Please try again later."}), 429
    j = request.get_json(force=True, silent=True) or {}
    name = str(j.get("name", "")).strip()[:60]
    age = str(j.get("age", "")).strip()[:10]
    sex = j.get("sex") if j.get("sex") in ("Male", "Female", "Other") else "Male"
    guardian = str(j.get("guardian", "")).strip()[:60]
    phone = re.sub(r"\D", "", str(j.get("phone", "")))[-10:]
    if len(name) < 2 or not age or not re.match(r"^[6-9]\d{9}$", phone):
        return jsonify({"error": "Please enter name, age and a valid 10-digit mobile number."}), 400
    now = datetime.now(IST)
    today = now.strftime("%Y-%m-%d")
    conn = get_db()
    cur = conn.cursor()
    try:
        _lock(cur)
        docs = _load(cur, "doctors")
        doc = next((d for d in docs if d.get("id") == j.get("doctorId")), None)
        if not doc or not _visits(doc, now):
            conn.rollback()
            return jsonify({"error": "This doctor is not available today. Please choose another."}), 400
        toks = _load(cur, "tokens", '%"date": "' + today + '"%')
        if sum(1 for t in toks if t.get("phone") == phone and t.get("status") != "cancelled") >= 4:
            conn.rollback()
            return jsonify({"error": "Too many tokens from this number today. Please call the clinic."}), 429
        no = max([t.get("no", 0) for t in toks if t.get("doctorId") == doc["id"]] or [0]) + 1
        start = _start_minutes(doc.get("timing"))
        slot = int(doc.get("slot") or 10)
        approx = _fmt_time(start + (no - 1) * slot) if start is not None else ""
        ts = _next_ts(cur)
        tk = {
            "id": "tk" + secrets.token_hex(5), "date": today, "doctorId": doc["id"],
            "doctorName": doc.get("name", ""), "doctorDeg": doc.get("deg", ""), "doctorSpec": doc.get("spec", ""),
            "fee": doc.get("fee", 0), "no": no, "approx": approx, "name": name, "age": age, "sex": sex,
            "phone": phone, "guardian": guardian, "status": "unpaid", "createdAt": int(time.time() * 1000), "src": "qr", "_u": ts,
        }
        cur.execute(
            "INSERT INTO records (store, id, data, updated_at) VALUES (" + ",".join([PH] * 4) + ")",
            ("tokens", tk["id"], json.dumps(tk), ts),
        )
        conn.commit()
    finally:
        conn.close()
    return jsonify(tk)


@app.route("/api/public/token/<tid>")
def public_token(tid):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT data FROM records WHERE store = " + PH + " AND id = " + PH, ("tokens", tid))
    row = cur.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "not found"}), 404
    return jsonify(json.loads(row[0]))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
