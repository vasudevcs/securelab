from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

@app.route("/camera-alert", methods=["POST"])
def camera_alert():
    data = request.json

    system = data.get("system")
    reason = data.get("reason")
    time = data.get("time")

    print("\n🚨 CCTV ALERT RECEIVED 🚨")
    print(f"📍 System   : {system}")
    print(f"⚠️  Reason  : {reason}")
    print(f"🕒 Time    : {time}")
    print("🎥 Camera status: RECORDING STARTED")
    print("🔴 Vigilant mode ON\n")

    return jsonify({"status": "camera_recording"})

if __name__ == "__main__":
    print("📷 Camera Simulator running on port 9000")
    app.run(host="0.0.0.0", port=9000)

