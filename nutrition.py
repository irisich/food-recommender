"""
Модуль расчёта персональных норм питания.

Формулы:
  BMR (Харрис-Бенедикт, пересмотренная):
    М: 88.362 + 13.397·W + 4.799·H − 5.677·A
    Ж: 447.593 + 9.247·W + 3.098·H − 4.330·A
  TDEE = BMR × activity_multiplier
  TDEE_target = TDEE × goal_multiplier
  Protein(г) = (TDEE_target × ratio_P) / 4
  Fat(г)     = (TDEE_target × ratio_F) / 9
  Carbs(г)   = (TDEE_target × ratio_C) / 4
  BMI = W / (H/100)²
"""

from config import ACTIVITY_LEVELS, GOALS, MACRO_RATIOS


# ───────────────────── BMR ─────────────────────
def calculate_bmr(gender: str, weight: float, height: float, age: int) -> float:
    """Базовый обмен веществ (ккал/сут)."""
    if gender == "Мужчина":
        return 88.362 + 13.397 * weight + 4.799 * height - 5.677 * age
    return 447.593 + 9.247 * weight + 3.098 * height - 4.330 * age


# ───────────────────── BMI ─────────────────────
def calculate_bmi(weight: float, height_cm: float) -> float:
    """Индекс массы тела."""
    h = height_cm / 100.0
    return round(weight / (h * h), 1) if h > 0 else 0.0


def bmi_category(bmi: float) -> str:
    """Текстовая категория ИМТ."""
    if bmi < 18.5:
        return "Дефицит массы"
    if bmi < 25:
        return "Норма"
    if bmi < 30:
        return "Избыточный вес"
    return "Ожирение"


# ─────────── Полный расчёт TDEE + БЖУ ─────────
def calculate_user_targets(
    gender: str,
    weight: float,
    height: float,
    age: int,
    activity_key: str,
    goal_key: str,
) -> dict:
    """
    Возвращает словарь:
        bmi, bmi_cat, bmr, tdee, tdee_target,
        protein_g, fat_g, carbs_g
    """
    bmr = calculate_bmr(gender, weight, height, age)
    activity_mult = ACTIVITY_LEVELS.get(activity_key, 1.2)
    tdee = bmr * activity_mult

    goal_mult = GOALS.get(goal_key, 1.0)
    tdee_target = tdee * goal_mult

    ratios = MACRO_RATIOS.get(goal_key, {"protein": 0.25, "fat": 0.30, "carbs": 0.45})
    protein_g = (tdee_target * ratios["protein"]) / 4
    fat_g = (tdee_target * ratios["fat"]) / 9
    carbs_g = (tdee_target * ratios["carbs"]) / 4

    bmi = calculate_bmi(weight, height)

    return {
        "bmi": bmi,
        "bmi_cat": bmi_category(bmi),
        "bmr": round(bmr),
        "tdee": round(tdee),
        "tdee_target": round(tdee_target),
        "protein_g": round(protein_g),
        "fat_g": round(fat_g),
        "carbs_g": round(carbs_g),
    }
