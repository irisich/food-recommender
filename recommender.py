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
        raw = self.db.search(query, top_k=SEARCH_TOP_K)
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

        # 3b. Калорийный фильтр по цели
        #     Датасет: max ~700 ккал на рецепт. Для высококалорийных норм
        #     (>700 ккал на приём) жёсткий фильтр невозможен — используем сортировку.
        goal = user.get("goal", "")
        meal_cals_preview = targets["tdee_target"] * meal_fraction

        if goal == "Похудение":
            # Строго меньше целевых ккал приёма
            goal_filtered = [
                (rid, meta, dist) for rid, meta, dist in filtered
                if meta["calories"] < meal_cals_preview
            ]
            # Fallback: наименее калорийные из доступных
            if len(goal_filtered) < 3:
                goal_filtered = sorted(filtered, key=lambda x: x[1]["calories"])

        elif goal == "Набор мышечной массы":
            # Строго больше целевых ккал приёма
            goal_filtered = [
                (rid, meta, dist) for rid, meta, dist in filtered
                if meta["calories"] > meal_cals_preview
            ]
            # Fallback: наиболее калорийные из доступных
            if len(goal_filtered) < 3:
                goal_filtered = sorted(filtered, key=lambda x: x[1]["calories"], reverse=True)

        else:
            # Поддержание веса — жёсткий фильтр не применяем:
            # датасет ограничен ~700 ккал, а норма на обед может быть 900+.
            # Сортируем по близости к цели — penalty-ранжирование уточнит выбор.
            goal_filtered = sorted(
                filtered, key=lambda x: abs(x[1]["calories"] - meal_cals_preview)
            )

        filtered = goal_filtered

        # 4. Ранжирование: score = alpha·dist + (1-alpha)·penalty  (меньше = лучше)
        #    meal_fraction задаёт целевую калорийность конкретного приёма пищи
        meal_cals = meal_cals_preview
        meal_prot = targets["protein_g"]   * meal_fraction
        meal_fat  = targets["fat_g"]       * meal_fraction
        meal_carb = targets["carbs_g"]     * meal_fraction

        scored: list[tuple[float, str, dict]] = []
        for rid, meta, dist in filtered:
            penalty = self._nutrient_penalty(meta, meal_cals, meal_prot, meal_fat, meal_carb)
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
    def _nutrient_penalty(meta: dict, t_cal: float, t_pro: float, t_fat: float, t_carb: float) -> float:
        """Взвешенная сумма относительных отклонений КБЖУ от целевых на один приём."""
        def rel(actual, target):
            return abs(actual - target) / target if target else 0.0

        return (
            0.4 * rel(meta["calories"], t_cal)
            + 0.3 * rel(meta["protein"], t_pro)
            + 0.15 * rel(meta["fat"],     t_fat)
            + 0.15 * rel(meta["carbs"],   t_carb)
        )
