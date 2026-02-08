# modules/auth.py
# modules/auth.py
import os, json
from typing import Dict, Any, Tuple
from .security import verify_password, hash_password, LoginPolicy, now_ts

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
USERS_PATH = os.path.join(DATA_DIR, "users.json")

DEFAULT_USERS = {
    "admin":  {"role": "admin",  "password": "admin123"},
    "auditor":{"role": "auditor","password": "audit456"},
    "usuario":{"role": "usuario","password": "user789"},
}

def normalize_username(u: str) -> str:
    return (u or "").strip().lower()

def ensure_users_file(force: bool = False):
    os.makedirs(DATA_DIR, exist_ok=True)
    if force or not os.path.exists(USERS_PATH):
        users = {}
        for uname, info in DEFAULT_USERS.items():
            users[uname] = {"role": info["role"], **hash_password(info["password"])}
        with open(USERS_PATH, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=2, ensure_ascii=False)

def load_users() -> Dict[str, Any]:
    ensure_users_file(force=False)
    try:
        with open(USERS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # si el archivo se dañó, lo regeneramos
        ensure_users_file(force=True)
        with open(USERS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

def save_users(users: Dict[str, Any]):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(USERS_PATH, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)

def authenticate(username: str, password: str) -> Tuple[bool, str]:
    users = load_users()
    u = normalize_username(username)
    if u not in users:
        return False, ""
    if verify_password(password or "", users[u]):
        return True, users[u].get("role", "usuario")
    return False, ""

def upsert_user(username: str, password: str, role: str = "usuario"):
    users = load_users()
    u = normalize_username(username)
    users[u] = {"role": role, **hash_password(password)}
    save_users(users)

def reset_users():
    """Restablece usuarios por defecto (local)."""
    ensure_users_file(force=True)

def login_guard(state: dict, policy: LoginPolicy):
    # bloqueo
    lock_until = state.get("lock_until", 0.0)
    if lock_until and now_ts() < lock_until:
        remaining = int(lock_until - now_ts())
        return False, f"Cuenta bloqueada temporalmente. Intenta en {remaining}s."

    # expiración por inactividad
    last = state.get("last_activity", 0.0)
    if state.get("usuario") and last and (now_ts() - last) > policy.session_idle_seconds:
        user = state.get("usuario")
        state.clear()
        return False, f"Sesión de {user} expirada por inactividad. Inicia sesión nuevamente."

    return True, ""