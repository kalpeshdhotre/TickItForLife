from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging
import os
import uuid

import bcrypt
import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI()
api_router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


class AuthInput(BaseModel):
    email: str
    password: str
    name: Optional[str] = None


class SessionInput(BaseModel):
    session_id: str


class HabitCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    icon: str = "check"
    habit_type: str = Field(pattern="^(boolean|measurable)$")
    target: Optional[float] = None
    unit: Optional[str] = None


class HabitUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=60)
    icon: Optional[str] = None
    target: Optional[float] = None
    unit: Optional[str] = None
    hidden: Optional[bool] = None


class EntryInput(BaseModel):
    date: str
    value: Optional[float] = None
    completed: Optional[bool] = None


def public_user(user: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user.get("name") or user["email"].split("@")[0].title(),
        "picture": user.get("picture"),
    }


async def make_session(user_id: str) -> str:
    token = uuid.uuid4().hex + uuid.uuid4().hex
    await db.user_sessions.insert_one({
        "session_token": token,
        "user_id": user_id,
        "created_at": now_iso(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
    })
    return token


async def current_user(request: Request) -> Dict[str, Any]:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    token = auth.split(" ", 1)[1].strip()
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=401, detail="Session expired")
    try:
        expiry = datetime.fromisoformat(session["expires_at"])
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if expiry < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Session expired")
    except (ValueError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid session")
    user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@app.on_event("startup")
async def startup_db():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id", unique=True)
    await db.user_sessions.create_index("session_token", unique=True)
    await db.user_sessions.create_index("expires_at", expireAfterSeconds=0)
    await db.habits.create_index([("user_id", 1), ("order", 1)])
    await db.entries.create_index([("user_id", 1), ("habit_id", 1), ("date", 1)], unique=True)


@api_router.get("/")
async def root():
    return {"message": "Rhythm Habit Tracker API"}


@api_router.post("/auth/register")
async def register(payload: AuthInput):
    email = payload.email.strip().lower()
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=409, detail="An account already exists for this email")
    user = {
        "user_id": new_id("user"),
        "email": email,
        "name": (payload.name or email.split("@")[0]).strip(),
        "password_hash": bcrypt.hashpw(payload.password.encode(), bcrypt.gensalt()).decode(),
        "created_at": now_iso(),
    }
    await db.users.insert_one(user.copy())
    return {"session_token": await make_session(user["user_id"]), "user": public_user(user)}


@api_router.post("/auth/login")
async def login(payload: AuthInput):
    user = await db.users.find_one({"email": payload.email.strip().lower()}, {"_id": 0})
    if not user or not user.get("password_hash") or not bcrypt.checkpw(payload.password.encode(), user["password_hash"].encode()):
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    return {"session_token": await make_session(user["user_id"]), "user": public_user(user)}


@api_router.post("/auth/session")
async def exchange_google_session(payload: SessionInput):
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            response = await http.get(
                "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
                headers={"X-Session-ID": payload.session_id},
            )
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Google session could not be verified")
        data = response.json()
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Google session exchange failed: %s", exc)
        raise HTTPException(status_code=401, detail="Google sign-in is unavailable")

    email = (data.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=401, detail="Google account email missing")
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        user = {
            "user_id": new_id("user"),
            "email": email,
            "name": data.get("name") or email.split("@")[0].title(),
            "picture": data.get("picture"),
            "created_at": now_iso(),
        }
        await db.users.insert_one(user.copy())
    else:
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"name": data.get("name") or user.get("name"), "picture": data.get("picture")}})
    token = data.get("session_token") or await make_session(user["user_id"])
    if data.get("session_token"):
        await db.user_sessions.insert_one({"session_token": token, "user_id": user["user_id"], "created_at": now_iso(), "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()})
    return {"session_token": token, "user": public_user(user)}


@api_router.get("/auth/me")
async def me(request: Request):
    return {"user": public_user(await current_user(request))}


@api_router.get("/habits")
async def list_habits(request: Request):
    user = await current_user(request)
    habits = await db.habits.find({"user_id": user["user_id"]}, {"_id": 0}).sort("order", 1).to_list(100)
    habit_ids = [habit["habit_id"] for habit in habits]
    entries = await db.entries.find({"user_id": user["user_id"], "habit_id": {"$in": habit_ids}}, {"_id": 0}).to_list(5000) if habit_ids else []
    grouped: Dict[str, List[Dict[str, Any]]] = {habit_id: [] for habit_id in habit_ids}
    for entry in entries:
        grouped.setdefault(entry["habit_id"], []).append(entry)
    return [{**habit, "entries": grouped.get(habit["habit_id"], [])} for habit in habits]


@api_router.post("/habits")
async def create_habit(payload: HabitCreate, request: Request):
    user = await current_user(request)
    count = await db.habits.count_documents({"user_id": user["user_id"]})
    habit = {
        "habit_id": new_id("habit"),
        "user_id": user["user_id"],
        "name": payload.name.strip(),
        "icon": payload.icon,
        "habit_type": payload.habit_type,
        "target": payload.target if payload.habit_type == "measurable" else None,
        "unit": payload.unit if payload.habit_type == "measurable" else None,
        "order": count,
        "created_at": now_iso(),
    }
    await db.habits.insert_one(habit.copy())
    return {**habit, "entries": []}


@api_router.patch("/habits/reorder")
async def reorder_habits(order: List[str], request: Request):
    user = await current_user(request)
    for position, habit_id in enumerate(order):
        await db.habits.update_one({"habit_id": habit_id, "user_id": user["user_id"]}, {"$set": {"order": position}})
    return {"ok": True}


@api_router.patch("/habits/{habit_id}")
async def update_habit(habit_id: str, payload: HabitUpdate, request: Request):
    user = await current_user(request)
    update = {key: value for key, value in payload.model_dump().items() if value is not None}
    if not update:
        raise HTTPException(status_code=400, detail="Nothing to update")
    result = await db.habits.update_one({"habit_id": habit_id, "user_id": user["user_id"]}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Habit not found")
    habit = await db.habits.find_one({"habit_id": habit_id, "user_id": user["user_id"]}, {"_id": 0})
    entries = await db.entries.find({"habit_id": habit_id, "user_id": user["user_id"]}, {"_id": 0}).to_list(5000)
    return {**habit, "entries": entries}


@api_router.delete("/habits/{habit_id}")
async def delete_habit(habit_id: str, request: Request):
    user = await current_user(request)
    result = await db.habits.delete_one({"habit_id": habit_id, "user_id": user["user_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Habit not found")
    await db.entries.delete_many({"habit_id": habit_id, "user_id": user["user_id"]})
    return {"ok": True}


@api_router.put("/habits/{habit_id}/entries")
async def save_entry(habit_id: str, payload: EntryInput, request: Request):
    user = await current_user(request)
    habit = await db.habits.find_one({"habit_id": habit_id, "user_id": user["user_id"]}, {"_id": 0})
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")
    if habit["habit_type"] == "boolean":
        value = None
        completed = bool(payload.completed)
    else:
        if payload.value is None or payload.value < 0:
            raise HTTPException(status_code=400, detail="Enter a valid value")
        value = payload.value
        completed = payload.value >= (habit.get("target") or 1)
    entry = {"user_id": user["user_id"], "habit_id": habit_id, "date": payload.date, "value": value, "completed": completed, "updated_at": now_iso()}
    if habit["habit_type"] == "boolean" and not completed:
        await db.entries.delete_one({"user_id": user["user_id"], "habit_id": habit_id, "date": payload.date})
        return {"deleted": True, "date": payload.date}
    await db.entries.replace_one({"user_id": user["user_id"], "habit_id": habit_id, "date": payload.date}, entry.copy(), upsert=True)
    return entry


app.include_router(api_router)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()