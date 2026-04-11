"""
profiles.py — хранилище профилей пользователей
===============================================
Сохраняет избранное, рейтинги и рационы в JSON-файлы в папке profiles/.
"""

import json
import uuid
from pathlib import Path
from datetime import datetime

PROFILES_DIR = Path(__file__).parent / "profiles"


def _path(name: str) -> Path:
    return PROFILES_DIR / f"{name}.json"


def _empty() -> dict:
    return {
        "settings":   {},
        "favorites":  {},
        "ratings":    {},
        "saved_plans": [],   # list of plan dicts
    }


def list_profiles() -> list[str]:
    """Возвращает список имён существующих профилей."""
    PROFILES_DIR.mkdir(exist_ok=True)
    return sorted(p.stem for p in PROFILES_DIR.glob("*.json"))


def profile_exists(name: str) -> bool:
    return _path(name).exists()


def load_profile(name: str) -> dict:
    """Загружает профиль по имени; возвращает пустой если не найден."""
    PROFILES_DIR.mkdir(exist_ok=True)
    p = _path(name)
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        # backwards-compat: убедимся что все ключи есть
        base = _empty()
        base.update(data)
        return base
    return _empty()


def save_profile(name: str, data: dict) -> None:
    """Сохраняет профиль на диск."""
    PROFILES_DIR.mkdir(exist_ok=True)
    with open(_path(name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def delete_profile(name: str) -> None:
    p = _path(name)
    if p.exists():
        p.unlink()


# ─── планы ────────────────────────────────────────────────────────────────────

def make_day_plan_record(meals: list, targets: dict) -> dict:
    """Создаёт запись для сохранения дневного рациона."""
    now   = datetime.now()
    total = sum(m["recipe"]["calories"] for m in meals)
    return {
        "id":      str(uuid.uuid4())[:8],
        "type":    "day",
        "title":   f"День · {now.strftime('%d %b %Y, %H:%M')}",
        "date":    now.isoformat(),
        "total_cal": round(total),
        "target_cal": targets["tdee_target"],
        "targets": targets,
        "meals":   _serialize_meals(meals),
    }


def make_week_plan_record(week_plan: list, targets: dict) -> dict:
    """Создаёт запись для сохранения недельного рациона."""
    now  = datetime.now()
    cals = [sum(m["recipe"]["calories"] for m in dm) for _, dm in week_plan if dm]
    avg  = round(sum(cals) / len(cals)) if cals else 0
    return {
        "id":       str(uuid.uuid4())[:8],
        "type":     "week",
        "title":    f"Неделя · {now.strftime('%d %b %Y')}",
        "date":     now.isoformat(),
        "avg_cal":  avg,
        "target_cal": targets["tdee_target"],
        "targets":  targets,
        "days": [
            {"day_name": dn, "meals": _serialize_meals(dm)}
            for dn, dm in week_plan if dm
        ],
    }


def _serialize_meals(meals: list) -> list:
    """Сериализует список блюд (убираем несериализуемые поля если есть)."""
    out = []
    for m in meals:
        out.append({
            "slot": {
                "label":    m["slot"]["label"],
                "icon":     m["slot"]["icon"],
                "fraction": m["slot"]["fraction"],
                "query":    m["slot"]["query"],
            },
            "recipe": dict(m["recipe"]),
        })
    return out
