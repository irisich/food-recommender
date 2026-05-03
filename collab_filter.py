"""
collab_filter.py — User-based Collaborative Filtering для NutriRec
===================================================================
Рекомендации основаны на оценках (1–5) всех зарегистрированных пользователей.
"""

import json
import math
from pathlib import Path
from profiles import PROFILES_DIR


# ─── Загрузка оценок ────────────────────────────────────────────────────────

def load_all_ratings() -> dict[str, dict[str, int]]:
    """
    Читает все профили и возвращает:
        {username: {recipe_id: rating(1-5)}}
    Нулевые (сброшенные) оценки отфильтровываются.
    """
    all_ratings: dict[str, dict[str, int]] = {}
    for prof_file in sorted(PROFILES_DIR.glob("*.json")):
        if prof_file.name.startswith("_"):
            continue          # _users.json и прочие служебные
        try:
            with open(prof_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw = data.get("ratings", {})
            # Оставляем только реальные оценки (1–5)
            filtered = {str(k): int(v) for k, v in raw.items() if int(v) >= 1}
            if filtered:
                all_ratings[prof_file.stem] = filtered
        except Exception:
            pass
    return all_ratings


def ratings_count() -> int:
    """Суммарное число оценок в системе."""
    return sum(len(r) for r in load_all_ratings().values())


# ─── Метрики сходства ────────────────────────────────────────────────────────

def _cosine_sim(a: dict[str, int], b: dict[str, int]) -> float:
    """Косинусное сходство двух словарей оценок."""
    common = set(a) & set(b)
    if not common:
        return 0.0
    dot   = sum(a[k] * b[k] for k in common)
    mag_a = math.sqrt(sum(v ** 2 for v in a.values()))
    mag_b = math.sqrt(sum(v ** 2 for v in b.values()))
    return dot / (mag_a * mag_b) if (mag_a and mag_b) else 0.0


def _pearson_sim(a: dict[str, int], b: dict[str, int]) -> float:
    """Корреляция Пирсона — устойчивее к 'щедрым' и 'строгим' пользователям."""
    common = list(set(a) & set(b))
    n = len(common)
    if n < 2:
        return _cosine_sim(a, b)

    mean_a = sum(a[k] for k in common) / n
    mean_b = sum(b[k] for k in common) / n

    num   = sum((a[k] - mean_a) * (b[k] - mean_b) for k in common)
    den_a = math.sqrt(sum((a[k] - mean_a) ** 2 for k in common))
    den_b = math.sqrt(sum((b[k] - mean_b) ** 2 for k in common))

    if den_a == 0 or den_b == 0:
        return 0.0
    return num / (den_a * den_b)


# ─── Поиск рецепта в DataFrame ───────────────────────────────────────────────

def _lookup_recipe(item_id: str, df, cf_score: float) -> dict | None:
    """Ищет рецепт по id в pandas DataFrame; возвращает dict или None."""
    # Пробуем строковый id
    mask = df["id"].astype(str) == str(item_id)
    if not mask.any():
        # Пробуем целочисленный id
        try:
            mask = df["id"] == int(item_id)
        except (ValueError, TypeError):
            return None
    if not mask.any():
        return None

    r = df[mask].iloc[0]
    stars = round(cf_score)
    return {
        "id":          str(r.get("id", item_id)),
        "name":        str(r.get("name", "—")),
        "calories":    float(r.get("calories", 0)),
        "protein":     float(r.get("protein", 0)),
        "fat":         float(r.get("fat", 0)),
        "carbs":       float(r.get("carbs", 0)),
        "ingredients": str(r.get("ingredients", "")),
        "steps":       str(r.get("steps", "")),
        "explanation": (
            f"Рекомендовано сообществом · прогнозируемая оценка "
            f"{'★' * stars}{'☆' * (5 - stars)} ({cf_score:.1f}/5)"
        ),
        "_cf_score":   cf_score,
    }


# ─── Основная функция ────────────────────────────────────────────────────────

def recommend_collaborative(
    current_username: str,
    current_ratings:  dict[str, int],
    df,                          # pandas DataFrame с рецептами
    top_n:       int = 8,
    top_k_users: int = 10,
    min_score:   float = 3.5,   # минимальный прогнозируемый балл
) -> tuple[list[dict], str]:
    """
    User-based Collaborative Filtering.

    Возвращает (список recipe_dict, информационная строка).
    """
    # Оставляем только реальные оценки текущего пользователя
    cur = {k: v for k, v in current_ratings.items() if v >= 1}

    all_ratings = load_all_ratings()
    others = {u: r for u, r in all_ratings.items() if u != current_username}

    # ── Сценарий 1: данных нет вообще ───────────────────────────────────────
    if not others:
        return [], "no_data"

    # ── Сценарий 2: у текущего пользователя нет оценок → популярные блюда ──
    if not cur:
        return _popular(others, df, top_n, min_score), "popular"

    # ── Сценарий 3: полноценный CF ───────────────────────────────────────────
    sims: list[tuple[float, dict]] = []
    for uname, ratings in others.items():
        sim = _pearson_sim(cur, ratings)
        if sim > 0:
            sims.append((sim, ratings))

    if not sims:
        # Нет пересечения — показываем популярное
        return _popular(others, df, top_n, min_score), "popular"

    sims.sort(key=lambda x: -x[0])
    top_users = sims[:top_k_users]

    # Взвешенная сумма оценок по непросмотренным рецептам
    weighted: dict[str, list[float]] = {}   # item_id → [weighted_sum, sim_sum]
    for sim, ratings in top_users:
        for item_id, rating in ratings.items():
            if item_id in cur:
                continue    # уже оценено
            if item_id not in weighted:
                weighted[item_id] = [0.0, 0.0]
            weighted[item_id][0] += sim * rating
            weighted[item_id][1] += sim

    if not weighted:
        return [], "no_new"

    # Предсказанные оценки
    preds: list[tuple[str, float]] = [
        (iid, ws[0] / ws[1])
        for iid, ws in weighted.items()
        if ws[1] > 0
    ]
    preds = [(iid, sc) for iid, sc in preds if sc >= min_score]
    preds.sort(key=lambda x: -x[1])
    preds = preds[:top_n]

    results = []
    for iid, sc in preds:
        rec = _lookup_recipe(iid, df, sc)
        if rec:
            results.append(rec)

    if not results:
        return _popular(others, df, top_n, min_score), "popular"

    return results, "cf"


def _popular(
    others: dict[str, dict[str, int]],
    df,
    top_n: int,
    min_score: float,
) -> list[dict]:
    """Fallback: агрегированный рейтинг по всем пользователям."""
    agg: dict[str, list[int]] = {}
    for ratings in others.values():
        for iid, r in ratings.items():
            if r >= 1:
                agg.setdefault(iid, []).append(r)

    scored = [
        (iid, sum(rs) / len(rs), len(rs))
        for iid, rs in agg.items()
        if len(rs) >= 1 and sum(rs) / len(rs) >= min_score
    ]
    scored.sort(key=lambda x: (-x[1], -x[2]))

    results = []
    for iid, score, _ in scored[:top_n]:
        rec = _lookup_recipe(iid, df, score)
        if rec:
            results.append(rec)
    return results
