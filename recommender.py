"""
Модуль рекомендательного конвейера (pipeline):
  Семантический поиск (KNN) → Строгая фильтрация (аллергены) → Ранжирование (КБЖУ) → RAG-объяснение
"""

from __future__ import annotations
from typing import Any

import pandas as pd
from vector_db import RecipeVectorDB
from nutrition import calculate_user_targets
from llm_explainer import LLMExplainer
from config import ALPHA_RANKING, MEAL_FRACTION, SEARCH_TOP_K, RESULT_TOP_N
from translator import translate_query_to_english

class Recommender:
    """Основной объект рекомендательной системы."""

    def __init__(self, db: RecipeVectorDB, df: pd.DataFrame):
        self.db = db
        self.df = df
        self.llm = LLMExplainer()

    # ══════════════════════════════════════════
    #  Публичный pipeline
    # ══════════════════════════════════════════
    def recommend(
        self,
        user: dict,
        query: str,
        top_n: int = RESULT_TOP_N,
        meal_fraction: float = MEAL_FRACTION,
        alpha: float = ALPHA_RANKING,
        override_targets: dict = None,
    ) -> list[dict]:
        """
        Parameters
        ----------
        user          : dict с ключами gender, weight, height, age, activity, goal, allergens
        query         : текстовый запрос пользователя
        top_n         : сколько рецептов вернуть
        meal_fraction : доля суточной нормы на этот приём пищи (0.10 – 0.35)
        alpha         : вес семантического расстояния (1-alpha = вес нутриентов)
                        уменьшите до 0.2 для строгого контроля калорий

        Returns
        -------
        list[dict]  —  отсортированный список рецептов с объяснениями
        """
        # 1. Целевые нормы
        targets = calculate_user_targets(
            user["gender"], user["weight"], user["height"],
            user["age"], user["activity"], user["goal"],
        )

        # 2. Семантический поиск кандидатов
        search_query = translate_query_to_english(query)
        raw = self.db.search(search_query, top_k=SEARCH_TOP_K)
        if not raw["ids"] or not raw["ids"][0]:
            return []

        ids       = raw["ids"][0]
        metas     = raw["metadatas"][0]
        distances = raw["distances"][0]

        # 3. Строгая фильтрация (аллергены)
        user_allergens = set(a.lower() for a in user.get("allergens", []))
        filtered: list[tuple[str, dict, float]] = []

        for rid, meta, dist in zip(ids, metas, distances):
            recipe_allergens = set(
                a.strip().lower() for a in meta.get("allergens", "").split(",") if a.strip()
            )
            if recipe_allergens & user_allergens:
                continue                         # пересечение ≠ ∅ → отбрасываем
            filtered.append((rid, meta, dist))

        if not filtered:
            return []

        # 3b. Определение точных целевых КБЖУ для данного приёма пищи
        # Если передан override_targets (динамический рюкзак), используем его.
        # Иначе считаем пропорционально meal_fraction.
        if override_targets:
            meal_cals = override_targets["calories"]
            meal_prot = override_targets["protein"]
            meal_fat  = override_targets["fat"]
            meal_carb = override_targets["carbs"]
        else:
            meal_cals = targets["tdee_target"] * meal_fraction
            meal_prot = targets["protein_g"]   * meal_fraction
            meal_fat  = targets["fat_g"]       * meal_fraction
            meal_carb = targets["carbs_g"]     * meal_fraction

        # 4. Мягкое Ранжирование: score = alpha·dist + (1-alpha)·penalty  (меньше = лучше)
        # Мы убрали жёсткую фильтрацию по калориям, чтобы функция _nutrient_penalty 
        # сама находила рецепт с минимальным отклонением в нужную сторону.

        goal = user.get("goal", "")
        scored: list[tuple[float, str, dict]] = []
        for rid, meta, dist in filtered:
            penalty = self._nutrient_penalty(meta, meal_cals, meal_prot, meal_fat, meal_carb, goal)
            score = alpha * dist + (1 - alpha) * penalty
            scored.append((score, rid, meta))

        scored.sort(key=lambda x: x[0])

        # 5. RAG-объяснения для top_n
        results: list[dict] = []
        for score, rid, meta in scored[:top_n]:
            explanation = self.llm.explain(
                recipe_name=meta["name"],
                recipe_calories=meta["calories"],
                recipe_protein=meta["protein"],
                recipe_fat=meta["fat"],
                recipe_carbs=meta["carbs"],
                user_goal=user["goal"],
                user_allergens=user.get("allergens", []),
                target_cals=targets["tdee_target"],
                target_protein=targets["protein_g"],
            )
            results.append({
                "id":          rid,
                "name":        meta["name"],
                "calories":    meta["calories"],
                "protein":     meta["protein"],
                "fat":         meta["fat"],
                "carbs":       meta["carbs"],
                "ingredients": meta.get("ingredients", ""),
                "steps":       meta.get("steps", ""),
                "description": meta.get("description", ""),
                "explanation": explanation,
                "score":       round(score, 4),
            })
        return results

    # ══════════════════════════════════════════
    #  Функция штрафа за отклонение КБЖУ
    # ══════════════════════════════════════════
    @staticmethod
    def _nutrient_penalty(meta: dict, t_cal: float, t_pro: float, t_fat: float, t_carb: float, goal: str = "") -> float:
        """Взвешенная сумма относительных отклонений КБЖУ от целевых на один приём."""
        actual_cal = meta["calories"]

        def rel(actual, target):
            return abs(actual - target) / target if target else 0.0

        cal_penalty = rel(actual_cal, t_cal)
        
        # Асимметричный штраф для калорий
        if goal == "Похудение" and actual_cal > t_cal:
            cal_penalty *= 5.0  # Жёстко штрафуем перебор
        elif goal == "Набор мышечной массы" and actual_cal < t_cal:
            cal_penalty *= 5.0  # Жёстко штрафуем недобор

        return (
            0.4 * cal_penalty
            + 0.3 * rel(meta["protein"], t_pro)
            + 0.15 * rel(meta["fat"],     t_fat)
            + 0.15 * rel(meta["carbs"],   t_carb)
        )
