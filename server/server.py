from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime
import requests

app = Flask(__name__)
app.secret_key = "securelab-secret-key-change-this"
DB = "securelab.db"

ADMIN_USER = "admin"
ADMIN_PASS_HASH = generate_password_hash("admin123")

def trigger_camera_alert(hostname, reason):
    CAMERA_ENDPOINT = "http://127.0.0.1:9000/camera-alert"

    payload = {
        "system": hostname,
        "reason": reason,
        "time": str(datetime.now())
    }

    try:
        requests.post(CAMERA_ENDPOINT, json=payload, timeout=3)

        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute(
            "UPDATE camera_status SET state=?, last_trigger=? WHERE id=1",
            ("VIGILANT", str(datetime.now()))
        )
        conn.commit()
        conn.close()

        print("[CCTV] Camera set to VIGILANT")

    except Exception as e:
        print("[CCTV] Failed:", e)


def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hostname TEXT,
            event TEXT,
            timestamp TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS systems (
            hostname TEXT PRIMARY KEY,
            last_seen REAL,
            system_group TEXT DEFAULT 'Ungrouped'
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS camera_status (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            state TEXT,
            last_trigger TEXT
        )
    """)

# ensure single row exists
    c.execute("""
        INSERT OR IGNORE INTO camera_status (id, state, last_trigger)
        VALUES (1, 'NORMAL', '')
    """)

    conn.commit()
    conn.close()

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username == ADMIN_USER and check_password_hash(ADMIN_PASS_HASH, password):
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        else:
            return "Invalid credentials", 403

    return """
    <h2>SecureLab Admin Login</h2>
    <form method="post">
        Username: <input name="username"><br><br>
        Password: <input name="password" type="password"><br><br>
        <button type="submit">Login</button>
    </form>
    """

@app.route("/event", methods=["POST"])
def receive_event():
    data = request.json
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        "INSERT INTO events (hostname, event, timestamp) VALUES (?, ?, ?)",
        (data["hostname"], data["event"], str(datetime.now()))
    )
    conn.commit()
    conn.close()
    
    if "ALERT" in data["event"]:
        trigger_camera_alert(data["hostname"], data["event"])

    return jsonify({"status": "ok"})

@app.route("/heartbeat", methods=["POST"])
def heartbeat():
    data = request.json
    hostname = data["hostname"]

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
        INSERT INTO systems (hostname, last_seen)
        VALUES (?, ?)
        ON CONFLICT(hostname)
        DO UPDATE SET last_seen=excluded.last_seen
    """, (hostname, datetime.now().timestamp()))

    conn.commit()
    conn.close()

    return jsonify({"status": "alive"})

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

def time_ago(seconds):
    minutes = int(seconds // 60)
    hours = int(minutes // 60)
    days = int(hours // 24)

    if days > 0:
        return f"{days} days ago"
    elif hours > 0:
        return f"{hours} hours ago"
    elif minutes > 0:
        return f"{minutes} minutes ago"
    else:
        return "just now"

@app.route("/")
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
     
    CHECKIN_LIMIT = 2 * 24 * 60 * 60  # 2 days in seconds
 
    show_offline_only = request.args.get("offline") == "1"
    
    show_alerts_only = request.args.get("alerts") == "1"

    selected_group = request.args.get("group", "ALL")

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    groups = c.execute(
        "SELECT DISTINCT system_group FROM systems"
    ).fetchall()

    groups = [g[0] for g in groups]

    if selected_group == "ALL":
        systems = c.execute(
            "SELECT hostname, last_seen FROM systems"
        ).fetchall()
    else:
        systems = c.execute(
            "SELECT hostname, last_seen FROM systems WHERE system_group = ?",
            (selected_group,)
        ).fetchall()

    events = c.execute(
        "SELECT hostname, event, timestamp FROM events ORDER BY id DESC LIMIT 50"
    ).fetchall()

    filtered_events = []

    for e in events:
        if show_alerts_only and "ALERT" not in e[1]:
            continue
        filtered_events.append(e)


    conn.close()

    status = []
    now = datetime.now().timestamp()

    for host, last_seen in systems:
        age = now - last_seen
        last_seen_text = time_ago(age)

        if age < 60:
            state = "ONLINE"
        elif age < CHECKIN_LIMIT:
            state = "OFFLINE"
        else:
            state = "STALE"

        if show_offline_only and state == "ONLINE":
            continue

        status.append((host, state, last_seen_text))
       
      
    total_systems = len(status)
    online_systems = sum(1 for s in status if s[1] == "ONLINE")
    offline_systems = sum(1 for s in status if s[1] == "OFFLINE")
    stale_systems = sum(1 for s in status if s[1] == "STALE")


    alert_count = sum(1 for e in events if "ALERT" in e[1])
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    camera = c.execute(
        "SELECT state FROM camera_status WHERE id=1"
    ).fetchone()

    current_camera_state = camera[0]

# Trigger camera ONLY ONCE
    if stale_systems > 0 and current_camera_state != "VIGILANT":
        trigger_camera_alert(
            "MULTIPLE SYSTEMS",
            "System offline beyond allowed window"
        )

# Reset camera when everything is safe
    if stale_systems == 0 and offline_systems == 0 and current_camera_state != "NORMAL":
        c.execute(
            "UPDATE camera_status SET state='NORMAL' WHERE id=1"
        )
        conn.commit()

    conn.close()
# ================= CAMERA STATE =================
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    camera = c.execute(
        "SELECT state, last_trigger FROM camera_status WHERE id=1"
    ).fetchone()

    if camera:
        camera_state = camera[0]
        camera_last_trigger = camera[1]
    else:
        camera_state = "UNKNOWN"
        camera_last_trigger = ""

    conn.close()
# ===============================================

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>SecureLab Dashboard</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
            }
            .header {
                background: #1f2937;
                color: white;
                padding: 15px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .card-container {
                display: flex;
                gap: 20px;
                margin-top: 20px;
                flex-wrap: wrap;
            }
            .stale {
                color: orange;
                font-weight: bold;
            }
 
            .card {
                background: white;
                padding: 15px;
                border-radius: 8px;
                width: 220px;
                box-shadow: 0 2px 6px rgba(0,0,0,0.1);
            }
            .online {
                color: green;
                font-weight: bold;
            }
            .offline {
               color: red;
               font-weight: bold;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
                background: white;
            }
            th, td {
                padding: 10px;
                border-bottom: 1px solid #ddd;
                text-align: left;
            }
            th {
                background: #e5e7eb;
            }
            .alert {
                color: red;
                font-weight: bold;
            }
            .info {
                color: #374151;
            }
        </style>    
        <script>
            setTimeout(function() {
                window.location.href = window.location.href;
            }, 5000;
            
        </script>

    </head>

    <body>
    <div style="margin-top: 15px;">
        <a href="/" style="margin-right: 10px;">🔁 Show All</a>
        <a href="/?offline=1" style="margin-right: 10px;">🔴 Offline Only</a>
        <a href="/?alerts=1">🚨 Alerts Only</a>
    </div>


    <div class="header">
        <h2>🔐 SecureLab – Central Security Dashboard</h2>
        <div>
            <a href="/systems" style="color:white; margin-right:15px;">
                🛠 Manage Systems
            </a>
            <a href="/logout" style="color:white;">
                Logout
            </a>
        </div>
    </div>
 
    <form method="get" style="margin: 15px 0;">
         <label><strong>Filter by Group:</strong></label>
         <select name="group" onchange="this.form.submit()">
             <option value="ALL">All Groups</option>
             {% for g in groups %}
             <option value="{{ g }}" {% if g == selected_group %}selected{% endif %}>
                 {{ g }}
             </option>
             {% endfor %}
         </select>
    </form>
 
    <div class="card-container">
        <div class="card">
            <h4>🖥️ Total Systems</h4>
            <p><strong>{{ total_systems }}</strong></p>
        </div>

        <div class="card">
            <h4>🟢 Online</h4>
            <p class="online"><strong>{{ online_systems }}</strong></p>
        </div>

        <div class="card">
            <h4>🔴 Offline</h4>
            <p class="offline"><strong>{{ offline_systems }}</strong></p>
        </div>

        <div class="card">
            <h4>🚨 Alerts</h4>
            <p class="alert"><strong>{{ alert_count }}</strong></p>
        </div>
    </div>
    <div class="card">
        <h4>⚠️ Stale</h4>
        <p class="stale"><strong>{{ stale_systems }}</strong></p>
    </div>
    <div class="card">
        <h4>📷 Camera Status</h4>
        <p style="font-weight:bold;
           color: {{ 'red' if camera_state=='VIGILANT' else 'green' }}">
            {{ camera_state }}
        </p>
        {% if camera_last_trigger %}
        <p style="font-size:12px; color:#6b7280;">
            Last alert: {{ camera_last_trigger }}
        </p>
        {% endif %}
    </div>

    <h3>System Status</h3>
    <div class="card-container">
        {% for s in status %}
        <div class="card">
            <h4>
                <a href="/system/{{ s[0] }}"
                   style="text-decoration:none;
                          color:#2563eb;
                          cursor:pointer;
                          display:inline-block;">
                   {{ s[0] }}
                </a>
            </h4>

            <p class="{{
                'online' if s[1]=='ONLINE'
                else 'stale' if s[1]=='STALE'
                else 'offline'
             }}">
                {{s[1]}}
            </p>
            <p style="font-size:12px; color:#6b7280;">
                Last seen: {{s[2]}}
            </p>
        </div>
        {% endfor %}

    </div>
 
    <h3>Recent Security Events</h3>
    <table>
        <tr>
             <th>System</th>
             <th>Event</th>
             <th>Time</th>
        </tr>
        {% for e in events %}
        <tr>
            <td>{{e[0]}}</td>
            <td class="{{ 'alert' if 'ALERT' in e[1] else 'info' }}">
                {{e[1]}}
            </td>
            <td>{{e[2]}}</td>
        </tr>
        {% endfor %}
    </table>

    </body>
    </html>
    """

    return render_template_string(
       html,
       status=status,
       events=filtered_events,
       total_systems=total_systems,
       online_systems=online_systems,
       offline_systems=offline_systems,
       groups=groups,
       selected_group=selected_group,
       stale_systems=stale_systems,
       alert_count=alert_count,
       camera_state=camera_state,
       camera_last_trigger=camera_last_trigger   
   )
@app.route("/system/<hostname>")
def system_detail(hostname):
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    system = c.execute(
        "SELECT hostname, last_seen, system_group FROM systems WHERE hostname = ?",
        (hostname,)
    ).fetchone()

    events = c.execute(
        "SELECT event, timestamp FROM events WHERE hostname = ? ORDER BY id DESC LIMIT 20",
        (hostname,)
    ).fetchall()

    conn.close()

    if not system:
        return "System not found", 404

    now = datetime.now().timestamp()
    age = now - system[1]

    if age < 60:
        state = "ONLINE"
    elif age < 2 * 24 * 60 * 60:
        state = "OFFLINE"
    else:
        state = "STALE"

    last_seen_text = time_ago(age)

    html = """
    <html>
    <head>
        <title>System Details</title>
        <style>
            body { font-family: Arial; padding: 20px; }
            .online { color: green; font-weight: bold; }
            .offline { color: red; font-weight: bold; }
            .stale { color: orange; font-weight: bold; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { padding: 10px; border-bottom: 1px solid #ddd; }
            th { background: #f3f4f6; }
        </style>
    </head>
    <body>

    <a href="/">⬅ Back to Dashboard</a>

    <h2>🖥️ {{ hostname }}</h2>

    <p>
        Status:
        <span class="{{ state|lower }}">{{ state }}</span>
    </p>

    <p>Group: <strong>{{ group }}</strong></p>
    <p>Last seen: {{ last_seen }}</p>

    <h3>Recent Events</h3>

    {% if events %}
    <table>
        <tr>
            <th>Event</th>
            <th>Time</th>
        </tr>
        {% for e in events %}
        <tr>
            <td>{{ e[0] }}</td>
            <td>{{ e[1] }}</td>
        </tr>
        {% endfor %}
    </table>
    {% else %}
        <p>No events recorded.</p>
    {% endif %}

    </body>
    </html>
    """

    return render_template_string(
        html,
        hostname=system[0],
        group=system[2],
        state=state,
        last_seen=last_seen_text,
        events=events
    )
   
@app.route("/systems")
def systems_page():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB)
    c = conn.cursor()
 
    groups = c.execute(
        "SELECT DISTINCT system_group FROM systems"
    ).fetchall()

    groups = [g[0] for g in groups]
  
    systems = c.execute(
        "SELECT hostname, system_group, last_seen FROM systems"
    ).fetchall()

    conn.close()

    html = """
    <html>
    <head>
        <title>System Management</title>
        <style>
            body { font-family: Arial; padding: 20px; }
            table { width: 100%; border-collapse: collapse; }
            th, td { padding: 10px; border-bottom: 1px solid #ddd; }
            th { background: #f3f4f6; }
        </style>
    </head>
    <body>

    <h2>🖥️ System Management</h2>
    <a href="/">⬅ Back to Dashboard</a>

    <table>
        <tr>
            <th>Hostname</th>
            <th>Group</th>
            <th>Last Seen</th>
        </tr>

        {% for s in systems %}
        <tr>
            <td>{{ s[0] }}</td>
            <td>
                <form method="post" action="/update-group" style="display:flex; gap:6px;">
                    <input type="hidden" name="hostname" value="{{ s[0] }}">

                    <select name="group">
                        {% for g in groups %}
                        <option value="{{ g }}" {% if g == s[1] %}selected{% endif %}>
                           {{ g }}
                        </option>
                        {% endfor %}
                    </select>

                    <input type="text"
                           name="new_group"
                           placeholder="New group"
                           style="width:120px;">

                    <button type="submit">Save</button>
               </form>
           </td>

            <td>{{ s[2] }}</td>
        </tr>
        {% endfor %}
    </table>

    </body>
    </html>
    """

    return render_template_string(html, systems=systems, groups=groups)

@app.route("/update-group", methods=["POST"])
def update_group():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    hostname = request.form.get("hostname")
    selected_group = request.form.get("group")
    new_group = request.form.get("new_group")

    final_group = new_group if new_group else selected_group

    if not final_group:
        return redirect(url_for("systems_page"))

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute(
        "UPDATE systems SET system_group = ? WHERE hostname = ?",
        (final_group, hostname)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("systems_page", _t=datetime.now().timestamp()))

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)
