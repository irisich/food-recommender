"""
ETL-модуль: загрузка, очистка и предобработка датасета рецептов.

Поддерживает два датасета:
  1. Better Recipes for a Better Life (Kaggle, 1090 рецептов)
     Колонки: recipe_name, ingredients, directions, nutrition (строка)
  2. Food.com Recipes (Kaggle, 231k рецептов) — активный датасет
     Колонки: name, id, nutrition (список), ingredients, steps, description

Основные функции:
  load_and_clean()    — читает CSV, нормализует структуру, парсит КБЖУ
  extract_allergens() — определяет аллергены по тексту ингредиентов
  preprocess()        — добавляет text_for_embedding и allergens
"""

import os
import re
import ast
import pandas as pd
import numpy as np
from config import DATA_PATH, ALLERGEN_KEYWORDS

# ──────────── Парсинг КБЖУ ─────────────────────────────────────

def _parse_nutrition_string(nutrition_str: str) -> dict:
    """
    Парсит строку Better Recipes:
      'Total Fat 19g 24%, Protein 2g, Total Carbohydrate 52g 19%...'
    """
    result = {"calories": np.nan, "protein": np.nan, "fat": np.nan, "carbs": np.nan}
    if not isinstance(nutrition_str, str):
        return result

    cal = re.search(r"(\d+(?:\.\d+)?)\s*calories?", nutrition_str, re.I)
    if not cal:
        cal = re.search(r"(\d+(?:\.\d+)?)\s*cal\b", nutrition_str, re.I)
    if cal:
        result["calories"] = float(cal.group(1))

    prot = re.search(r"Protein\s+(\d+(?:\.\d+)?)g", nutrition_str, re.I)
    if prot:
        result["protein"] = float(prot.group(1))

    fat = re.search(r"Total\s+Fat\s+(\d+(?:\.\d+)?)g", nutrition_str, re.I)
    if fat:
        result["fat"] = float(fat.group(1))

    carb = re.search(r"Total\s+Carbohydrate\s+(\d+(?:\.\d+)?)g", nutrition_str, re.I)
    if not carb:
        carb = re.search(r"Carbohydrates?\s+(\d+(?:\.\d+)?)g", nutrition_str, re.I)
    if carb:
        result["carbs"] = float(carb.group(1))

    return result


def _parse_nutrition_list(nutrition_val) -> dict:
    """
    Парсит Food.com format:
      [calories, total_fat%, sugar%, sodium%, protein%, sat_fat%, carbs%]
    Конвертирует %ДН в граммы используя стандартные суточные нормы.
    """
    result = {"calories": np.nan, "protein": np.nan, "fat": np.nan, "carbs": np.nan}
    try:
        if isinstance(nutrition_val, str):
            arr = ast.literal_eval(nutrition_val)
        else:
            arr = list(nutrition_val)
        if len(arr) < 7:
            return result
        # arr = [calories, fat_pdv, sugar_pdv, sodium_pdv, protein_pdv, sat_fat_pdv, carbs_pdv]
        # Суточные нормы: fat=78г, protein=50г, carbs=275г
        result["calories"] = float(arr[0])
        result["fat"]      = round(float(arr[1]) * 78 / 100, 1)    # % от 78г
        result["protein"]  = round(float(arr[4]) * 50 / 100, 1)    # % от 50г
        result["carbs"]    = round(float(arr[6]) * 275 / 100, 1)   # % от 275г
    except Exception:
        pass
    return result


# ──────────── Определение типа датасета ──────────────────────

def _detect_dataset_type(df: pd.DataFrame) -> str:
    """Определяет тип датасета по наличию колонок."""
    cols = set(df.columns)
    if "recipe_name" in cols:
        return "better_recipes"
    if "name" in cols and "nutrition" in cols and "n_steps" in cols:
        return "foodcom"
    return "unknown"


# ──────────── Загрузка / мок ──────────────────────────────────

def load_and_clean(path: str = DATA_PATH) -> pd.DataFrame:
    """
    Загружает CSV и нормализует до стандартной схемы проекта:
      id, name, description, ingredients, steps, calories, protein, fat, carbs, image_url
    """
    if not os.path.exists(path):
        print("[WARN] Dataset file not found, using mock data.")
        return _mock_dataset()

    df = pd.read_csv(path, low_memory=False)
    dataset_type = _detect_dataset_type(df)

    # ── Food.com ───────────────────────────────────────────────
    if dataset_type == "foodcom":
        df = df.rename(columns={"id": "recipe_id"})
        df.insert(0, "id", range(1, len(df) + 1))
        df["id"] = df["id"].astype(str)

        # Парсинг КБЖУ из списка
        parsed = df["nutrition"].apply(_parse_nutrition_list)
        for key in ("calories", "protein", "fat", "carbs"):
            df[key] = parsed.apply(lambda d: d[key])

        # Нормализация ингредиентов: список Python → строка
        def liststr(val):
            try:
                lst = ast.literal_eval(val) if isinstance(val, str) else val
                return ", ".join(str(x) for x in lst) if isinstance(lst, list) else str(val)
            except Exception:
                return str(val)

        df["ingredients"] = df["ingredients"].apply(liststr)

        # Шаги → строка
        def steps_str(val):
            try:
                lst = ast.literal_eval(val) if isinstance(val, str) else val
                if isinstance(lst, list):
                    return " ".join(f"{i+1}. {s}" for i, s in enumerate(lst))
            except Exception:
                pass
            return str(val)

        df["steps"] = df.get("steps", pd.Series("", index=df.index)).apply(steps_str)

        if "description" not in df.columns:
            df["description"] = ""
        df["description"] = df["description"].fillna("")
        df["image_url"] = ""

        # Реалистичная фильтрация калорий (убираем явные ошибки)
        df = df[
            df["calories"].between(50, 3000)
        ].copy()

    # ── Better Recipes ─────────────────────────────────────────
    elif dataset_type == "better_recipes":
        df = df.rename(columns={"recipe_name": "name", "directions": "steps"})
        if "id" not in df.columns:
            df.insert(0, "id", range(1, len(df) + 1))
        df["id"] = df["id"].astype(str)

        if "nutrition" in df.columns:
            parsed = df["nutrition"].apply(_parse_nutrition_string)
            for key in ("calories", "protein", "fat", "carbs"):
                if key not in df.columns:
                    df[key] = parsed.apply(lambda d: d[key])

        if "description" not in df.columns:
            df["description"] = df.get("cuisine_path", pd.Series("", index=df.index)).fillna("")
        df["image_url"] = df.get("img_src", pd.Series("", index=df.index)).fillna("")

    # ── Общая постобработка ─────────────────────────────────────
    # Заполнение пустых текстовых колонок
    for col in ("steps", "description", "image_url"):
        if col not in df.columns:
            df[col] = ""
        else:
            df[col] = df[col].fillna("").astype(str)

    # Заполнение пустых числовых колонок
    fallback_ranges = {
        "calories": (200, 700),
        "protein": (5, 50),
        "fat": (3, 40),
        "carbs": (10, 80),
    }
    for col, (lo, hi) in fallback_ranges.items():
        if col not in df.columns:
            df[col] = np.random.randint(lo, hi, len(df)).astype(float)
        else:
            mask = df[col].isna()
            if mask.any():
                df.loc[mask, col] = np.random.randint(lo, hi, mask.sum()).astype(float)

    # Чистка имён
    df = df.dropna(subset=["name"]).copy()
    df["name"] = df["name"].astype(str).str.strip()
    df = df[df["name"] != ""].reset_index(drop=True)

    print(f"[DATA] Loaded {len(df)} recipes ({dataset_type})")
    return df


# ──────────── Разметка аллергенов ─────────────────────────────

def extract_allergens(ingredients_text: str) -> list[str]:
    """Возвращает список групп аллергенов, найденных в тексте ингредиентов."""
    if not isinstance(ingredients_text, str):
        return []
    text = ingredients_text.lower()
    found: set[str] = set()
    for group, keywords in ALLERGEN_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                found.add(group)
                break
    return sorted(found)


# ──────────── Полная предобработка ────────────────────────────

def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    """
    Добавляет:
      text_for_embedding — конкатенация текстовых полей
      allergens          — строка через запятую (ChromaDB не поддерживает списки)
    """
    df = df.copy()

    df["text_for_embedding"] = (
        df["name"].fillna("")
        + ". "
        + df["description"].fillna("")
        + ". Ingredients: "
        + df["ingredients"].fillna("")
    )

    df["allergens"] = df["ingredients"].apply(
        lambda x: ", ".join(extract_allergens(x))
    )

    return df


# ──────────── Мок-датасет (fallback) ──────────────────────────

def _mock_dataset() -> pd.DataFrame:
    recipes = [
        dict(id="1", name="Grilled Chicken Breast with Quinoa",
             description="High-protein dinner for muscle building.",
             ingredients="chicken breast, quinoa, olive oil, garlic, salt, pepper, lemon",
             steps="1. Cook quinoa 15 min. 2. Grill chicken 7 min each side. 3. Serve together.",
             calories=450, protein=42, fat=12, carbs=38, image_url=""),
        dict(id="2", name="Salmon and Avocado Salad",
             description="Light salad rich in omega-3 and healthy fats.",
             ingredients="salmon, avocado, spinach, cucumber, lemon juice, olive oil",
             steps="1. Bake salmon 12 min at 200C. 2. Slice avocado and cucumber. 3. Combine.",
             calories=320, protein=28, fat=20, carbs=8, image_url=""),
        dict(id="3", name="Oatmeal with Nuts and Honey",
             description="Energizing breakfast for the whole day.",
             ingredients="oatmeal, milk, walnuts, honey, cinnamon",
             steps="1. Cook oatmeal in milk 5 min. 2. Add nuts, honey, cinnamon.",
             calories=380, protein=12, fat=14, carbs=52, image_url=""),
        dict(id="4", name="Cheese and Spinach Omelette",
             description="Classic protein breakfast with greens.",
             ingredients="eggs, cheese, spinach, butter, salt",
             steps="1. Beat 3 eggs. 2. Melt butter. 3. Add spinach and cheese. 4. Cook 3 min.",
             calories=390, protein=28, fat=28, carbs=4, image_url=""),
        dict(id="5", name="Asian Tofu with Vegetables",
             description="Vegan dish: plant protein.",
             ingredients="tofu, soy sauce, broccoli, carrot, sesame, garlic, ginger",
             steps="1. Fry tofu until golden. 2. Add vegetables and soy sauce. 3. Simmer 5 min.",
             calories=260, protein=18, fat=14, carbs=16, image_url=""),
    ]
    return pd.DataFrame(recipes)
