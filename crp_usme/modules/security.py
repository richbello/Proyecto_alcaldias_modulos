# modules/security.py
import time, hmac, hashlib, secrets
from dataclasses import dataclass
from typing import Dict

PBKDF2_ITERS = 210_000
HASH_ALG = "sha256"

def hash_password(password: str, salt: bytes | None = None) -> Dict[str, str]:
    if salt is None:
        salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac(HASH_ALG, password.encode("utf-8"), salt, PBKDF2_ITERS, dklen=32)
    return {"salt": salt.hex(), "hash": dk.hex(), "iters": str(PBKDF2_ITERS), "algo": f"pbkdf2_{HASH_ALG}"}

def verify_password(password: str, stored: Dict[str, str]) -> bool:
    try:
        salt = bytes.fromhex(stored["salt"])
        iters = int(stored.get("iters", PBKDF2_ITERS))
        dk = hashlib.pbkdf2_hmac(HASH_ALG, password.encode("utf-8"), salt, iters, dklen=32)
        return hmac.compare_digest(dk.hex(), stored["hash"])
    except Exception:
        return False

def now_ts() -> float:
    return time.time()

@dataclass
class LoginPolicy:
    max_attempts: int = 5
    lock_seconds: int = 60
    session_idle_seconds: int = 20 * 60