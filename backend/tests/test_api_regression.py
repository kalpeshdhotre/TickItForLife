import os
import uuid
import requests
from dotenv import dotenv_values

BASE_URL = (os.environ.get("EXPO_BACKEND_URL") or os.environ.get("EXPO_PUBLIC_BACKEND_URL") or dotenv_values("/app/frontend/.env").get("EXPO_PUBLIC_BACKEND_URL")).rstrip("/")

def test_auth_habit_entry_reorder_flow():
    email = f"TEST_{uuid.uuid4().hex}@example.com"
    password = "RhythmTest123!"
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/register", json={"email": email, "password": password, "name": "TEST QA"})
    assert r.status_code == 200 and r.json()["user"]["email"] == email.lower()
    token = r.json()["session_token"]
    s.headers["Authorization"] = f"Bearer {token}"
    assert s.get(f"{BASE_URL}/api/auth/me").json()["user"]["email"] == email.lower()
    habit = s.post(f"{BASE_URL}/api/habits", json={"name":"TEST Water", "icon":"droplet", "habit_type":"measurable", "target":3, "unit":"L"})
    assert habit.status_code == 200
    hid = habit.json()["habit_id"]
    entry = s.put(f"{BASE_URL}/api/habits/{hid}/entries", json={"date":"2026-08-15", "value":3})
    assert entry.status_code == 200 and entry.json()["completed"] is True
    listed = s.get(f"{BASE_URL}/api/habits").json()
    assert listed[0]["entries"][0]["value"] == 3
    assert s.patch(f"{BASE_URL}/api/habits/reorder", json=[hid]).json()["ok"] is True