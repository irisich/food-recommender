"""
NutriRec — Персональные рекомендации по питанию
================================================
Sidebar:  профиль пользователя + кнопки генерации рациона
Main:     метрики КБЖУ / рацион на день / рацион на неделю / поиск по запросу
"""

import streamlit as st
import random
from data_processing import load_and_clean, preprocess
from vector_db import RecipeVectorDB
from recommender import Recommender
from nutrition import calculate_user_targets
from config import ACTIVITY_LEVELS, GOALS, ALLERGEN_KEYWORDS

# ──────────────── Настройка страницы ────────────────
st.set_page_config(
    page_title="NutriRec — Умные рекомендации питания",
    page_icon="🥗",
    layout="wide",
)

# ──────────────── Кастомные стили ────────────────
st.markdown("""
<style>
    .stApp { background-color: #F8F9FA; }

    .recipe-card {
        background: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 18px;
        margin-bottom: 14px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    .recipe-card h3 { margin-top: 0; color: #2e7d32; font-size: 1.05em; }

    .meal-slot-header {
        background: linear-gradient(90deg, #e8f5e9, #f1f8e9);
        border-left: 4px solid #4CAF50;
        border-radius: 8px;
        padding: 8px 14px;
        margin: 14px 0 6px 0;
        font-weight: 700;
        font-size: 1.05em;
        color: #1b5e20;
    }

    .macro-badge {
        display: inline-block;
        background: #e8f5e9;
        color: #2e7d32;
        padding: 3px 9px;
        border-radius: 14px;
        font-size: 0.82em;
        margin-right: 5px;
        font-weight: 600;
    }

    .explanation-box {
        background: #e3f2fd;
        border-left: 4px solid #1976d2;
        border-radius: 8px;
        padding: 10px 14px;
        margin: 8px 0 0 0;
        font-size: 0.88em;
        color: #0d47a1;
    }

    .cal-ok   { color: #2e7d32; font-weight: 700; }
    .cal-bad  { color: #c62828; font-weight: 700; }
    .cal-warn { color: #e65100; font-weight: 700; }

    .empty-state {
        text-align: center;
        margin-top: 80px;
        color: #888;
    }
    .empty-state h2 { font-size: 1.8em; color: #666; }
</style>
""", unsafe_allow_html=True)


# ──────────────── Приёмы пищи: запросы и доли TDEE ────────────────
MEAL_SLOTS = [
    {"label": "Завтрак", "icon": "🌅", "query": "breakfast eggs oatmeal pancakes smoothie", "fraction": 0.25},
    {"label": "Перекус", "icon": "🍎", "query": "snack nuts fruit sandwich yogurt",        "fraction": 0.10},
    {"label": "Обед",    "icon": "🍽️",  "query": "lunch hearty meat pasta chicken salad",  "fraction": 0.35},
    {"label": "Ужин",    "icon": "🌙", "query": "dinner fish beef vegetables potato",      "fraction": 0.30},
]

DAYS_RU = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]


# ──────────────── Инициализация системы (кэш) ────────────────
@st.cache_resource(show_spinner="Загрузка моделей и базы данных...")
def init_system():
    df = load_and_clean()
    df = preprocess(df)
    db = RecipeVectorDB()
    db.build_index(df)
    rec = Recommender(db, df)
    return rec


recsys = init_system()


# ──────────────── Session state ────────────────
for key, default in [
    ("view",          "empty"),  # "empty" | "day" | "week" | "search"
    ("day_plan",      None),
    ("week_plan",     None),
    ("search_res",    None),
    ("last_query",    ""),
    ("regen_seed",    0),        # нарастает при каждом перегенерировании
    ("shown_ids",     set()),    # накопленные ID уже показанных рецептов
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ──────────────── Генерация одного дня ────────────────
def generate_day(user_profile: dict, used_ids: set, seed: int = 0) -> list[dict]:
    """Подбирает 4 блюда (завтрак/перекус/обед/ужин).

    seed обеспечивает вариативность: при каждом перегенерировании
    выбирается случайный рецепт из top-3 кандидатов (75% вероятность на #1).
    used_ids — ID уже показанных рецептов, они будут пропущены.
    """
    rng = random.Random(seed)
    day_meals = []
    for slot_idx, slot in enumerate(MEAL_SLOTS):
        candidates = recsys.recommend(
            user_profile,
            slot["query"],
            top_n=20,                          # больше кандидатов = больше вариативности
            meal_fraction=slot["fraction"],
            alpha=0.2,
        )
        # Фильтруем уже показанные
        fresh = [c for c in candidates if c["id"] not in used_ids]
        pool  = fresh if fresh else candidates  # fallback

        if not pool:
            continue

        # Случайный выбор из top-3: новый результат при каждом нажатии "заново"
        top_k  = min(3, len(pool))
        chosen = rng.choice(pool[:top_k])
        used_ids.add(chosen["id"])
        day_meals.append({"slot": slot, "recipe": chosen})
    return day_meals


# ──────────────── Подсветка калорийной дельты ────────────────
def calorie_delta_html(total_cal: float, target_cal: float, goal: str) -> str:
    """Возвращает HTML строку дельты с цветом согласно цели."""
    delta = total_cal - target_cal
    sign  = "+" if delta >= 0 else ""

    if goal == "Похудение":
        # меньше нормы = хорошо (зелёный), больше = плохо (красный)
        cls = "cal-ok" if delta <= 0 else "cal-bad"
    elif goal == "Набор мышечной массы":
        # больше нормы = хорошо (зелёный), меньше = плохо (красный)
        cls = "cal-ok" if delta >= 0 else "cal-bad"
    else:
        # Поддержание: ±150 — норм (зелёный), выход за пределы — предупреждение
        cls = "cal-ok" if abs(delta) <= 150 else "cal-warn"

    return f'<span class="{cls}">{sign}{delta:.0f} ккал к цели</span>'


# ──────────────── Рендер карточки рецепта ────────────────
def render_recipe_card(rec: dict, container=None):
    target = container if container else st
    target.markdown(f"""
    <div class="recipe-card">
        <h3>{rec['name']}</h3>
        <div>
            <span class="macro-badge">🔥 {rec['calories']:.0f} ккал</span>
            <span class="macro-badge">🥩 Б: {rec['protein']:.0f} г</span>
            <span class="macro-badge">🧈 Ж: {rec['fat']:.0f} г</span>
            <span class="macro-badge">🌾 У: {rec['carbs']:.0f} г</span>
        </div>
        <div class="explanation-box">
            ✨ <b>Почему подходит:</b><br>{rec['explanation']}
        </div>
    </div>
    """, unsafe_allow_html=True)
    with target.expander("📖 Посмотреть рецепт"):
        st.markdown(f"**Ингредиенты:** {rec['ingredients']}")
        st.markdown(f"**Приготовление:** {rec['steps']}")


# ──────────────── Рендер одного дня ────────────────
def render_day(day_meals: list[dict]):
    cols = st.columns(2)
    for i, meal in enumerate(day_meals):
        col  = cols[i % 2]
        slot = meal["slot"]
        rec  = meal["recipe"]
        col.markdown(
            f'<div class="meal-slot-header">{slot["icon"]} {slot["label"]}</div>',
            unsafe_allow_html=True,
        )
        render_recipe_card(rec, col)


# ──────────────── Метрики дня с умной подсветкой ────────────────
def render_day_metrics(day_meals: list[dict], targets: dict, goal: str):
    total_cal  = sum(m["recipe"]["calories"] for m in day_meals)
    total_prot = sum(m["recipe"]["protein"]  for m in day_meals)
    total_fat  = sum(m["recipe"]["fat"]      for m in day_meals)
    total_carb = sum(m["recipe"]["carbs"]    for m in day_meals)
    tdee       = targets["tdee_target"]

    delta_html = calorie_delta_html(total_cal, tdee, goal)

    st.markdown(
        f"""
        <div style="display:flex; gap:24px; flex-wrap:wrap; margin:12px 0 20px 0;">
            <div style="min-width:160px;">
                <div style="font-size:0.8em;color:#555;">Калории за день</div>
                <div style="font-size:1.4em;font-weight:700;">{total_cal:.0f} ккал</div>
                <div style="font-size:0.85em;">{delta_html}</div>
            </div>
            <div style="min-width:120px;">
                <div style="font-size:0.8em;color:#555;">Белки</div>
                <div style="font-size:1.4em;font-weight:700;">{total_prot:.0f} г</div>
                <div style="font-size:0.85em;color:#888;">{total_prot - targets['protein_g']:+.0f} г к цели</div>
            </div>
            <div style="min-width:120px;">
                <div style="font-size:0.8em;color:#555;">Жиры</div>
                <div style="font-size:1.4em;font-weight:700;">{total_fat:.0f} г</div>
                <div style="font-size:0.85em;color:#888;">{total_fat - targets['fat_g']:+.0f} г к цели</div>
            </div>
            <div style="min-width:120px;">
                <div style="font-size:0.8em;color:#555;">Углеводы</div>
                <div style="font-size:1.4em;font-weight:700;">{total_carb:.0f} г</div>
                <div style="font-size:0.85em;color:#888;">{total_carb - targets['carbs_g']:+.0f} г к цели</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    return total_cal


# ╔══════════════════════════════════════════════╗
# ║             SIDEBAR: ПРОФИЛЬ                 ║
# ╚══════════════════════════════════════════════╝
st.sidebar.title("🥑 Мой профиль питания")

st.sidebar.subheader("Антропометрия")
gender = st.sidebar.radio("Пол", ["Мужчина", "Женщина"], horizontal=True)
age    = st.sidebar.number_input("Возраст", min_value=18, max_value=100, value=25)

# Рост: слайдер + поле ввода, синхронизированы через on_change колбэки.
# Каждый виджет при изменении обновляет session_state ключ ДРУГОГО виджета,
# что заставляет Streamlit отрисовать его с новым значением на следующем ренере.
for _k, _v in [("_h_slider", 170), ("_h_input", 170)]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

def _on_slider_change():
    if "_h_slider" in st.session_state:
        st.session_state["_h_input"] = st.session_state["_h_slider"]

def _on_input_change():
    if "_h_input" in st.session_state:
        val = int(max(140, min(220, st.session_state.get("_h_input", 170))))
        st.session_state["_h_slider"] = val
        st.session_state["_h_input"]  = val

st.sidebar.markdown("**Рост (см)**")
h_col1, h_col2 = st.sidebar.columns([3, 1])

with h_col1:
    st.slider(
        "", 140, 220,
        key="_h_slider",
        on_change=_on_slider_change,
        label_visibility="collapsed",
    )
with h_col2:
    st.number_input(
        "", min_value=140, max_value=220, step=1,
        key="_h_input",
        on_change=_on_input_change,
        label_visibility="collapsed",
    )

height = int(st.session_state["_h_slider"])

weight   = st.sidebar.number_input("Вес (кг)", min_value=40.0, max_value=200.0, value=65.0, step=0.5)

st.sidebar.subheader("Активность и Цели")
activity = st.sidebar.selectbox("Уровень активности", list(ACTIVITY_LEVELS.keys()))
goal     = st.sidebar.selectbox("Цель", list(GOALS.keys()))

st.sidebar.subheader("Ограничения")
allergens = st.sidebar.multiselect("Аллергии / непереносимости", list(ALLERGEN_KEYWORDS.keys()))

user_profile = dict(
    gender=gender, age=age, height=height, weight=weight,
    activity=activity, goal=goal, allergens=allergens,
)

# ── Кнопки генерации рациона ──
st.sidebar.markdown("---")
st.sidebar.subheader("Готовый рацион")
btn_day  = st.sidebar.button("📅 Рацион на день",    use_container_width=True, type="primary")
btn_week = st.sidebar.button("🗓️ Рацион на неделю", use_container_width=True)

if btn_day:
    st.session_state.view      = "day"
    st.session_state.day_plan  = None
    st.session_state.regen_seed = 0
    st.session_state.shown_ids  = set()   # сброс истории при новом запросе
if btn_week:
    st.session_state.view       = "week"
    st.session_state.week_plan  = None
    st.session_state.regen_seed  = 0
    st.session_state.shown_ids   = set()


# ╔══════════════════════════════════════════════╗
# ║        MAIN: МЕТРИКИ                         ║
# ╚══════════════════════════════════════════════╝
st.title("🍽️ Персональные рекомендации по питанию")

targets = calculate_user_targets(gender, weight, height, age, activity, goal)

st.subheader("📊 Ваши расчётные нормы")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("ИМТ",           f"{targets['bmi']}  ({targets['bmi_cat']})")
c2.metric("Калории/день",  f"{targets['tdee_target']} ккал")
c3.metric("Белки",         f"{targets['protein_g']} г")
c4.metric("Жиры",          f"{targets['fat_g']} г")
c5.metric("Углеводы",      f"{targets['carbs_g']} г")

st.markdown("---")


# ╔══════════════════════════════════════════════╗
# ║        MAIN: РАЦИОН НА ДЕНЬ                  ║
# ╚══════════════════════════════════════════════╝
if st.session_state.view == "day":
    st.subheader("📅 Ваш рацион на день")
    tdee = targets["tdee_target"]
    st.caption(
        f"Суммарная цель: {tdee} ккал  |  "
        f"Завтрак ~{round(tdee*0.25)} ккал  |  "
        f"Перекус ~{round(tdee*0.10)} ккал  |  "
        f"Обед ~{round(tdee*0.35)} ккал  |  "
        f"Ужин ~{round(tdee*0.30)} ккал"
    )

    # Генерируем если ещё нет
    if st.session_state.day_plan is None:
        with st.spinner("Подбираем блюда..."):
            working_ids = st.session_state.shown_ids.copy()
            st.session_state.day_plan = generate_day(
                user_profile,
                used_ids=working_ids,
                seed=st.session_state.regen_seed,
            )
            # запоминаем показанные ID
            for m in st.session_state.day_plan:
                st.session_state.shown_ids.add(m["recipe"]["id"])

    day_meals = st.session_state.day_plan

    if not day_meals:
        st.warning("Не удалось подобрать блюда с учётом ваших ограничений.")
    else:
        render_day_metrics(day_meals, targets, goal)
        render_day(day_meals)

        # Кнопка «Сгенерировать заново»
        if st.button("🔄 Сгенерировать заново", key="regen_day"):
            for m in (st.session_state.day_plan or []):
                st.session_state.shown_ids.add(m["recipe"]["id"])
            st.session_state.regen_seed += 1
            st.session_state.day_plan   = None
            st.rerun()


# ╔══════════════════════════════════════════════╗
# ║        MAIN: РАЦИОН НА НЕДЕЛЮ                ║
# ╚══════════════════════════════════════════════╝
elif st.session_state.view == "week":
    st.subheader("🗓️ Ваш рацион на неделю")
    st.caption("Блюда не повторяются в течение недели.")

    if st.session_state.week_plan is None:
        with st.spinner("Составляем рацион на 7 дней..."):
            used_ids: set = st.session_state.shown_ids.copy()
            seed = st.session_state.regen_seed
            week_plan = []
            for day_idx, day_name in enumerate(DAYS_RU):
                day_meals = generate_day(user_profile, used_ids, seed=seed + day_idx)
                week_plan.append((day_name, day_meals))
            st.session_state.week_plan = week_plan

    week_plan = st.session_state.week_plan
    tdee      = targets["tdee_target"]

    for day_name, day_meals in week_plan:
        if not day_meals:
            continue
        total_cal  = sum(m["recipe"]["calories"] for m in day_meals)
        delta_html = calorie_delta_html(total_cal, tdee, goal)

        with st.expander(
            f"📆 {day_name}  —  {total_cal:.0f} ккал",
            expanded=(day_name == DAYS_RU[0]),
        ):
            # Компактные метрики дня внутри expander
            st.markdown(
                f"Суточная сумма: **{total_cal:.0f} ккал** &nbsp; {delta_html} &nbsp;"
                f"(цель: {tdee} ккал)",
                unsafe_allow_html=True,
            )
            render_day(day_meals)

    # Кнопка «Сгенерировать заново»
    if st.button("🔄 Сгенерировать заново", key="regen_week"):
        for _, dm in (st.session_state.week_plan or []):
            for m in dm:
                st.session_state.shown_ids.add(m["recipe"]["id"])
        st.session_state.regen_seed += 1
        st.session_state.week_plan  = None
        st.rerun()


# ╔══════════════════════════════════════════════╗
# ║        MAIN: ПОИСК ПО ЗАПРОСУ                ║
# ╚══════════════════════════════════════════════╝
else:
    st.markdown("#### 🔍 Или найдите конкретное блюдо")
    query = st.text_input(
        "Что хотите приготовить?",
        placeholder="Например: быстрый белковый завтрак без мяса",
        label_visibility="collapsed",
    )
    search_clicked = st.button("Подобрать рецепты", type="primary", use_container_width=True)

    if search_clicked:
        if not query.strip():
            st.warning("Введите запрос — опишите, что хотите приготовить.")
        else:
            with st.spinner("Ищем идеальные рецепты для вас..."):
                results = recsys.recommend(user_profile, query, top_n=5)
            if not results:
                st.info(
                    "По вашему запросу с учётом всех ограничений ничего не найдено. "
                    "Попробуйте смягчить фильтры или изменить запрос."
                )
            else:
                st.subheader(f"Найдено рецептов: {len(results)}")
                for i in range(0, len(results), 2):
                    cols = st.columns(2)
                    for j, col in enumerate(cols):
                        idx = i + j
                        if idx >= len(results):
                            break
                        render_recipe_card(results[idx], col)

    elif not query:
        st.markdown("""
        <div class="empty-state">
            <h2>👈 Заполните профиль и выберите действие</h2>
            <p>Нажмите <b>«Рацион на день»</b> или <b>«Рацион на неделю»</b> в боковой панели,<br>
            или введите запрос ниже, чтобы найти конкретное блюдо.</p>
        </div>
        """, unsafe_allow_html=True)
