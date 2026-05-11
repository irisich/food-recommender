"""
Генерация текстовых объяснений «почему рецепт подходит пользователю».

Стратегия:
  1. Попытка использовать GigaChat (Сбер) — бесплатно, работает в России.
  2. Если ключа нет или возникла ошибка — fallback на умные шаблоны.
"""

import os
from config import LLM_MODEL_NAME, GIGACHAT_API_KEY


class LLMExplainer:
    """Инициализация клиента GigaChat + fallback."""

    def __init__(self):
        self._client = None
        self._loaded = False
        self._failed = False

    # ──────────── Инициализация клиента ────────────
    def _load(self):
        if self._loaded or self._failed:
            return

        key = ""
        try:
            # pyrefly: ignore [missing-import]
            import streamlit as st
            key = st.secrets.get("GIGACHAT_API_KEY", "")
        except Exception:
            pass

        if not key:
            from config import GIGACHAT_API_KEY
            key = GIGACHAT_API_KEY or os.getenv("GIGACHAT_API_KEY", "")

        if not key:
            print("[INFO] GigaChat API key not found. Using fallback templates.")
            self._failed = True
            return

        try:
            from gigachat import GigaChat
            # verify_ssl_certs=False нужен для работы с российскими сертификатами
            self._client = GigaChat(credentials=key, verify_ssl_certs=False)
            self._loaded = True
            print("[OK] GigaChat client initialized.")
        except ImportError:
            print("[WARN] 'gigachat' package not installed. Run: pip install gigachat")
            self._failed = True
        except Exception as e:
            print(f"[WARN] GigaChat init error: {e}")
            self._failed = True

    # ──────────── Основной метод ────────────
    def explain(
        self,
        recipe_name: str,
        recipe_calories: float,
        recipe_protein: float,
        recipe_fat: float,
        recipe_carbs: float,
        user_goal: str,
        user_allergens: list[str],
        target_cals: float,
        target_protein: float,
    ) -> str:
        """Генерирует объяснение (через GigaChat или шаблон)."""
        self._load()

        if self._loaded and self._client is not None:
            return self._llm_explanation(
                recipe_name, recipe_calories, recipe_protein,
                user_goal, user_allergens, target_cals, target_protein
            )

        return self._template_explanation(
            recipe_name, recipe_calories, recipe_protein,
            recipe_fat, recipe_carbs,
            user_goal, user_allergens, target_cals, target_protein,
        )

    # ──────────── LLM (GigaChat) ────────────
    def _llm_explanation(
        self, name, cals, prot, goal, allergens, t_cals, t_prot,
    ) -> str:
        allergen_str = ", ".join(allergens) if allergens else "без ограничений"

        prompt = (
            f"Ты нейро-диетолог. Коротко (1-2 предложения) объясни, "
            f"почему блюдо '{name}' ({cals:.0f} ккал, {prot:.0f} г белка) "
            f"подойдет клиенту. Его цель: {goal}. Аллергии: {allergen_str}. "
            f"Пиши на русском, дружелюбно, выдели цифры тегом <b>цифра</b>. "
            f"Не пиши вводных слов, пиши сразу ответ."
        )

        try:
            from gigachat.models import Chat, Messages, MessagesRole
            response = self._client.chat(
                Chat(
                    messages=[Messages(role=MessagesRole.USER, content=prompt)],
                    temperature=0.7,
                    max_tokens=150,
                )
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[WARN] GigaChat API Error: {e}")
            return self._template_explanation(
                name, cals, prot, 0, 0, goal, allergens, t_cals, t_prot,
            )

    # ──────────── Шаблонный fallback ────────────
    @staticmethod
    def _template_explanation(
        name, cals, prot, fat, carbs, goal, allergens, t_cals, t_prot,
    ) -> str:
        benefits = []
        if prot >= 25:
            benefits.append("отличное количество белка")
        elif prot >= 15:
            benefits.append("хорошая порция белка")

        if cals <= 350 and goal == "Похудение":
            benefits.append("приятно низкая калорийность")
        elif cals > 600 and goal == "Набор мышечной массы":
            benefits.append("высокая энергетическая ценность")

        if carbs >= 50:
            benefits.append("долгие углеводы для энергии")

        import random
        rng = random.Random(hash(name))

        benefit_str = f" ({', '.join(benefits)})" if benefits else ""

        goal_phrases = {
            "Похудение": [
                "комфортно худеть без чувства голода",
                "оставаться в дефиците калорий",
                "снижать вес легко и вкусно",
            ],
            "Поддержание веса": [
                "поддерживать идеальный баланс и форму",
                "оставаться в своей норме",
                "питаться сбалансировано каждый день",
            ],
            "Набор мышечной массы": [
                "обеспечить качественный строительный материал для мышц",
                "получить нужный профицит для массонабора",
                "зарядить организм энергией для тренировок",
            ],
        }

        g_phrase = rng.choice(goal_phrases.get(goal, ["следовать вашему плану"]))

        templates = [
            f"Это блюдо{benefit_str} идеально подойдёт, чтобы {g_phrase}. Оно сбалансировано и даёт вам <b>{cals:.0f} ккал</b>, включая <b>{prot:.0f} г</b> качественного белка.",
            f"Мы выбрали этот рецепт, так как он поможет {g_phrase}. В одной порции содержится <b>{cals:.0f} ккал</b> и <b>{prot:.0f} г</b> белка{benefit_str}.",
            f"Отличный выбор, чтобы {g_phrase}! Вы получите <b>{cals:.0f} ккал</b> и <b>{prot:.0f} г</b> белка, а также дополнительные плюсы: {', '.join(benefits) if benefits else 'отличный вкус'}.",
            f"С этим блюдом легко {g_phrase}. Оно содержит <b>{prot:.0f} г</b> белка при калорийности <b>{cals:.0f} ккал</b>{benefit_str}.",
            f"Рекомендуем этот вариант, чтобы {g_phrase}. Баланс нутриентов отличный: <b>{cals:.0f} ккал</b> и <b>{prot:.0f} г</b> ценного белка{benefit_str}.",
        ]

        explanation = rng.choice(templates)

        if allergens:
            allergen_phrases = [
                f" Рецепт безопасен: в нём нет {', '.join(allergens).lower()}.",
                f" Мы проверили состав на аллергены: {', '.join(allergens).lower()} отсутствуют.",
                f" И никаких следов {', '.join(allergens).lower()} — можно есть спокойно."
            ]
            explanation += rng.choice(allergen_phrases)

        return explanation
