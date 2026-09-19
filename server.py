import os
import time
from flask import Flask, jsonify, send_from_directory

app = Flask(__name__)

@app.route("/")
def home():
    return send_from_directory(".", "index.html")

@app.route("/api/dashboard")
def dashboard():
    return jsonify({
        "news": [],
        "status": "Backend connected",
        "server_time": int(time.time())
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
