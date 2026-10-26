# Books the demo day's patients through the time-shifted API, for recording only.
# The dates match DEMO_NOW in make-video.sh and DEMO_START in common.js.
import json, sys, urllib.request
API = "http://localhost:8001/api"
env = dict(l.rstrip("\n").split("=", 1) for l in open(sys.argv[1]) if "=" in l and not l.startswith("#"))

def call(method, path, body=None, token=None):
    req = urllib.request.Request(API + path, json.dumps(body).encode() if body is not None else None, method=method,
                                 headers={"content-type": "application/json", **({"authorization": f"Bearer {token}"} if token else {})})
    return json.load(urllib.request.urlopen(req))

token = call("POST", "/auth/login", {"username": env["CLINIC_ADMIN_USERNAME"], "password": env["CLINIC_ADMIN_PASSWORD"]})["access_token"]
patients = call("GET", "/patients?limit=100", token=token)
items = patients["items"] if isinstance(patients, dict) else patients
by_name = {p["full_name"]: p["id"] for p in items}
doctors = {d["display_name"]: d["id"] for d in call("GET", "/doctors")}
plan = [
    ("Dr. Kasun Wickramasinghe", "2026-10-26T08:00:00+05:30", ["Arjun Selvarajah", "Lakshmi Nadarajah", "Kumari Silva"]),
    ("Dr. Ayesha Fernando", "2026-10-26T17:00:00+05:30", ["Tharindu Bandara", "Arjun Selvarajah", "Nimal Perera", "Kumari Silva", "Mohamed Imran"]),
]
for doctor, start, names in plan:
    for name in names:
        a = call("POST", "/appointments", {"doctor_id": doctors[doctor], "patient_id": by_name[name], "start_at": start}, token)
        print(doctor, "No.", a.get("appointment_number"), name)
