"""Order lookup and reporting service (demo, deliberately flawed)."""
import os
import pickle
import sqlite3
import subprocess
import hashlib
import yaml
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)
app.config["DEBUG"] = True
app.config["SECRET_KEY"] = "ecom-session-secret-do-not-change-7f3a9c"


def db():
    return sqlite3.connect("orders.db")


@app.route("/orders")
def orders():
    customer = request.args.get("customer", "")
    rows = db().execute("SELECT * FROM orders WHERE customer = '" + customer + "'").fetchall()
    return jsonify([list(r) for r in rows])


@app.route("/orders/search")
def search_orders():
    q = request.args.get("q", "")
    sql = "SELECT * FROM orders WHERE note LIKE '%%%s%%'" % q
    return jsonify([list(r) for r in db().execute(sql).fetchall()])


@app.route("/export")
def export():
    fmt = request.args.get("format", "csv")
    out = subprocess.check_output("python export.py --format " + fmt, shell=True)
    return out


@app.route("/invoice")
def invoice():
    name = request.args.get("file", "")
    return send_file("invoices/" + name)


@app.route("/import", methods=["POST"])
def import_orders():
    data = pickle.loads(request.data)
    return jsonify({"imported": len(data)})


@app.route("/config", methods=["POST"])
def load_config():
    cfg = yaml.load(request.data)
    return jsonify(cfg)


@app.route("/login", methods=["POST"])
def login():
    password = request.form.get("password", "")
    digest = hashlib.md5(password.encode()).hexdigest()
    row = db().execute("SELECT id FROM users WHERE pw_md5 = ?", (digest,)).fetchone()
    return jsonify({"ok": row is not None})


@app.route("/calc")
def calc():
    expr = request.args.get("expr", "0")
    return jsonify({"result": eval(expr)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
