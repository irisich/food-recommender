"""
auth.py — Аутентификация пользователей NutriRec
================================================
Пароли хранятся как PBKDF2-SHA256 хеш с солью.
Данные пользователей: profiles/_users.json
"""

import hashlib
import json
import os
from pathlib import Path

from profiles import PROFILES_DIR, save_profile, load_profile

USERS_FILE = PROFILES_DIR / "_users.json"


# ─── Внутренние helpers ───────────────────────────────────────────────────────

def _load_users() -> dict:
    PROFILES_DIR.mkdir(exist_ok=True)
    if USERS_FILE.exists():
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_users(users: dict) -> None:
    PROFILES_DIR.mkdir(exist_ok=True)
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


# ─── Пароли ───────────────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    """PBKDF2-SHA256: <hex_salt>:<hex_dk>"""
    salt = os.urandom(16).hex()
    dk   = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                salt.encode(), 260_000)
    return f"{salt}:{dk.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, dk_hex = stored.split(":", 1)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                  salt.encode(), 260_000)
        return dk.hex() == dk_hex
    except Exception:
        return False


# ─── Public API ───────────────────────────────────────────────────────────────

def user_exists(username: str) -> bool:
    return username.strip().lower() in _load_users()


def register_user(
    username: str,
    password: str,
    display_name: str = "",
) -> tuple[bool, str]:
    """
    Регистрирует нового пользователя.
    Возвращает (success: bool, error_msg: str).
    """
    key = username.strip().lower()
    if len(key) < 2:
        return False, "Имя пользователя должно содержать минимум 2 символа."
    if len(password) < 6:
        return False, "Пароль должен содержать минимум 6 символов."

    users = _load_users()
    if key in users:
        return False, "Пользователь с таким именем уже зарегистрирован."

    users[key] = {
        "username":     key,
        "display_name": display_name.strip() or username.strip(),
        "password_hash": _hash_password(password),
    }
    _save_users(users)

    # Создать пустой профиль
    save_profile(key, load_profile(key))
    return True, ""


def authenticate(
    username: str,
    password: str,
) -> tuple[bool, str, str]:
    """
    Проверяет логин/пароль.
    Возвращает (success, display_name, error_msg).
    """
    key   = username.strip().lower()
    users = _load_users()

    if key not in users:
        return False, "", "Пользователь не найден."

    u = users[key]
    if not _verify_password(password, u.get("password_hash", "")):
        return False, "", "Неверный пароль."

    return True, u.get("display_name", key), ""


def get_display_name(username: str) -> str:
    users = _load_users()
    u     = users.get(username.strip().lower(), {})
    return u.get("display_name", username)
