"""
NutriRec — Персональные рекомендации по питанию
================================================
UI v2: дизайн-система · tabs · Plotly · избранное · рейтинги · экспорт
"""

import streamlit as st
import random
import plotly.graph_objects as go
from data_processing import load_and_clean, preprocess
from vector_db import RecipeVectorDB
from recommender import Recommender
from nutrition import calculate_user_targets
from config import ACTIVITY_LEVELS, GOALS, ALLERGEN_KEYWORDS
from profiles import (
    list_profiles, load_profile, save_profile, delete_profile,
    make_day_plan_record, make_week_plan_record,
)
from auth import register_user, authenticate

# ─────────────────────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NutriRec — Умные рекомендации питания",
    page_icon="🥗",
    layout="wide",
)

# ─────────────────────────────────────────────────────────────────────────────
# Design System — CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

:root {
    --font:       'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    --bg:         #F5F2ED;
    --card:       #FFFFFF;
    --sage-900:   #1B3A2D;
    --sage-700:   #2D5540;
    --sage-500:   #4A8060;
    --sage-300:   #85BDA0;
    --sage-100:   #CEEADB;
    --sage-50:    #EBF5EF;
    --terra-600:  #B85C38;
    --terra-200:  #F0B594;
    --gold-500:   #C9923A;
    --gold-50:    #FBF5E6;
    --violet-500: #7262B3;
    --violet-50:  #F2EEFB;
    --blue-500:   #4876B8;
    --blue-50:    #EEF4FF;
    --txt:        #1A1A1A;
    --txt-2:      #5A5A5A;
    --txt-3:      #9B9B9B;
    --border:     #E5DFD5;
    --r:          14px;
    --r-sm:       10px;
    --sh-sm:      0 1px 4px rgba(0,0,0,.07), 0 1px 2px rgba(0,0,0,.04);
    --sh:         0 6px 28px rgba(0,0,0,.10);
}

/* ── Reset ── */
*, *::before, *::after { box-sizing: border-box; }
html, body, .stApp, [class*="css"] { font-family: var(--font) !important; }
.stApp { background: var(--bg) !important; }
#MainMenu, footer, header { visibility: hidden; }

/* ── Remove default top padding ── */
.stApp > header { display: none !important; }
section[data-testid="stSidebar"] > div:first-child { padding-top: 1.5rem !important; }
.stMainBlockContainer, div[data-testid="stMainBlockContainer"] { padding-top: 1.5rem !important; }

/* ── Sidebar ── */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div,
section[data-testid="stSidebar"] > div > div {
    background: var(--sage-900) !important;
}
section[data-testid="stSidebar"] * {
    color: rgba(255,255,255,.78) !important;
}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] b,
section[data-testid="stSidebar"] strong {
    color: #fff !important;
}
section[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,.08) !important;
}
section[data-testid="stSidebar"] input {
    color: #1A1A1A !important;
    border-radius: 8px !important;
}
section[data-testid="stSidebar"] [data-baseweb="select"] div,
section[data-testid="stSidebar"] [data-baseweb="select"] span {
    color: #1A1A1A !important;
}
section[data-testid="stSidebar"] [data-baseweb="tag"] span {
    color: #1A1A1A !important;
}
section[data-testid="stSidebar"] .stButton > button {
    background: var(--sage-500) !important;
    color: #fff !important;
    border: none !important;
    border-radius: var(--r-sm) !important;
    font-weight: 600 !important;
    font-size: .88em !important;
    transition: background .2s !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: var(--sage-300) !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px !important;
    background: var(--card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-sm) !important;
    padding: 5px !important;
    box-shadow: var(--sh-sm) !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px !important;
    font-size: .88em !important;
    font-weight: 500 !important;
    color: var(--txt-2) !important;
    padding: 8px 22px !important;
    background: transparent !important;
    border: none !important;
    transition: all .18s ease !important;
}
.stTabs [aria-selected="true"] {
    background: var(--sage-700) !important;
    color: #fff !important;
}
.stTabs [data-baseweb="tab-highlight"],
.stTabs [data-baseweb="tab-border"] { display: none !important; }

/* ── Border containers → recipe cards ── */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border: 1px solid var(--border) !important;
    border-radius: var(--r) !important;
    background: var(--card) !important;
    box-shadow: var(--sh-sm) !important;
    transition: box-shadow .22s ease, transform .22s ease !important;
    overflow: hidden !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:hover {
    box-shadow: var(--sh) !important;
    transform: translateY(-2px) !important;
}

/* ── st.metric ── */
[data-testid="stMetric"] {
    background: var(--card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-sm) !important;
    padding: 14px 18px !important;
    box-shadow: var(--sh-sm) !important;
}
[data-testid="stMetricLabel"] {
    font-size: .70em !important;
    font-weight: 600 !important;
    letter-spacing: .06em !important;
    text-transform: uppercase !important;
    color: var(--txt-3) !important;
}
[data-testid="stMetricValue"] {
    font-size: 1.2em !important;
    font-weight: 700 !important;
    color: var(--txt) !important;
}

/* ── Buttons ── */
.stButton > button[kind="primary"] {
    background: var(--sage-700) !important;
    color: #fff !important;
    border: none !important;
    border-radius: var(--r-sm) !important;
    font-weight: 600 !important;
    transition: background .2s, transform .12s !important;
}
.stButton > button[kind="primary"]:hover {
    background: var(--sage-500) !important;
    transform: translateY(-1px) !important;
}
.stButton > button[kind="secondary"] {
    border: 1px solid var(--border) !important;
    border-radius: var(--r-sm) !important;
    color: var(--txt-2) !important;
    background: var(--card) !important;
    font-weight: 500 !important;
}
.stDownloadButton > button {
    border-radius: var(--r-sm) !important;
    font-weight: 500 !important;
}

/* ── Expanders ── */
details[data-testid="stExpander"] {
    background: var(--sage-50) !important;
    border: 1px solid var(--sage-100) !important;
    border-radius: var(--r-sm) !important;
}
details[data-testid="stExpander"] summary {
    font-size: .84em !important;
    font-weight: 500 !important;
    color: var(--txt-2) !important;
}

/* ── Alert ── */
.stAlert { border-radius: var(--r-sm) !important; }

/* ── Headings ── */
h1 { font-weight: 800 !important; letter-spacing: -.035em !important; }
h2 { font-weight: 700 !important; }
h3 { font-weight: 600 !important; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# Color identity per meal type
MEAL_STYLES = {
    "Завтрак": {"stripe": "#C9923A", "bg": "#FBF5E6", "color": "#8B621A"},
    "Перекус": {"stripe": "#4A8060", "bg": "#EBF5EF", "color": "#2D5540"},
    "Обед":    {"stripe": "#7262B3", "bg": "#F2EEFB", "color": "#4D3F8A"},
    "Ужин":    {"stripe": "#4876B8", "bg": "#EEF4FF", "color": "#2D5188"},
}

MEAL_SLOTS = [
    {"label": "Завтрак", "icon": "🌅", "query": "breakfast eggs oatmeal pancakes smoothie", "fraction": 0.25},
    {"label": "Перекус", "icon": "🍎", "query": "snack nuts fruit sandwich yogurt",         "fraction": 0.10},
    {"label": "Обед",    "icon": "🍽️", "query": "lunch hearty meat pasta chicken salad",   "fraction": 0.35},
    {"label": "Ужин",    "icon": "🌙", "query": "dinner fish beef vegetables potato",       "fraction": 0.30},
]

DAYS_RU    = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
DAYS_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
STAR_OPTS  = ["☆☆☆☆☆", "★☆☆☆☆", "★★☆☆☆", "★★★☆☆", "★★★★☆", "★★★★★"]


# ─────────────────────────────────────────────────────────────────────────────
# System init (cached)
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner="⏳ Инициализация системы…")
def init_system():
    df = load_and_clean()
    df = preprocess(df)
    db = RecipeVectorDB()
    db.build_index(df)
    return Recommender(db, df)

recsys = init_system()


# ─────────────────────────────────────────────────────────────────────────────
# Session state
# ─────────────────────────────────────────────────────────────────────────────
for _k, _v in {
    "view":           "none",
    "day_plan":       None,
    "week_plan":      None,
    "regen_seed":     0,
    "shown_ids":      set(),
    "favorites":      {},
    "ratings":        {},
    "profile_name":   "",
    "saved_plans":    [],
    "_profile_loaded": "",
    # ── Auth ──
    "authenticated":  False,
    "username":       "",
    "display_name":   "",
}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ─────────────────────────────────────────────────────────────────────────────
# Core: generate one day
# ─────────────────────────────────────────────────────────────────────────────
def generate_day(user_profile: dict, used_ids: set, seed: int = 0) -> list[dict]:
    """Подбирает 4 блюда (завтрак/перекус/обед/ужин)."""
    rng   = random.Random(seed)
    meals = []
    for slot in MEAL_SLOTS:
        cands = recsys.recommend(
            user_profile, slot["query"],
            top_n=20, meal_fraction=slot["fraction"], alpha=0.2,
        )
        fresh  = [c for c in cands if c["id"] not in used_ids]
        pool   = fresh if fresh else cands
        if not pool:
            continue
        chosen = rng.choice(pool[:min(3, len(pool))])
        used_ids.add(chosen["id"])
        meals.append({"slot": slot, "recipe": chosen})
    return meals


# ─────────────────────────────────────────────────────────────────────────────
# Plotly charts
# ─────────────────────────────────────────────────────────────────────────────
def make_macro_donut(prot_g: float, fat_g: float, carb_g: float) -> go.Figure:
    """Кольцевая диаграмма БЖУ текущего рациона."""
    labels = ["Белки", "Жиры", "Углеводы"]
    values = [round(prot_g * 4), round(fat_g * 9), round(carb_g * 4)]
    colors = ["#4A8060", "#C9923A", "#7262B3"]
    total  = sum(values)

    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.70,
        marker=dict(colors=colors, line=dict(color="#fff", width=2)),
        textinfo="none",
        hovertemplate="<b>%{label}</b><br>%{value} ккал · %{percent}<extra></extra>",
    ))
    fig.add_annotation(
        x=0.5, y=0.5, showarrow=False, align="center",
        text=f"<b>{total}</b><br><span style='font-size:11px;color:#9B9B9B'>ккал</span>",
        font=dict(size=16, family="Inter", color="#1A1A1A"),
    )
    fig.update_layout(
        showlegend=True, height=190,
        margin=dict(l=0, r=10, t=5, b=5),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(
            orientation="v", x=1.02, y=0.5, xanchor="left",
            font=dict(size=11, family="Inter", color="#5A5A5A"),
        ),
    )
    return fig


def make_week_chart(week_plan: list, tdee: float) -> go.Figure:
    """Столбчатый график калорий по дням недели."""
    labels, cals, bar_colors = [], [], []
    for i, (_, meals) in enumerate(week_plan):
        if not meals:
            continue
        total = sum(m["recipe"]["calories"] for m in meals)
        labels.append(DAYS_SHORT[i])
        cals.append(round(total))
        d = abs(total - tdee)
        bar_colors.append("#4A8060" if d <= 150 else ("#C9923A" if d <= 400 else "#B85C38"))

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels, y=cals, marker_color=bar_colors,
        hovertemplate="<b>%{x}</b>: %{y} ккал<extra></extra>",
    ))
    fig.add_hline(
        y=tdee, line_dash="dot", line_color="#9B9B9B", line_width=1.5,
        annotation_text=f"Цель {tdee}", annotation_position="bottom right",
        annotation_font=dict(size=10, color="#9B9B9B"),
    )
    fig.update_layout(
        height=310, margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False, bargap=0.35,
        xaxis=dict(tickfont=dict(size=11, family="Inter", color="#5A5A5A"),
                   gridcolor="rgba(0,0,0,0)", showline=False),
        yaxis=dict(tickfont=dict(size=10, family="Inter", color="#9B9B9B"),
                   gridcolor="#F0EDE8", showline=False, ticksuffix=" ккал"),
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# HTML helpers
# ─────────────────────────────────────────────────────────────────────────────

def cal_progress_html(current: float, target: float, goal: str) -> str:
    """Прогресс-бар калорий с подписью дельты."""
    pct = min(100, current / target * 100) if target > 0 else 0
    d   = current - target
    s   = "+" if d >= 0 else ""

    if goal == "Похудение":
        color = "#4A8060" if d <= 0 else "#B85C38"
    elif goal == "Набор мышечной массы":
        color = "#4A8060" if d >= 0 else "#B85C38"
    else:
        color = "#4A8060" if abs(d) <= 150 else "#C9923A"

    return f"""
    <div style="margin:0 0 14px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:7px;">
        <span style="font-size:.71em;font-weight:600;color:#9B9B9B;
                     text-transform:uppercase;letter-spacing:.05em;">Калории за день</span>
        <span style="font-size:.82em;font-weight:600;color:{color};">{s}{d:.0f} ккал к цели</span>
      </div>
      <div style="background:#EAE7E2;border-radius:100px;height:8px;overflow:hidden;">
        <div style="background:linear-gradient(90deg,{color}AA,{color});
                    width:{pct}%;height:100%;border-radius:100px;"></div>
      </div>
      <div style="display:flex;justify-content:space-between;margin-top:5px;">
        <span style="font-size:.71em;color:#9B9B9B;">{current:.0f} ккал</span>
        <span style="font-size:.71em;color:#9B9B9B;">цель: {target:.0f}</span>
      </div>
    </div>"""


def macro_bar_html(value: float, target: float,
                   label: str, unit: str, color: str) -> str:
    """Прогресс-бар одного нутриента."""
    pct = min(100, value / target * 100) if target > 0 else 0
    d   = value - target
    s   = "+" if d >= 0 else ""
    dc  = "#4A8060" if d >= -5 else "#B85C38"
    return f"""
    <div style="margin-bottom:9px;">
      <div style="display:flex;justify-content:space-between;margin-bottom:3px;">
        <span style="font-size:.70em;font-weight:600;color:#9B9B9B;
                     text-transform:uppercase;letter-spacing:.04em;">{label}</span>
        <span style="font-size:.76em;font-weight:600;color:#1A1A1A;">
          {value:.0f}&nbsp;{unit}
          <span style="color:{dc};font-weight:500;font-size:.88em;">({s}{d:.0f})</span>
          <span style="color:#9B9B9B;font-weight:400;">/ {target:.0f}</span>
        </span>
      </div>
      <div style="background:#EAE7E2;border-radius:100px;height:5px;overflow:hidden;">
        <div style="background:{color};width:{pct}%;height:100%;border-radius:100px;"></div>
      </div>
    </div>"""


def calorie_delta_html(total: float, target: float, goal: str) -> str:
    """Инлайн-бейдж дельты с цветом под цель."""
    d = total - target
    s = "+" if d >= 0 else ""
    if goal == "Похудение":
        color = "#4A8060" if d <= 0 else "#B85C38"
    elif goal == "Набор мышечной массы":
        color = "#4A8060" if d >= 0 else "#B85C38"
    else:
        color = "#4A8060" if abs(d) <= 150 else "#C9923A"
    return f'<span style="color:{color};font-weight:600;">{s}{d:.0f} ккал</span>'


def week_summary_html(week_plan: list, tdee: float, goal: str) -> str:
    """HTML-таблица сводки недели."""
    rows = ""
    for day_name, meals in week_plan:
        if not meals:
            continue
        cal  = sum(m["recipe"]["calories"] for m in meals)
        prot = sum(m["recipe"]["protein"]  for m in meals)
        fat  = sum(m["recipe"]["fat"]      for m in meals)
        carb = sum(m["recipe"]["carbs"]    for m in meals)
        d = cal - tdee
        s = "+" if d >= 0 else ""

        if goal == "Похудение":
            ok = d <= 0
        elif goal == "Набор мышечной массы":
            ok = d >= 0
        else:
            ok = abs(d) <= 150

        ok2  = abs(d) <= 400
        icon = "✅" if ok else ("⚠️" if ok2 else "❌")
        dc   = "#4A8060" if ok else ("#C9923A" if ok2 else "#B85C38")

        rows += (
            f"<tr>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #EEE;color:#1A1A1A;font-weight:600;'>{day_name}</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #EEE;color:#5A5A5A;'>{cal:.0f}</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #EEE;color:#5A5A5A;'>{prot:.0f} г</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #EEE;color:#5A5A5A;'>{fat:.0f} г</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #EEE;color:#5A5A5A;'>{carb:.0f} г</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #EEE;color:{dc};font-weight:600;'>{icon} {s}{d:.0f}</td>"
            f"</tr>"
        )

    th = ("background:#F9F7F4;padding:7px 12px;font-size:.68em;font-weight:700;"
          "text-transform:uppercase;letter-spacing:.06em;color:#9B9B9B;text-align:left;"
          "border-bottom:2px solid #E5DFD5;")
    return (
        f"<div style='background:#fff;border:1px solid #E5DFD5;border-radius:12px;"
        f"overflow:hidden;font-size:.85em;'>"
        f"<table style='width:100%;border-collapse:collapse;'>"
        f"<thead><tr>"
        f"<th style='{th}'>День</th><th style='{th}'>Ккал</th>"
        f"<th style='{th}'>Белки</th><th style='{th}'>Жиры</th>"
        f"<th style='{th}'>Углеводы</th><th style='{th}'>Δ к цели</th>"
        f"</tr></thead>"
        f"<tbody>{rows}</tbody></table></div>"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Export helpers
# ─────────────────────────────────────────────────────────────────────────────

def plan_to_text(day_meals: list, targets: dict) -> str:
    """Красивый экспорт рациона на день."""
    total_cal  = sum(m["recipe"]["calories"] for m in day_meals)
    total_prot = sum(m["recipe"]["protein"]  for m in day_meals)
    total_fat  = sum(m["recipe"]["fat"]      for m in day_meals)
    total_carb = sum(m["recipe"]["carbs"]    for m in day_meals)

    W = 46
    sep  = "─" * W
    dsep = "═" * W

    lines = [
        dsep,
        "  🥗  NutriRec — Персональный рацион на день",
        dsep,
        "",
        f"  📊 Ваши цели:",
        f"     Калории:   {targets['tdee_target']} ккал/день",
        f"     Белки:     {targets['protein_g']} г",
        f"     Жиры:      {targets['fat_g']} г",
        f"     Углеводы:  {targets['carbs_g']} г",
        "",
        sep,
        "",
    ]

    for m in day_meals:
        r  = m["recipe"]
        sl = m["slot"]
        lines += [
            f"  {sl['icon']}  {sl['label'].upper()}",
            f"  {'─' * (W - 2)}",
            f"  {r['name']}",
            "",
            f"  🔥 {r['calories']:.0f} ккал   "
            f"Б: {r['protein']:.0f} г   "
            f"Ж: {r['fat']:.0f} г   "
            f"У: {r['carbs']:.0f} г",
            "",
            f"  Ингредиенты:",
            f"  {r['ingredients']}",
            "",
            f"  Приготовление:",
            f"  {r['steps']}",
            "",
            sep,
            "",
        ]

    lines += [
        f"  📋 ИТОГО ЗА ДЕНЬ:",
        f"     Калории:   {total_cal:.0f} ккал  "
        f"(цель: {targets['tdee_target']}, "
        f"Δ {total_cal - targets['tdee_target']:+.0f})",
        f"     Белки:     {total_prot:.0f} г",
        f"     Жиры:      {total_fat:.0f} г",
        f"     Углеводы:  {total_carb:.0f} г",
        "",
        dsep,
        "  Сформировано с помощью NutriRec",
        dsep,
    ]
    return "\n".join(lines)


def week_to_text(week_plan: list, targets: dict) -> str:
    """Красивый экспорт рациона на неделю."""
    W    = 46
    sep  = "─" * W
    dsep = "═" * W

    lines = [
        dsep,
        "  🥗  NutriRec — Рацион на неделю",
        dsep,
        "",
        f"  📊 Дневная цель: {targets['tdee_target']} ккал",
        f"     Б: {targets['protein_g']} г  "
        f"Ж: {targets['fat_g']} г  "
        f"У: {targets['carbs_g']} г",
        "",
        sep,
        "",
    ]
    for day_name, meals in week_plan:
        if not meals:
            continue
        total = sum(m["recipe"]["calories"] for m in meals)
        d     = total - targets["tdee_target"]
        status = "✅" if abs(d) <= 150 else ("⚠️" if abs(d) <= 400 else "❌")
        lines += [
            f"  📆  {day_name.upper()}   {status}  {total:.0f} ккал (Δ {d:+.0f})",
            f"  {'─' * (W - 2)}",
        ]
        for m in meals:
            r  = m["recipe"]
            sl = m["slot"]
            lines += [
                f"  {sl['icon']} {sl['label']}: {r['name']}",
                f"      {r['calories']:.0f} ккал  "
                f"Б{r['protein']:.0f}г  "
                f"Ж{r['fat']:.0f}г  "
                f"У{r['carbs']:.0f}г",
            ]
        lines += ["", sep, ""]
    lines += [
        "  Сформировано с помощью NutriRec",
        dsep,
    ]
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Recipe card component
# ─────────────────────────────────────────────────────────────────────────────

def recipe_card(
    rec: dict,
    parent=None,
    slot_label: str = "",
    tdee: float = 0,
    meal_fraction: float = 0.25,
    key_prefix: str = "",
):
    """Рендерит карточку рецепта с цветовой идентификацией, прогресс-баром,
    объяснением, кнопкой избранного и слайдером оценки."""
    target      = parent if parent is not None else st
    style       = MEAL_STYLES.get(slot_label, MEAL_STYLES["Обед"])
    meal_target = tdee * meal_fraction if tdee > 0 else rec["calories"]
    cal_pct     = min(100, rec["calories"] / meal_target * 100) if meal_target > 0 else 0
    rid         = rec["id"]
    is_fav      = rid in st.session_state.favorites
    rating      = st.session_state.ratings.get(rid, 0)

    with target.container(border=True):
        # ── Цветной акцент вверху ──
        target.markdown(
            f'<div style="width:40px;height:3px;background:{style["stripe"]};'
            f'border-radius:100px;margin-bottom:12px;"></div>',
            unsafe_allow_html=True,
        )

        # ── Бейдж приёма пищи ──
        if slot_label:
            target.markdown(
                f'<span style="background:{style["bg"]};color:{style["color"]};'
                f'font-size:.70em;font-weight:700;padding:2px 9px;'
                f'border-radius:12px;letter-spacing:.02em;">'
                f'{slot_label}</span>',
                unsafe_allow_html=True,
            )

        # ── Название ──
        target.markdown(
            f'<h3 style="margin:6px 0 10px;font-size:.96em;font-weight:700;'
            f'color:#1A1A1A;line-height:1.45;">{rec["name"]}</h3>',
            unsafe_allow_html=True,
        )

        # ── Макро-чипсы + мини прогресс-бар ──
        target.markdown(f"""
        <div style="display:flex;flex-wrap:wrap;gap:5px;margin-bottom:9px;align-items:center;">
            <span style="background:#F5F2ED;border:1px solid #E5DFD5;border-radius:20px;
                         padding:3px 10px;font-size:.73em;font-weight:600;color:#5A5A5A;">
                🔥 {rec['calories']:.0f} ккал
            </span>
            <span style="background:#EBF5EF;border:1px solid #CEEADB;border-radius:20px;
                         padding:3px 9px;font-size:.73em;font-weight:600;color:#2D5540;">
                Б&nbsp;{rec['protein']:.0f}г
            </span>
            <span style="background:#FBF5E6;border:1px solid #F0D5A0;border-radius:20px;
                         padding:3px 9px;font-size:.73em;font-weight:600;color:#8B621A;">
                Ж&nbsp;{rec['fat']:.0f}г
            </span>
            <span style="background:#F2EEFB;border:1px solid #D9D0F0;border-radius:20px;
                         padding:3px 9px;font-size:.73em;font-weight:600;color:#4D3F8A;">
                У&nbsp;{rec['carbs']:.0f}г
            </span>
            <span style="margin-left:auto;font-size:.69em;color:#9B9B9B;white-space:nowrap;">
                {cal_pct:.0f}% от нормы
            </span>
        </div>
        <div style="background:#EAE7E2;border-radius:100px;height:4px;overflow:hidden;margin-bottom:12px;">
            <div style="background:{style['stripe']};width:{cal_pct}%;height:100%;border-radius:100px;"></div>
        </div>
        <div style="background:#F9F7F4;border-left:3px solid {style['stripe']};
                    border-radius:0 8px 8px 0;padding:8px 12px;
                    font-size:.80em;color:#5A5A5A;line-height:1.65;margin-bottom:12px;">
            ✨ <b>Почему подходит:</b> {rec['explanation']}
        </div>
        """, unsafe_allow_html=True)

        # ── Интерактивная строка: избранное / оценка ──
        fav_col, rate_col = target.columns([1, 4])
        with fav_col:
            if st.button(
                "❤️" if is_fav else "🤍",
                key=f"fav_{key_prefix}_{rid}",
                help="Убрать из избранного" if is_fav else "Добавить в избранное",
            ):
                if is_fav:
                    del st.session_state.favorites[rid]
                else:
                    st.session_state.favorites[rid] = rec
                st.rerun()

        with rate_col:
            selected = st.select_slider(
                "Оценить",
                options=STAR_OPTS,
                value=STAR_OPTS[rating],
                key=f"rate_{key_prefix}_{rid}",
                label_visibility="collapsed",
            )
            new_r = STAR_OPTS.index(selected)
            if new_r != rating:
                st.session_state.ratings[rid] = new_r

        # ── Рецепт (раскрывающийся) ──
        with target.expander("📖 Посмотреть рецепт"):
            st.markdown(f"**Ингредиенты:** {rec['ingredients']}")
            st.markdown(f"**Приготовление:** {rec['steps']}")


# ─────────────────────────────────────────────────────────────────────────────
# Render helpers
# ─────────────────────────────────────────────────────────────────────────────

def render_day(meals: list[dict], tdee: float = 0, key_prefix: str = ""):
    """2-колоночная сетка из 4 приёмов пищи."""
    cols = st.columns(2)
    for i, meal in enumerate(meals):
        col   = cols[i % 2]
        slot  = meal["slot"]
        style = MEAL_STYLES.get(slot["label"], MEAL_STYLES["Обед"])
        mt    = tdee * slot["fraction"]

        col.markdown(f"""
        <div style="display:flex;align-items:center;gap:8px;margin:18px 0 8px;">
            <div style="background:{style['bg']};border-radius:50%;width:32px;height:32px;
                        display:flex;align-items:center;justify-content:center;flex-shrink:0;">
                {slot['icon']}
            </div>
            <span style="font-weight:700;font-size:.9em;color:#1A1A1A;">{slot['label']}</span>
            <span style="font-size:.72em;color:#9B9B9B;margin-left:auto;">~{mt:.0f} ккал</span>
        </div>""", unsafe_allow_html=True)

        recipe_card(
            meal["recipe"], col,
            slot_label=slot["label"], tdee=tdee,
            meal_fraction=slot["fraction"], key_prefix=key_prefix,
        )


def render_day_metrics(meals: list[dict], targets: dict, goal: str) -> float:
    """Прогресс-бары КБЖУ + кольцевая диаграмма."""
    total_cal  = sum(m["recipe"]["calories"] for m in meals)
    total_prot = sum(m["recipe"]["protein"]  for m in meals)
    total_fat  = sum(m["recipe"]["fat"]      for m in meals)
    total_carb = sum(m["recipe"]["carbs"]    for m in meals)
    tdee       = targets["tdee_target"]

    bar_col, donut_col = st.columns([1.8, 1])
    with bar_col:
        st.markdown(
            cal_progress_html(total_cal, tdee, goal)
            + macro_bar_html(total_prot, targets["protein_g"], "Белки",    "г", "#4A8060")
            + macro_bar_html(total_fat,  targets["fat_g"],     "Жиры",     "г", "#C9923A")
            + macro_bar_html(total_carb, targets["carbs_g"],   "Углеводы", "г", "#7262B3"),
            unsafe_allow_html=True,
        )
    with donut_col:
        st.plotly_chart(
            make_macro_donut(total_prot, total_fat, total_carb),
            use_container_width=True,
            config={"displayModeBar": False},
        )
    return total_cal


def empty_state_ui(
    emoji: str, title: str, body: str,
    btn_label: str = "", btn_key: str = "",
) -> bool:
    """Пустой экран с кнопкой генерации."""
    st.markdown(f"""
    <div style="text-align:center;padding:60px 20px 40px;">
        <div style="font-size:3.2em;margin-bottom:14px;">{emoji}</div>
        <h2 style="font-size:1.2em;font-weight:700;color:#5A5A5A;margin-bottom:8px;">{title}</h2>
        <p style="color:#9B9B9B;font-size:.88em;line-height:1.75;
                  max-width:360px;margin:0 auto 24px;">{body}</p>
    </div>""", unsafe_allow_html=True)
    if btn_label:
        _, c, _ = st.columns([2, 1.6, 2])
        with c:
            return st.button(btn_label, type="primary",
                             use_container_width=True, key=btn_key)
    return False


# ═════════════════════════════════════════════════════════════════════════════
# AUTH GATE — пока не авторизован, показываем экран входа/регистрации
# ═════════════════════════════════════════════════════════════════════════════
if not st.session_state.authenticated:
    _, auth_col, _ = st.columns([1, 2, 1])
    with auth_col:
        st.markdown("""
        <div style="text-align:center;padding:40px 0 28px;">
            <div style="font-size:2.6em;margin-bottom:8px;">🥗</div>
            <h1 style="font-size:1.8em;font-weight:800;color:#1A1A1A;
                       letter-spacing:-.04em;margin:0 0 6px;">NutriRec</h1>
            <p style="color:#9B9B9B;font-size:.9em;margin:0;">
                Персональные рекомендации питания
            </p>
        </div>""", unsafe_allow_html=True)

        login_tab, reg_tab = st.tabs(["🔑 Войти", "🆕 Регистрация"])

        with login_tab:
            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
            l_user = st.text_input("Логин", placeholder="Ваше имя пользователя", key="l_user")
            l_pass = st.text_input("Пароль", type="password",
                                   placeholder="Введите пароль", key="l_pass")
            st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)
            if st.button("Войти", type="primary",
                         use_container_width=True, key="btn_login"):
                if not l_user.strip() or not l_pass:
                    st.error("Заполните все поля.")
                else:
                    ok, dname, err = authenticate(l_user, l_pass)
                    if ok:
                        ukey = l_user.strip().lower()
                        data = load_profile(ukey)
                        st.session_state.authenticated = True
                        st.session_state.username      = ukey
                        st.session_state.display_name  = dname
                        st.session_state.profile_name  = ukey
                        st.session_state["_profile_loaded"] = ukey
                        st.session_state.favorites     = data["favorites"]
                        st.session_state.ratings       = data["ratings"]
                        st.session_state.saved_plans   = data["saved_plans"]
                        st.rerun()
                    else:
                        st.error(err)

        with reg_tab:
            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
            r_name = st.text_input("Имя пользователя",
                                   placeholder="Будет использоваться для входа",
                                   key="r_user")
            r_disp = st.text_input("Отображаемое имя (необязательно)",
                                   placeholder="Например: Анна Петрова",
                                   key="r_disp")
            r_pass  = st.text_input("Пароль", type="password",
                                    placeholder="Минимум 6 символов",
                                    key="r_pass")
            r_pass2 = st.text_input("Подтвердите пароль", type="password",
                                    placeholder="Повторите пароль",
                                    key="r_pass2")
            st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)
            if st.button("Зарегистрироваться", type="primary",
                         use_container_width=True, key="btn_register"):
                if r_pass != r_pass2:
                    st.error("Пароли не совпадают.")
                else:
                    ok, err = register_user(r_name, r_pass, r_disp)
                    if ok:
                        ukey = r_name.strip().lower()
                        dname = r_disp.strip() or r_name.strip()
                        data  = load_profile(ukey)
                        st.session_state.authenticated = True
                        st.session_state.username      = ukey
                        st.session_state.display_name  = dname
                        st.session_state.profile_name  = ukey
                        st.session_state["_profile_loaded"] = ukey
                        st.session_state.favorites     = data["favorites"]
                        st.session_state.ratings       = data["ratings"]
                        st.session_state.saved_plans   = data["saved_plans"]
                        st.success(f"Добро пожаловать, {dname}! Вход выполнен.")
                        st.rerun()
                    else:
                        st.error(err)

    st.stop()   # Не отображать главный интерфейс пока не авторизован


# ═════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    # Brand
    st.markdown("""
    <div style="padding:10px 0 18px;">
        <div style="font-size:1.55em;font-weight:800;color:#fff;letter-spacing:-.03em;">
            🥗 NutriRec
        </div>
        <div style="font-size:.72em;color:rgba(255,255,255,.36);margin-top:3px;font-weight:400;">
            Персональные рекомендации питания
        </div>
    </div>""", unsafe_allow_html=True)

    # ── Пользователь ────────────────────────────────────────────────────────────
    dname = st.session_state.get("display_name", "") or st.session_state.get("username", "")
    favs_count  = len(st.session_state.get("favorites", {}))
    plans_count = len(st.session_state.get("saved_plans", []))
    st.markdown(
        f"""<div style="background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.10);
                    border-radius:10px;padding:12px 14px;margin-bottom:16px;
                    display:flex;align-items:center;gap:11px;">
            <div style="background:rgba(255,255,255,.12);border-radius:50%;
                        width:34px;height:34px;display:flex;align-items:center;
                        justify-content:center;font-size:1.1em;flex-shrink:0;">👤</div>
            <div style="flex:1;min-width:0;">
                <div style="font-weight:700;color:#fff;font-size:.9em;
                            white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{dname}</div>
                <div style="font-size:.68em;color:rgba(255,255,255,.38);margin-top:2px;">
                    {favs_count} ♥ &nbsp;·&nbsp; {plans_count} 🗂</div>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )
    if st.button("🚶 Выйти из аккаунта",
                 use_container_width=True, key="btn_logout"):
        for _k in ["authenticated", "username", "display_name", "profile_name",
                   "_profile_loaded", "favorites", "ratings", "saved_plans",
                   "day_plan", "week_plan", "view", "regen_seed", "shown_ids"]:
            if _k in st.session_state:
                del st.session_state[_k]
        st.rerun()
    # ── /Пользователь ──────────────────────────────────────────────────────

    st.markdown("**Пол**")
    gender = st.radio("Пол", ["Мужчина", "Женщина"],
                      horizontal=True, label_visibility="collapsed")

    col_a, col_w = st.columns(2)
    with col_a:
        age = st.number_input("Возраст", 18, 100, 25)
    with col_w:
        weight = st.number_input("Вес (кг)", 40.0, 200.0, 65.0, 0.5)

    for _k, _v in [("_h_slider", 170), ("_h_input", 170)]:
        if _k not in st.session_state:
            st.session_state[_k] = _v

    def _on_slider():
        st.session_state["_h_input"] = st.session_state["_h_slider"]

    def _on_input():
        v = int(max(140, min(220, st.session_state.get("_h_input", 170))))
        st.session_state["_h_slider"] = v
        st.session_state["_h_input"]  = v

    st.markdown("**Рост (см)**")
    hc1, hc2 = st.columns([3, 1])
    with hc1:
        st.slider("", 140, 220, key="_h_slider",
                  on_change=_on_slider, label_visibility="collapsed")
    with hc2:
        st.number_input("", 140, 220, step=1, key="_h_input",
                        on_change=_on_input, label_visibility="collapsed")
    height = int(st.session_state["_h_slider"])

    st.markdown("---")
    st.markdown("**Уровень активности**")
    activity = st.selectbox("Активность", list(ACTIVITY_LEVELS.keys()),
                             label_visibility="collapsed")
    st.markdown("**Цель**")
    goal = st.selectbox("Цель", list(GOALS.keys()), label_visibility="collapsed")

    st.markdown("---")
    st.markdown("**Аллергии / ограничения**")
    allergens = st.multiselect("Аллергии", list(ALLERGEN_KEYWORDS.keys()),
                                label_visibility="collapsed")

    st.markdown("---")

    # TDEE preview — обновляется в реальном времени
    targets = calculate_user_targets(gender, weight, height, age, activity, goal)
    st.markdown(f"""
    <div style="background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.09);
                border-radius:12px;padding:12px 16px;margin-bottom:16px;">
        <div style="font-size:.66em;color:rgba(255,255,255,.38);text-transform:uppercase;
                    letter-spacing:.06em;margin-bottom:4px;">Ваша норма</div>
        <div style="font-size:1.35em;font-weight:700;color:#fff;line-height:1.2;">
            {targets['tdee_target']} ккал/день
        </div>
        <div style="font-size:.70em;color:rgba(255,255,255,.36);margin-top:4px;">
            ИМТ {targets['bmi']} · {targets['bmi_cat']}&nbsp;&nbsp;
            Б {targets['protein_g']}г · Ж {targets['fat_g']}г · У {targets['carbs_g']}г
        </div>
    </div>""", unsafe_allow_html=True)

    btn_day  = st.button("📅 Рацион на день",    use_container_width=True, type="primary")
    btn_week = st.button("🗓️ Рацион на неделю", use_container_width=True)


# ═════════════════════════════════════════════════════════════════════════════
# USER PROFILE + handle sidebar buttons
# ═════════════════════════════════════════════════════════════════════════════
user_profile = dict(
    gender=gender, age=age, height=height, weight=weight,
    activity=activity, goal=goal, allergens=allergens,
)

if btn_day:
    st.session_state.update(dict(view="day",  day_plan=None,  regen_seed=0, shown_ids=set()))
if btn_week:
    st.session_state.update(dict(view="week", week_plan=None, regen_seed=0, shown_ids=set()))

# ── Авто-сохранение в профиль ────────────────────────────────────────────────
def _autosave():
    pname = st.session_state.get("profile_name", "")
    if not pname:
        return
    data = load_profile(pname)
    data["favorites"]   = st.session_state.favorites
    data["ratings"]     = st.session_state.ratings
    data["saved_plans"] = st.session_state.saved_plans
    data["settings"]    = user_profile
    save_profile(pname, data)

_autosave()


# ═════════════════════════════════════════════════════════════════════════════
# MAIN — Header + Metrics
# ═════════════════════════════════════════════════════════════════════════════
st.markdown("""
<h1 style="margin:0 0 4px;font-size:2em;font-weight:800;color:#1A1A1A;letter-spacing:-.04em;">
    Рекомендации питания
</h1>
<p style="color:#9B9B9B;margin:0 0 20px;font-size:.9em;font-weight:400;">
    Персональный план на основе ваших параметров и целей
</p>""", unsafe_allow_html=True)

mc1, mc2, mc3, mc4, mc5 = st.columns(5)
mc1.metric("ИМТ",          f"{targets['bmi']}  ·  {targets['bmi_cat']}")
mc2.metric("Калорий/день", f"{targets['tdee_target']} ккал")
mc3.metric("Белки",        f"{targets['protein_g']} г")
mc4.metric("Жиры",         f"{targets['fat_g']} г")
mc5.metric("Углеводы",     f"{targets['carbs_g']} г")

st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
# TABS
# ═════════════════════════════════════════════════════════════════════════════
tab_day, tab_week, tab_search, tab_favs, tab_cabinet = st.tabs(
    ["📅 День", "🗓️ Неделя", "🔍 Поиск", "❤️ Избранное", "👤 Кабинет"]
)


# ── Tab: День ─────────────────────────────────────────────────────────────────
with tab_day:
    if st.session_state.view == "day":
        # Автогенерация если нет готового плана
        if st.session_state.day_plan is None:
            with st.spinner("Подбираем блюда под ваш профиль…"):
                wids = st.session_state.shown_ids.copy()
                st.session_state.day_plan = generate_day(
                    user_profile, wids, seed=st.session_state.regen_seed
                )
                for m in st.session_state.day_plan:
                    wids.add(m["recipe"]["id"])
                st.session_state.shown_ids = wids

        day_meals = st.session_state.day_plan

        if not day_meals:
            st.warning(
                "Не удалось подобрать блюда с учётом ваших ограничений. "
                "Попробуйте уменьшить количество фильтров."
            )
        else:
            tdee = targets["tdee_target"]
            # Заголовок + кнопка скачивания
            hcol, dlcol = st.columns([3, 1])
            with hcol:
                st.markdown(f"""
                <h2 style="margin:0 0 3px;font-size:1.2em;">📅 Рацион на день</h2>
                <p style="color:#9B9B9B;margin:0;font-size:.81em;">
                    Суточная цель: {tdee} ккал &nbsp;·&nbsp;
                    Завтрак ~{round(tdee*.25)} &nbsp;·&nbsp;
                    Перекус ~{round(tdee*.10)} &nbsp;·&nbsp;
                    Обед ~{round(tdee*.35)} &nbsp;·&nbsp;
                    Ужин ~{round(tdee*.30)}
                </p>""", unsafe_allow_html=True)
            with dlcol:
                st.download_button(
                    label="⬇️ Скачать план",
                    data=plan_to_text(day_meals, targets).encode("utf-8"),
                    file_name="NutriRec_рацион_на_день.txt",
                    mime="text/plain; charset=utf-8",
                    use_container_width=True,
                )

            st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
            render_day_metrics(day_meals, targets, goal)
            render_day(day_meals, tdee=tdee, key_prefix="day")

            btn_r, btn_s, _ = st.columns([2, 2, 3])
            with btn_r:
                if st.button("🔄 Сгенерировать заново", key="regen_day"):
                    for m in day_meals:
                        st.session_state.shown_ids.add(m["recipe"]["id"])
                    st.session_state.regen_seed += 1
                    st.session_state.day_plan   = None
                    st.rerun()
            with btn_s:
                pname = st.session_state.get("profile_name", "")
                if pname:
                    if st.button("💾 Сохранить рацион", key="save_day", type="primary"):
                        rec = make_day_plan_record(day_meals, targets)
                        st.session_state.saved_plans.insert(0, rec)
                        _autosave()
                        st.success("✅ Рацион сохранён в профиль!")
                else:
                    st.caption("🔒 Войдите в профиль чтобы сохранить")
    else:
        if empty_state_ui(
            "📅", "Рацион на день не сформирован",
            "Заполните профиль в боковой панели и нажмите кнопку ниже, "
            "чтобы получить персональный план питания на сегодня.",
            "📅 Сформировать рацион на день", "gen_day_tab",
        ):
            st.session_state.update(dict(view="day", day_plan=None,
                                         regen_seed=0, shown_ids=set()))
            st.rerun()


# ── Tab: Неделя ────────────────────────────────────────────────────────────────
with tab_week:
    if st.session_state.view == "week":
        if st.session_state.week_plan is None:
            prog = st.progress(0, text="Составляем рацион на неделю…")
            used = st.session_state.shown_ids.copy()
            seed = st.session_state.regen_seed
            wplan = []
            for i, day_name in enumerate(DAYS_RU):
                prog.progress((i + 1) / 7, text=f"📅 {day_name}…")
                dm = generate_day(user_profile, used, seed=seed + i)
                wplan.append((day_name, dm))
            prog.empty()
            st.session_state.week_plan = wplan
            st.session_state.shown_ids = used

        week_plan = st.session_state.week_plan
        tdee      = targets["tdee_target"]

        # Заголовок + скачать
        wh_col, wdl_col = st.columns([3, 1])
        with wh_col:
            st.markdown(f"""
            <h2 style="margin:0 0 3px;font-size:1.2em;">🗓️ Рацион на неделю</h2>
            <p style="color:#9B9B9B;margin:0;font-size:.81em;">
                Блюда не повторяются &nbsp;·&nbsp; Цель {tdee} ккал/день
            </p>""", unsafe_allow_html=True)
        with wdl_col:
            st.download_button(
                label="⬇️ Скачать план",
                data=week_to_text(week_plan, targets).encode("utf-8"),
                file_name="NutriRec_рацион_на_неделю.txt",
                mime="text/plain",
                use_container_width=True,
            )

        st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)

        # График + сводная таблица рядом
        chart_col, table_col = st.columns([1, 1.5])
        with chart_col:
            st.markdown(
                "<p style='font-size:.76em;font-weight:700;color:#9B9B9B;"
                "text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px;'>"
                "Калории по дням</p>", unsafe_allow_html=True
            )
            st.plotly_chart(
                make_week_chart(week_plan, tdee),
                use_container_width=True,
                config={"displayModeBar": False},
            )
        with table_col:
            st.markdown(
                "<p style='font-size:.76em;font-weight:700;color:#9B9B9B;"
                "text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px;'>"
                "Сводка</p>", unsafe_allow_html=True
            )
            st.markdown(week_summary_html(week_plan, tdee, goal), unsafe_allow_html=True)

        st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

        # ── Недельная аналитика ──────────────────────────────────────────────
        valid_days = [(dn, dm) for dn, dm in week_plan if dm]
        day_cals   = [(dn, sum(m["recipe"]["calories"] for m in dm)) for dn, dm in valid_days]
        day_prots  = [(dn, sum(m["recipe"]["protein"]  for m in dm)) for dn, dm in valid_days]
        day_carbs  = [(dn, sum(m["recipe"]["carbs"]    for m in dm)) for dn, dm in valid_days]
        day_fats   = [(dn, sum(m["recipe"]["fat"]      for m in dm)) for dn, dm in valid_days]

        avg_cal   = sum(c for _, c in day_cals)   / len(day_cals)
        avg_prot  = sum(p for _, p in day_prots)  / len(day_prots)
        avg_fat   = sum(f for _, f in day_fats)   / len(day_fats)
        avg_carb  = sum(c for _, c in day_carbs)  / len(day_carbs)
        total_week_cal = sum(c for _, c in day_cals)

        # дни в норме (±150 ккал от цели — для поддержания; или d≤0/d≥0 для похудения/набора)
        def day_ok(cal):
            d = cal - tdee
            if goal == "Похудение":             return d <= 0
            elif goal == "Набор мышечной массы": return d >= 0
            else:                                return abs(d) <= 150

        ok_days   = sum(1 for _, c in day_cals if day_ok(c))
        compliance = round(ok_days / len(day_cals) * 100)

        best_day  = min(day_cals, key=lambda x: abs(x[1] - tdee))
        most_prot_day = max(day_prots, key=lambda x: x[1])

        st.markdown(
            "<p style='font-size:.76em;font-weight:700;color:#9B9B9B;"
            "text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px;'>"
            "Аналитика недели</p>",
            unsafe_allow_html=True,
        )

        def stat_card(emoji, label, value, sub="", color="#1A1A1A"):
            return (
                f"<div style='background:#fff;border:1px solid #E5DFD5;border-radius:12px;"
                f"padding:14px 18px;'>"
                f"<div style='font-size:.68em;font-weight:600;color:#9B9B9B;"
                f"text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px;'>"
                f"{emoji} {label}</div>"
                f"<div style='font-size:1.3em;font-weight:700;color:{color};line-height:1.2;'>"
                f"{value}</div>"
                f"<div style='font-size:.74em;color:#9B9B9B;margin-top:3px;'>{sub}</div>"
                f"</div>"
            )

        sc1, sc2, sc3, sc4, sc5 = st.columns(5)
        delta_avg = avg_cal - tdee
        avg_color = "#4A8060" if day_ok(avg_cal) else ("#C9923A" if abs(delta_avg) <= 400 else "#B85C38")

        sc1.markdown(stat_card(
            "🔥", "Средние калории",
            f"{avg_cal:.0f} ккал",
            f"Δ {delta_avg:+.0f} к цели {tdee}",
            avg_color,
        ), unsafe_allow_html=True)

        comp_color = "#4A8060" if compliance >= 70 else ("#C9923A" if compliance >= 40 else "#B85C38")
        sc2.markdown(stat_card(
            "🎯", "Попадание в норму",
            f"{compliance}%",
            f"{ok_days} из {len(day_cals)} дней",
            comp_color,
        ), unsafe_allow_html=True)

        sc3.markdown(stat_card(
            "📅", "Лучший день",
            best_day[0],
            f"{best_day[1]:.0f} ккал (Δ {best_day[1]-tdee:+.0f})",
            "#4A8060",
        ), unsafe_allow_html=True)

        sc4.markdown(stat_card(
            "💪", "Больше всего белка",
            most_prot_day[0],
            f"{most_prot_day[1]:.0f} г белка",
            "#7262B3",
        ), unsafe_allow_html=True)

        sc5.markdown(stat_card(
            "📊", "Неделя итого",
            f"{total_week_cal:.0f} ккал",
            f"Avg Б {avg_prot:.0f}г · Ж {avg_fat:.0f}г · У {avg_carb:.0f}г",
        ), unsafe_allow_html=True)

        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

        # Раскрывающиеся карточки по дням

        for day_idx, (day_name, day_meals) in enumerate(week_plan):
            if not day_meals:
                continue
            total_cal  = sum(m["recipe"]["calories"] for m in day_meals)
            delta_html = calorie_delta_html(total_cal, tdee, goal)
            with st.expander(
                f"📆 {day_name}  —  {total_cal:.0f} ккал",
                expanded=(day_idx == 0),
            ):
                st.markdown(
                    f"<p style='margin:0 0 12px;font-size:.86em;color:#5A5A5A;'>"
                    f"Суточная сумма: <b>{total_cal:.0f} ккал</b>"
                    f" &nbsp; {delta_html} &nbsp; (цель: {tdee} ккал)</p>",
                    unsafe_allow_html=True,
                )
                render_day(day_meals, tdee=tdee, key_prefix=f"week_{day_idx}")

        if st.button("🔄 Сгенерировать заново", key="regen_week"):
            for _, dm in week_plan:
                for m in dm:
                    st.session_state.shown_ids.add(m["recipe"]["id"])
            st.session_state.regen_seed += 1
            st.session_state.week_plan   = None
            st.rerun()

        # Кнопка сохранения недельного рациона
        pname_w = st.session_state.get("profile_name", "")
        if pname_w:
            if st.button("💾 Сохранить недельный рацион", key="save_week", type="primary"):
                rec_w = make_week_plan_record(week_plan, targets)
                st.session_state.saved_plans.insert(0, rec_w)
                _autosave()
                st.success("✅ Недельный рацион сохранён в профиль!")
        else:
            st.caption("🔒 Войдите в профиль чтобы сохранить рацион")
    else:
        if empty_state_ui(
            "🗓️", "Рацион на неделю не сформирован",
            "Нажмите кнопку ниже, чтобы получить недельный план питания "
            "с уникальными блюдами на каждый день.",
            "🗓️ Сформировать рацион на неделю", "gen_week_tab",
        ):
            st.session_state.update(dict(view="week", week_plan=None,
                                          regen_seed=0, shown_ids=set()))
            st.rerun()


# ── Tab: Поиск ─────────────────────────────────────────────────────────────────
with tab_search:
    st.markdown(
        "<h2 style='margin:0 0 14px;font-size:1.2em;'>🔍 Поиск рецептов</h2>",
        unsafe_allow_html=True,
    )
    sq_col, sb_col = st.columns([5, 1])
    with sq_col:
        query = st.text_input(
            "Запрос",
            placeholder="Например: быстрый белковый завтрак без мяса",
            label_visibility="collapsed",
            key="search_query",
        )
    with sb_col:
        search_clicked = st.button("Найти", type="primary", use_container_width=True)

    # Фильтры
    with st.expander("⚙️ Фильтры"):
        fc1, fc2 = st.columns([2, 1])
        with fc1:
            cal_min, cal_max = st.slider(
                "Калории на порцию (ккал)", 50, 1500, (100, 800), step=25,
            )
        with fc2:
            no_meat = st.checkbox("Без красного мяса")
        st.caption("Ограничения из профиля применяются автоматически")

    if search_clicked:
        if not query.strip():
            st.warning("Введите запрос — опишите, что хотите приготовить.")
        else:
            _p = user_profile.copy()
            if no_meat and "Красное мясо" not in _p["allergens"]:
                _p["allergens"] = _p["allergens"] + ["Красное мясо"]
            with st.spinner("Ищем идеальные рецепты для вас…"):
                results = recsys.recommend(_p, query, top_n=8)
            results = [r for r in results if cal_min <= r["calories"] <= cal_max]
            if not results:
                st.info(
                    "По вашему запросу с учётом фильтров ничего не найдено. "
                    "Попробуйте расширить диапазон калорий или изменить запрос."
                )
            else:
                st.markdown(
                    f"<p style='font-size:.86em;color:#9B9B9B;margin-bottom:12px;'>"
                    f"Найдено: <b style='color:#4A8060;'>{len(results)}</b> рецептов</p>",
                    unsafe_allow_html=True,
                )
                for i in range(0, len(results), 2):
                    cols = st.columns(2)
                    for j, col in enumerate(cols):
                        idx = i + j
                        if idx < len(results):
                            recipe_card(
                                results[idx], col,
                                tdee=targets["tdee_target"],
                                meal_fraction=0.33,
                                key_prefix=f"search_{idx}",
                            )
    elif not query:
        st.markdown("""
        <div style="text-align:center;padding:50px 0;color:#9B9B9B;">
            <div style="font-size:2.8em;margin-bottom:14px;">🔍</div>
            <p style="font-size:.88em;line-height:1.8;max-width:340px;margin:0 auto;">
                Введите запрос в строку поиска.<br>
                Например: <i>«быстрый завтрак»</i>, <i>«высокобелковый ужин»</i>,<br>
                <i>«лёгкий суп без глютена»</i>
            </p>
        </div>""", unsafe_allow_html=True)


# ── Tab: Избранное ─────────────────────────────────────────────────────────────
with tab_favs:
    favs    = st.session_state.favorites
    ratings = st.session_state.ratings

    if not favs:
        empty_state_ui(
            "🤍", "Избранное пока пусто",
            "Нажимайте ❤️ на карточках рецептов, "
            "чтобы сохранять любимые блюда здесь.",
        )
    else:
        fav_h_col, fav_clr_col = st.columns([3, 1])
        with fav_h_col:
            st.markdown(
                f"<h2 style='margin:0 0 4px;font-size:1.2em;'>❤️ Избранное</h2>"
                f"<p style='color:#9B9B9B;margin:0;font-size:.81em;'>"
                f"{len(favs)} сохранённых рецептов · по убыванию оценки</p>",
                unsafe_allow_html=True,
            )
        with fav_clr_col:
            if st.button("🗑️ Очистить", type="secondary", use_container_width=True):
                st.session_state.favorites = {}
                st.rerun()

        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

        # Сортировка по оценке (убывание)
        sorted_favs = sorted(favs.values(), key=lambda r: -ratings.get(r["id"], 0))

        for i in range(0, len(sorted_favs), 2):
            cols = st.columns(2)
            for j, col in enumerate(cols):
                idx = i + j
                if idx < len(sorted_favs):
                    rec = sorted_favs[idx]
                    r   = ratings.get(rec["id"], 0)
                    if r > 0:
                        col.markdown(
                            f'<p style="font-size:.73em;color:#C9923A;margin:0 0 4px;">'
                            f'{"⭐" * r}</p>',
                            unsafe_allow_html=True,
                        )
                    recipe_card(
                        rec, col,
                        tdee=targets["tdee_target"],
                        meal_fraction=0.33,
                        key_prefix=f"fav_{idx}",
                    )


# ══ Tab: Кабинет ─────────────────────────────────────────────────────────────────
with tab_cabinet:
    pname_c = st.session_state.get("profile_name", "")

    if not pname_c:
        # Нет профиля
        st.markdown("""
        <div style="text-align:center;padding:60px 20px 40px;">
            <div style="font-size:3.2em;margin-bottom:14px;">👤</div>
            <h2 style="font-size:1.2em;font-weight:700;color:#5A5A5A;margin-bottom:8px;">
                Личный кабинет</h2>
            <p style="color:#9B9B9B;font-size:.88em;line-height:1.75;
                      max-width:380px;margin:0 auto;">
                Выберите или создайте профиль в боковой панели, чтобы
                сохранять рационы, избранное и оценки между сессиями.
            </p>
        </div>""", unsafe_allow_html=True)
    else:
        saved = st.session_state.saved_plans
        favs_c   = st.session_state.favorites
        ratings_c = st.session_state.ratings

        # ── Заголовок профиля ────────────────────────────────────────────────────────────
        avg_rating = (
            sum(ratings_c.values()) / len(ratings_c) if ratings_c else 0
        )
        n_day_plans  = sum(1 for p in saved if p["type"] == "day")
        n_week_plans = sum(1 for p in saved if p["type"] == "week")

        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#1B3A2D,#2D5540);
                    border-radius:16px;padding:24px 28px;margin-bottom:20px;
                    display:flex;align-items:center;gap:22px;">
            <div style="background:rgba(255,255,255,.1);border-radius:50%;
                        width:56px;height:56px;display:flex;align-items:center;
                        justify-content:center;font-size:1.7em;flex-shrink:0;">👤</div>
            <div>
                <div style="font-size:1.35em;font-weight:800;color:#fff;
                            letter-spacing:-.03em;margin-bottom:4px;">{pname_c}</div>
                <div style="font-size:.80em;color:rgba(255,255,255,.56);">
                    {len(favs_c)} избранных · {len(saved)} рационов ·
                    {'★' * round(avg_rating) + '☆' * (5 - round(avg_rating))}
                    &nbsp;{avg_rating:.1f} ср. оценка
                </div>
            </div>
            <div style="margin-left:auto;display:flex;gap:24px;text-align:center;">
                <div>
                    <div style="font-size:1.5em;font-weight:700;color:#fff;">{n_day_plans}</div>
                    <div style="font-size:.70em;color:rgba(255,255,255,.46);
                                text-transform:uppercase;letter-spacing:.05em;">Дней</div>
                </div>
                <div>
                    <div style="font-size:1.5em;font-weight:700;color:#fff;">{n_week_plans}</div>
                    <div style="font-size:.70em;color:rgba(255,255,255,.46);
                                text-transform:uppercase;letter-spacing:.05em;">Недель</div>
                </div>
                <div>
                    <div style="font-size:1.5em;font-weight:700;color:#fff;">{len(ratings_c)}</div>
                    <div style="font-size:.70em;color:rgba(255,255,255,.46);
                                text-transform:uppercase;letter-spacing:.05em;">Оценок</div>
                </div>
            </div>
        </div>""", unsafe_allow_html=True)

        # ── Сохранённые рационы ────────────────────────────────────────────────────────────
        st.markdown(
            "<h3 style='font-size:1.05em;font-weight:700;margin:0 0 12px;'>"
            "🗂️ Сохранённые рационы</h3>", unsafe_allow_html=True
        )

        if not saved:
            st.markdown(
                "<p style='color:#9B9B9B;font-size:.88em;'>"
                "Нет сохранённых рационов. Нажмите «💾 Сохранить» на вкладке День или Неделя.<br>"
                "Данные сохраняются между сессиями и рестартами приложения.</p>",
                unsafe_allow_html=True,
            )
        else:
            for p_idx, plan in enumerate(saved):
                is_day  = plan["type"] == "day"
                icon    = "📅" if is_day else "🗓️"
                tc      = plan.get("total_cal") or plan.get("avg_cal", 0)
                tgt     = plan.get("target_cal", 0)
                delta   = tc - tgt
                ds      = f"{delta:+.0f}"
                dc      = "#4A8060" if abs(delta) <= 150 else ("#C9923A" if abs(delta) <= 400 else "#B85C38")
                sub     = f"· {tc:.0f} ккал ({'Δ' + ds if tgt else ''})" if tc else ""

                with st.container(border=True):
                    hc, ac = st.columns([4, 1])
                    with hc:
                        st.markdown(
                            f"<div style='display:flex;align-items:center;gap:10px;'>"
                            f"<span style='font-size:1.4em;'>{icon}</span>"
                            f"<div>"
                            f"<div style='font-weight:700;font-size:.95em;color:#1A1A1A;'>{plan['title']}</div>"
                            f"<div style='font-size:.76em;color:#9B9B9B;margin-top:1px;'>"
                            f"{'Дневной' if is_day else 'Недельный'} рацион &nbsp; "
                            f"<span style='color:{dc};font-weight:600;'>{sub}</span></div>"
                            f"</div></div>",
                            unsafe_allow_html=True,
                        )
                    with ac:
                        if st.button("🗑️", key=f"del_plan_{p_idx}",
                                     help="Удалить рацион"):
                            st.session_state.saved_plans.pop(p_idx)
                            _autosave()
                            st.rerun()

                    # Развернуть подробности
                    with st.expander("🔍 Посмотреть состав"):
                        if is_day:
                            for m in plan.get("meals", []):
                                sl = m["slot"]
                                r  = m["recipe"]
                                st.markdown(
                                    f"**{sl['icon']} {sl['label']}** &nbsp; {r['name']} &nbsp; "
                                    f"*{r['calories']:.0f} ккал*"
                                )
                        else:
                            for day_rec in plan.get("days", []):
                                dn    = day_rec["day_name"]
                                dm    = day_rec["meals"]
                                dcal  = sum(m["recipe"]["calories"] for m in dm)
                                st.markdown(f"**📆 {dn}** &nbsp; — &nbsp; {dcal:.0f} ккал")
                                for m in dm:
                                    sl = m["slot"]
                                    r  = m["recipe"]
                                    st.markdown(
                                        f"&nbsp;&nbsp; {sl['icon']} {sl['label']}: "
                                        f"{r['name']} *({r['calories']:.0f} ккал)*"
                                    )

        # ── Лучшие оценки ───────────────────────────────────────────────────────────────
        if ratings_c:
            st.markdown(
                "<h3 style='font-size:1.05em;font-weight:700;margin:20px 0 12px;'>"
                "⭐ Оценённые рецепты</h3>",
                unsafe_allow_html=True,
            )
            top_rated = sorted(
                [(rid, r) for rid, r in ratings_c.items() if r >= 4],
                key=lambda x: -x[1],
            )
            if top_rated:
                for rid, r in top_rated[:6]:
                    rec_r  = favs_c.get(rid)
                    name_r = rec_r["name"] if rec_r else f"#{rid}"
                    stars  = "★" * r
                    st.markdown(
                        f"<div style='display:flex;align-items:center;gap:10px;"
                        f"padding:7px 12px;background:#fff;border:1px solid #E5DFD5;"
                        f"border-radius:10px;margin-bottom:6px;'>"
                        f"<span style='color:#C9923A;font-size:1.0em;'>{stars}</span>"
                        f"<span style='font-size:.88em;color:#1A1A1A;'>{name_r}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("Оценки 4+ звезды пока не выставлены.")

        # ── Опасная зона: удалить профиль ───────────────────────────────────────────────
        st.markdown(
            "<h3 style='font-size:.95em;font-weight:600;color:#9B9B9B;margin:26px 0 10px;'>"
            "⚙️ Управление профилем</h3>",
            unsafe_allow_html=True,
        )
        with st.expander("🗑️ Удалить профиль «" + pname_c + "»"):
            st.warning("Это действие нельзя отменить. Все данные профиля будут удалены.")
            if st.button("Подтвердить удаление", type="primary",
                         key="confirm_delete_profile"):
                delete_profile(pname_c)
                st.session_state["profile_name"]    = ""
                st.session_state["_profile_loaded"] = ""
                st.session_state["favorites"]       = {}
                st.session_state["ratings"]         = {}
                st.session_state["saved_plans"]     = []
                st.rerun()
