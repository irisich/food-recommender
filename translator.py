# translator.py
import os
import re


def has_cyrillic(text):
    return bool(re.search(r"[а-яА-ЯёЁ]", text or ""))


def fallback_translate_ru_to_en(text):
    """Простой запасной перевод, если GigaChat недоступен."""
    result = text.lower()

    replacements = {
        "быстрый": "quick",
        "быстрая": "quick",
        "легкий": "light",
        "лёгкий": "light",
        "легкая": "light",
        "лёгкая": "light",
        "низкокалорийный": "low calorie",
        "низкокалорийная": "low calorie",
        "высокобелковый": "high protein",
        "высокобелковая": "high protein",
        "белковый": "protein",
        "белковая": "protein",

        "завтрак": "breakfast",
        "перекус": "snack",
        "обед": "lunch",
        "ужин": "dinner",

        "курица": "chicken",
        "рыба": "fish",
        "мясо": "meat",
        "говядина": "beef",
        "свинина": "pork",
        "овощи": "vegetables",
        "салат": "salad",
        "суп": "soup",
        "каша": "porridge",
        "овсянка": "oatmeal",
        "рис": "rice",
        "паста": "pasta",
        "макароны": "pasta",
        "яйца": "eggs",
        "яйцо": "egg",
        "творог": "cottage cheese",
        "сыр": "cheese",
        "молоко": "milk",
        "орехи": "nuts",
        "фрукты": "fruit",

        "без мяса": "without meat",
        "без молока": "without milk",
        "без молочных продуктов": "without dairy products",
        "без глютена": "gluten free",
        "без сахара": "sugar free",
        "без яиц": "without eggs",
        "без орехов": "without nuts",
    }

    # сначала длинные фразы, потом отдельные слова
    for ru in sorted(replacements, key=len, reverse=True):
        result = result.replace(ru, replacements[ru])

    return result


def translate_query_to_english(text):
    """
    Переводит русский пользовательский запрос на английский.
    Если запрос уже на английском — возвращает как есть.
    """
    if not text:
        return text

    if not has_cyrillic(text):
        return text

    key = ""
    try:
        # pyrefly: ignore [missing-import]
        import streamlit as st
        key = st.secrets.get("GIGACHAT_API_KEY", "")
    except Exception:
        pass

    if not key:
        key = os.getenv("GIGACHAT_API_KEY", "")

    if not key:
        return fallback_translate_ru_to_en(text)

    try:
        # pyrefly: ignore [missing-import]
        from gigachat import GigaChat
        # pyrefly: ignore [missing-import]
        from gigachat.models import Chat, Messages, MessagesRole

        client = GigaChat(credentials=key, verify_ssl_certs=False)

        prompt = (
            "Переведи пользовательский запрос для поиска рецептов на английский язык. "
            "Верни только перевод, без пояснений и кавычек. "
            f"Запрос: {text}"
        )

        response = client.chat(
            Chat(
                messages=[Messages(role=MessagesRole.USER, content=prompt)],
                temperature=0.1,
                max_tokens=80,
            )
        )

        translated = response.choices[0].message.content.strip()
        return translated or fallback_translate_ru_to_en(text)

    except Exception:
        return fallback_translate_ru_to_en(text)