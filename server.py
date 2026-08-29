#!/usr/bin/env python3
"""PillPath local demonstration server. Python 3 standard library only."""
from __future__ import annotations
import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import time
from urllib.parse import parse_qs, urlparse
import secrets

ROOT = Path(__file__).parent
DATA_FILE = ROOT / "data.json"
PUBLIC = ROOT / "public"
OVERDUE_SECONDS = 30 * 60

def today_at(hour: int) -> int:
    import datetime
    now = datetime.datetime.now().astimezone()
    return int(now.replace(hour=hour, minute=0, second=0, microsecond=0).timestamp() * 1000)

def seed() -> dict:
    now = int(time() * 1000)
    return {
        "devices": [{"id": "PILL-001", "patient": "Margaret Wilson", "lastSeen": now, "online": True}],
        "medications": [
            {"id": "med-1", "deviceId": "PILL-001", "name": "Donepezil", "strength": "5 mg", "stock": 8, "lowAt": 10, "scheduledHour": 9},
            {"id": "med-2", "deviceId": "PILL-001", "name": "Vitamin D", "strength": "1,000 IU", "stock": 22, "lowAt": 7, "scheduledHour": 9},
        ],
        "doses": [
            {"id": "dose-1", "deviceId": "PILL-001", "medicationId": "med-1", "dueAt": now + 10 * 60 * 1000, "status": "pending", "dispensedAt": None},
            {"id": "dose-2", "deviceId": "PILL-001", "medicationId": "med-2", "dueAt": now + 10 * 60 * 1000, "status": "pending", "dispensedAt": None},
        ], "alerts": [],
        "alertSettings": {"browser": True, "email": True, "sms": False, "emailAddress": "care.team@example.test", "phoneNumber": "+64 21 000 0000"},
        "outbox": []
    }

def load() -> dict:
    try: data = json.loads(DATA_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError): return seed()
    defaults = seed()
    for key in ("alertSettings", "outbox"):
        data.setdefault(key, defaults[key])
    return data

db = load()
def save() -> None: DATA_FILE.write_text(json.dumps(db, indent=2))
def make_id(prefix: str) -> str: return f"{prefix}-{int(time()*1000)}-{secrets.token_hex(2)}"
def medication(medication_id: str): return next((m for m in db["medications"] if m["id"] == medication_id), None)
def alert(kind, message, device_id, medication_id=None):
    if not any(a["type"] == kind and a["deviceId"] == device_id and a.get("medicationId") == medication_id and not a["resolved"] for a in db["alerts"]):
        item = {"id": make_id("alert"), "type": kind, "message": message, "deviceId": device_id, "medicationId": medication_id, "createdAt": int(time()*1000), "resolved": False}
        db["alerts"].insert(0, item)
        settings = db["alertSettings"]
        for channel, destination in (("email", settings.get("emailAddress")), ("sms", settings.get("phoneNumber"))):
            if settings.get(channel) and destination:
                db["outbox"].insert(0, {"id": make_id("delivery"), "alertId": item["id"], "channel": channel, "destination": destination, "message": message, "createdAt": int(time()*1000), "status": "demo-queued"})
def evaluate():
    now = int(time() * 1000)
    for dose in db["doses"]:
        if dose["status"] == "pending" and now > dose["dueAt"] + OVERDUE_SECONDS * 1000:
            dose["status"] = "missed"; med = medication(dose["medicationId"])
            alert("missed-dose", f"Dose window missed: {med['name'] if med else 'Medication'} was not dispensed within 30 minutes.", dose["deviceId"], dose["medicationId"])
    for med in db["medications"]:
        if med["stock"] <= med["lowAt"]: alert("low-stock", f"Low stock: {med['name']} has {med['stock']} doses remaining.", med["deviceId"], med["id"])
    save()

class App(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs): super().__init__(*args, directory=str(PUBLIC), **kwargs)
    def log_message(self, fmt, *args): print("[PillPath]", fmt % args)
    def send_json(self, data, status=HTTPStatus.OK):
        encoded = json.dumps(data).encode(); self.send_response(status); self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(encoded))); self.end_headers(); self.wfile.write(encoded)
    def read_json(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if not raw: return {}
        try: return json.loads(raw)
        except (ValueError, TypeError): raise ValueError("Invalid JSON")
    def do_GET(self):
        route = urlparse(self.path).path
        if route == "/api/dashboard":
            evaluate(); return self.send_json({**db, "generatedAt": int(time()*1000), "overdueAfterMinutes": 30})
        if route == "/api/device/next-dose":
            device_id = parse_qs(urlparse(self.path).query).get("deviceId", [""])[0]
            dose = next((d for d in sorted(db["doses"], key=lambda x:x["dueAt"]) if d["deviceId"] == device_id and d["status"] == "pending"), None)
            return self.send_json({"dose": dose})
        if route == "/api/alert-settings": return self.send_json({"settings": db["alertSettings"], "outbox": db["outbox"][:10]})
        if route == "/": self.path = "/index.html"
        return super().do_GET()
    def do_POST(self): self.handle_write()
    def do_PATCH(self): self.handle_write()
    def handle_write(self):
        global db
        route = urlparse(self.path).path
        try:
            payload = self.read_json()
            if self.command == "POST" and route == "/api/device/heartbeat":
                device = next((d for d in db["devices"] if d["id"] == payload.get("deviceId")), None)
                if not device:
                    device = {"id": payload.get("deviceId"), "patient": payload.get("patient", "Unassigned patient"), "lastSeen": 0, "online": True}; db["devices"].append(device)
                device.update(lastSeen=int(time()*1000), online=True); save(); return self.send_json({"ok": True, "serverTime": int(time()*1000)})
            if self.command == "POST" and route == "/api/device/dispense":
                dose = next((d for d in db["doses"] if d["id"] == payload.get("doseId") and d["deviceId"] == payload.get("deviceId")), None)
                if not dose or dose["status"] != "pending": return self.send_json({"error": "No pending dose matches this request."}, HTTPStatus.CONFLICT)
                dose.update(status="dispensed", dispensedAt=int(time()*1000)); med = medication(dose["medicationId"])
                if med: med["stock"] = max(0, med["stock"] - 1)
                for a in db["alerts"]:
                    if a["type"] == "missed-dose" and a.get("medicationId") == dose["medicationId"]: a["resolved"] = True
                evaluate(); return self.send_json({"ok": True, "dose": dose, "medication": med})
            if self.command == "POST" and route == "/api/doses":
                med = medication(payload.get("medicationId")); due = payload.get("dueAt")
                if not med or not isinstance(due, (int, float)): return self.send_json({"error": "medicationId and dueAt are required."}, HTTPStatus.BAD_REQUEST)
                dose = {"id": make_id("dose"), "deviceId": med["deviceId"], "medicationId": med["id"], "dueAt": int(due), "status": "pending", "dispensedAt": None}; db["doses"].append(dose); save(); return self.send_json(dose, HTTPStatus.CREATED)
            if self.command == "PATCH" and route.startswith("/api/medications/"):
                med = medication(route.rsplit("/", 1)[-1]); stock = payload.get("stock")
                if not med or not isinstance(stock, int): return self.send_json({"error": "A whole-number stock value is required."}, HTTPStatus.BAD_REQUEST)
                med["stock"] = max(0, stock); evaluate(); return self.send_json(med)
            if self.command == "POST" and route.startswith("/api/alerts/") and route.endswith("/resolve"):
                alert_id = route.split("/")[3]; item = next((a for a in db["alerts"] if a["id"] == alert_id), None)
                if not item: return self.send_json({"error": "Alert not found."}, HTTPStatus.NOT_FOUND)
                item["resolved"] = True; save(); return self.send_json(item)
            if self.command == "PATCH" and route == "/api/alert-settings":
                allowed = {"browser", "email", "sms", "emailAddress", "phoneNumber"}
                for key in allowed:
                    if key in payload: db["alertSettings"][key] = payload[key]
                save(); return self.send_json({"settings": db["alertSettings"]})
            if self.command == "POST" and route == "/api/alerts/test":
                alert("test-alert", "Test alert generated by the care portal. No clinical action is required.", "PILL-001")
                save(); return self.send_json({"ok": True, "alert": db["alerts"][0]})
            if self.command == "POST" and route == "/api/demo/reset": db = seed(); save(); evaluate(); return self.send_json(db)
            self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        except ValueError as e: self.send_json({"error": str(e)}, HTTPStatus.BAD_REQUEST)

if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", 3000), App)
    print("PillPath portal listening on http://localhost:3000")
    server.serve_forever()
