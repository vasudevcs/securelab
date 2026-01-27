# 🔐 SecureLab – Centralized Security Monitoring System

SecureLab is a lightweight **centralized security monitoring dashboard** built using **Python, Flask, and SQLite**.  
It simulates how SOC (Security Operations Center) teams monitor multiple endpoints for availability, alerts, and security events.

---

## 🚀 Features

- ✅ Central dashboard for all systems
- ❤️ Heartbeat monitoring (online / offline / stale)
- 🚨 Security event ingestion & alert filtering
- 🖥️ Per-system detail page with event history
- 🗂️ System grouping (Lab / Cyber / Test / etc.)
- 🔎 Filter systems by group, alerts, or status
- 🔐 Admin login (session-based authentication)
- ♻️ Auto-refreshing dashboard
- 🕒 Offline tolerance with **2-day routine check policy**

---

## 🏗️ Architecture

Agent (Client)
|
| POST /heartbeat
| POST /event
↓
SecureLab Server (Flask)
|
|-- SQLite Database
|-- Web Dashboard


---

## ⚙️ Tech Stack

- Python 3
- Flask
- SQLite
- HTML / CSS
- Git & GitHub

---

## 🛠️ Installation & Setup

### 1️⃣ Clone the repository
```bash
git clone https://github.com/vasudevcs/securelab.git
cd securelab

2️⃣ Create virtual environment

python3 -m venv venv
source venv/bin/activate

3️⃣ Install dependencies

pip install flask werkzeug

4️⃣ Run the server

python server.py

Server runs at:

http://localhost:5000

🔑 Default Login

    Username: admin

    Password: admin123

    ⚠️ Change this before production use.

🧪 Example Agent (Heartbeat)

import requests
requests.post(
    "http://SERVER_IP:5000/heartbeat",
    json={"hostname": "kali4"}
)

🧠 Design Decisions

    No instant alerts outside lab hours

    Systems must check in at least once every 2 days

    Extended offline → warning, not incident

    Designed for low-resource lab environments

📈 Future Improvements

    Email / Telegram alerts

    Agent authentication (API keys)

    Role-based access

    Export logs

    Docker support

    TLS support

👤 Author

Vasudev C S
Beginner Cybersecurity Practitioner
Built as a learning + portfolio project

