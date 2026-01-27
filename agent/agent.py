import pyudev
import subprocess
import json
import os
from datetime import datetime
import time
import socket
import requests
import threading

last_add_time = {}
last_removal_time = {}
DEBOUNCE_SECONDS = 2
SERVER_URL = "http://127.0.0.1:5000/event"
HOSTNAME = socket.gethostname()

BASELINE_FILE = "baseline.json"
LOG_FILE = "events.log"
MAINTENANCE_FILE = "maintenance.json"


def log_event(message):
    timestamp = datetime.now()
    with open(LOG_FILE, "a") as f:
        f.write(f"{timestamp} - {message}\n")

    try:
        requests.post(
            SERVER_URL,
            json={
                "hostname": HOSTNAME,
                "event": message
            },
            timeout=2
        )
    except:
        pass

def normalize_name(device):
    return (
        device.get("ID_MODEL")
        or device.get("NAME")
        or "Unknown Device"
    )

def collect_current_devices():
    context = pyudev.Context()
    devices = set()

    for device in context.list_devices():
        if device.subsystem in ["usb", "input"]:
            name = normalize_name(device)
            if name != "Unknown Device":
                devices.add((device.subsystem, name))

    return list(devices)

def create_baseline():
    devices = collect_current_devices()
    data = {
        "created_at": str(datetime.now()),
        "trusted_devices": devices
    }

    with open(BASELINE_FILE, "w") as f:
        json.dump(data, f, indent=4)

    print("[+] Baseline created with trusted devices")

def load_baseline():
    try:
        with open(BASELINE_FILE, "r") as f:
            data = json.load(f)
            return set(tuple(x) for x in data.get("trusted_devices", []))
    except (json.JSONDecodeError, FileNotFoundError):
        print("[!] Baseline corrupted or missing. Recreating baseline...")
        create_baseline()
        with open(BASELINE_FILE, "r") as f:
            data = json.load(f)
            return set(tuple(x) for x in data.get("trusted_devices", []))

lock_triggered = False

def lock_screen():
    global lock_triggered

    # Prevent repeated locking spam
    if lock_triggered:
        return

    try:
        output = subprocess.check_output(
            ["loginctl", "list-sessions", "--no-legend"],
            text=True
        )

        for line in output.strip().split("\n"):
            parts = line.split()
            if len(parts) < 1:
                continue

            session_id = parts[0]

            # Lock only graphical user sessions
            subprocess.run(
                ["loginctl", "lock-session", session_id],
                check=False
            )

        log_event("ACTION: Screen locked due to unauthorized device removal")
        lock_triggered = True

    except Exception as e:
        log_event(f"ERROR: Failed to lock screen - {e}")

def is_critical_input(device):
    name = normalize_name(device).lower()
    return any(x in name for x in ["keyboard", "mouse"])

def maintenance_active():
    if not os.path.exists(MAINTENANCE_FILE):
        return False

    try:
        with open(MAINTENANCE_FILE, "r") as f:
            data = json.load(f)

        expires_at = data.get("expires_at", 0)
        return time.time() < expires_at

    except Exception:
        return False

def send_heartbeat():
    try:
        requests.post(
            SERVER_URL.replace("/event", "/heartbeat"),
            json={"hostname": HOSTNAME},
            timeout=2
        )
    except:
        pass

def heartbeat_loop():
    while True:
        send_heartbeat()
        time.sleep(30)

def monitor_devices(trusted_devices):
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)

    print("[*] Monitoring devices with baseline enforcement...")

    for action, device in monitor:
        if device.subsystem not in ["usb", "input"]:
            continue

        name = normalize_name(device)
        if name == "Unknown Device":
            continue

        key = (device.subsystem, name)

        if action == "remove" and key in trusted_devices:
            now = time.time()
            last_time = last_removal_time.get(key, 0)

            if now - last_time < DEBOUNCE_SECONDS:
                continue

            last_removal_time[key] = now 

            msg = f"ALERT: TRUSTED DEVICE REMOVED [{device.subsystem}]: {name}"
            print(msg)
            log_event(msg)
            
            if is_critical_input(device):
                if maintenance_active():
                     log_event("INFO: Maintenance mode active - screen lock skipped")
                else:
                     lock_screen()

        elif action == "add" and key not in trusted_devices:
            msg = f"ALERT: UNAUTHORIZED DEVICE INSERTED [{device.subsystem}]: {name}"
            print(msg)
            log_event(msg)

        elif action == "add" and key in trusted_devices:
            now = time.time()
            last_time = last_add_time.get(key,0)

            if now - last_time < DEBOUNCE_SECONDS:
                continue

            last_add_time[key] = now

            global lock_triggered
            lock_triggered = False 

            msg = f"INFO: TRUSTED DEVICE RECONNECTED [{device.subsystem}]: {name}"
            print(msg)
            log_event(msg)

if __name__ == "__main__":
    if not os.path.exists(BASELINE_FILE):
        print("[!] No baseline found. Creating baseline (admin mode)...")
        create_baseline()

    log_event("INFO: Agent started successfully")

    threading.Thread(target=heartbeat_loop, daemon=True).start()

    trusted = load_baseline()
    monitor_devices(trusted)

