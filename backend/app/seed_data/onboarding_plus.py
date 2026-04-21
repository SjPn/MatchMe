"""Второй блок из 10 вопросов (pack=onboarding_plus), оси justice, autonomy, …"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import delete, func, insert, select

from app.models.answer import Answer
from app.models.question import Question, QuestionAxis, question_axis_link

PACK = "onboarding_plus"

PLUS_AXES: list[tuple[str, str, str]] = [
    ("justice", "Справедливость / правила", "Правила vs результат, ответственность за нормы."),
    ("autonomy", "Автономия решений", "Самостоятельность vs опора на группу и консенсус."),
    ("emotion_logic", "Чувство и логика", "Интуиция и ощущения vs наблюдения и факты."),
    ("depth_breadth", "Глубина vs ширина", "Одна тема глубоко vs много направлений понемногу."),
    ("future_past", "Прошлое и настоящее vs будущее", "Опора на проверенное vs эксперименты и горизонт."),
]

# Подсказки Likert: ключ = order_index внутри onboarding_plus
LIKERT_HINTS_PLUS: dict[int, list[str]] = {
    2: [
        "Всегда советуюсь; решение в одиночку ощущается как ошибка.",
        "Сильно нужна опора на близких или команду.",
        "Скорее обсуждаю; одиночные решения — редкость.",
        "Чуть ближе к «спросить», чем к «решить самому».",
        "Нейтрально: зависит от масштаба решения.",
        "Нейтрально: иногда советуюсь, иногда нет — по ситуации.",
        "Чуть чаще разбираюсь сам; чужое мнение — дополнение, не опора.",
        "Скорее самостоятельно; советы слушаю, но не жду их.",
        "Почти всегда сам; лишние мнения путают.",
        "Полностью самостоятельно; обсуждение решений — не моё.",
    ],
    4: [
        "Постоянно новое; глубина в одной теме быстро наскучивает.",
        "Широко и разнообразно; узкая специализация кажется скучной.",
        "Скорее много направлений, чем одно глубокое.",
        "Чуть ближе к широте, хотя иногда задерживаюсь подольше.",
        "Нейтрально: и глубина, и разброс.",
        "Нейтрально: зависит от темы.",
        "Чуть ближе к глубине; интересное затягивает надолго.",
        "Скорее глубоко; поверхностный интерес быстро раздражает.",
        "Погружаюсь глубоко в немногое; широта кажется суетой.",
        "Одна тема — до самого дна; широта без глубины не интересна.",
    ],
    6: [
        "Спокойно слушаю; у каждого своя правда, и это нормально.",
        "Сдерживаюсь; возражаю только если прямо спрашивают.",
        "Скорее промолчу; конфликт ради принципа — лишнее.",
        "Чуть ближе к молчанию, но иногда не удерживаюсь.",
        "Нейтрально: зависит от темы и отношений с человеком.",
        "Нейтрально: могу и промолчать, и мягко возразить.",
        "Чуть чаще возражаю; молчание ощущается как соучастие.",
        "Скорее скажу; несогласие сложно держать в себе.",
        "Почти всегда возражаю; молчание = согласие для меня неприемлемо.",
        "Всегда реагирую; не высказаться — значит солгать.",
    ],
    8: [
        "Почти всегда интуиция; «что-то не то» — достаточный аргумент.",
        "Сильно опираюсь на ощущения; анализ — вторичен.",
        "Скорее чувства; логика подключается постфактум.",
        "Чуть ближе к интуиции, хотя факты тоже учитываю.",
        "Нейтрально: и ощущения, и наблюдения одинаково важны.",
        "Нейтрально: смотрю на поведение, но и интуиция в игре.",
        "Чуть чаще ориентируюсь на конкретные факты поведения.",
        "Скорее анализирую: что делает, как говорит, что обещает.",
        "Почти всегда факты; интуиции не доверяю без подтверждения.",
        "Только наблюдения и анализ; «ощущение» — не аргумент.",
    ],
    10: [
        "Живу тем, что есть; строить воздушные замки — не моё.",
        "Ценю настоящее и опыт прошлого; будущее — туманно.",
        "Скорее настоящее; планировать далеко кажется наивным.",
        "Чуть ближе к «здесь и сейчас», чем к горизонту.",
        "Нейтрально: и настоящее важно, и будущее интересует.",
        "Нейтрально: смотрю в обе стороны примерно поровну.",
        "Чуть чаще думаю о том, что будет, чем о том, что есть.",
        "Будущее тянет сильнее; настоящее — точка отсчёта, не финал.",
        "Живу в основном горизонтом; «что будет» важнее «что есть».",
        "Почти всегда в будущем; настоящее — только трамплин.",
    ],
}

PLUS_ITEMS: list[dict[str, Any]] = [
    {
        "order": 1,
        "qtype": "forced_choice",
        "text": "Твой коллега нарушил правило, но итог оказался отличным. Как ты к этому?",
        "option_a": "Результат оправдывает отступление от правил",
        "option_b": "Правило нарушено — это проблема, даже если всё вышло хорошо",
        "axes": ["justice"],
        "choice_score_invert": False,
    },
    {
        "order": 2,
        "qtype": "likert",
        "text": "Важное решение — ты скорее…",
        "axes": ["autonomy", "social"],
        "likert_left_label": "Советуюсь, нужна поддержка «своих»",
        "likert_right_label": "Разбираюсь сам, чужое мнение мешает",
        "likert_bipolar_invert": False,
    },
    {
        "order": 3,
        "qtype": "forced_choice",
        "text": "Ты принял (а) важное решение. Через неделю оказалось, что логически оно было неверным, но внутри всё равно ощущается правильным. Ты…",
        "option_a": "Доверяю ощущению — значит, так и надо",
        "option_b": "Признаю ошибку — ощущения не аргумент",
        "axes": ["emotion_logic"],
        "choice_score_invert": False,
    },
    {
        "order": 4,
        "qtype": "likert",
        "text": "Когда тебя что-то цепляет — ты скорее…",
        "axes": ["depth_breadth"],
        "likert_left_label": "Пробую много всего понемногу",
        "likert_right_label": "Ухожу в одну очень глубоко",
        "likert_bipolar_invert": False,
    },
    {
        "order": 5,
        "qtype": "forced_choice",
        "text": "Что тебя больше вдохновляет?",
        "option_a": "То, что уже проверено временем — традиции, классика, опыт",
        "option_b": "Того ещё не было — эксперименты, новые идеи, будущее",
        "axes": ["future_past"],
        "choice_score_invert": False,
    },
    {
        "order": 6,
        "qtype": "likert",
        "text": "Человек рядом говорит то, с чем ты категорически не согласен. Ты…",
        "axes": ["honesty_directness", "justice"],
        "likert_left_label": "Слушаю, не реагирую — его право",
        "likert_right_label": "Не могу не возразить, молчание = согласие",
        "likert_bipolar_invert": False,
    },
    {
        "order": 7,
        "qtype": "forced_choice",
        "text": "Ты скорее…",
        "option_a": "Человек одного круга — глубоко, долго, с теми же людьми",
        "option_b": "Человек многих кругов — разные компании, контексты, роли",
        "axes": ["autonomy", "depth_breadth"],
        "choice_score_invert": True,
    },
    {
        "order": 8,
        "qtype": "likert",
        "text": "Когда нужно понять нового человека — ты опираешься на…",
        "axes": ["emotion_logic", "social"],
        "likert_left_label": "Интуицию и ощущения",
        "likert_right_label": "Наблюдения и факты",
        "likert_bipolar_invert": False,
    },
    {
        "order": 9,
        "qtype": "forced_choice",
        "text": "В группе принято решение, с которым ты не согласен. Ты…",
        "option_a": "Подчиняюсь — группа решила, значит так и будет",
        "option_b": "Остаюсь при своём мнении, даже действую врозь со всеми",
        "axes": ["justice", "autonomy"],
        "choice_score_invert": False,
    },
    {
        "order": 10,
        "qtype": "likert",
        "text": "Когда ты думаешь о своей жизни — куда смотришь чаще?",
        "axes": ["future_past", "adaptability"],
        "likert_left_label": "На то, что есть и было",
        "likert_right_label": "На то, что будет и может быть",
        "likert_bipolar_invert": False,
    },
]


def _plus_needs_refresh(db) -> bool:
    n = db.scalar(select(func.count()).select_from(Question).where(Question.pack == PACK)) or 0
    if n != 10:
        return True
    t = db.scalar(select(Question.text).where(Question.pack == PACK, Question.order_index == 1).limit(1))
    return not (t and "коллега" in t)


def _clear_pack_questions(db, pack: str) -> None:
    ids = list(db.scalars(select(Question.id).where(Question.pack == pack)).all())
    if not ids:
        return
    db.execute(delete(Answer).where(Answer.question_id.in_(ids)))
    db.execute(delete(question_axis_link).where(question_axis_link.c.question_id.in_(ids)))
    db.query(Question).filter(Question.pack == pack).delete(synchronize_session=False)
    db.commit()


def _ensure_plus_axes(db) -> dict[str, QuestionAxis]:
    for slug, name, desc in PLUS_AXES:
        if db.scalar(select(QuestionAxis.id).where(QuestionAxis.slug == slug)) is None:
            db.add(QuestionAxis(slug=slug, name=name, description=desc))
    db.commit()
    return {a.slug: a for a in db.query(QuestionAxis).all()}


def apply_onboarding_plus_labels(db) -> None:
    specs: dict[int, dict[str, Any]] = {
        2: {
            "text": "Важное решение — ты скорее…",
            "left": "Советуюсь, нужна поддержка «своих»",
            "right": "Разбираюсь сам, чужое мнение мешает",
            "invert": False,
        },
        4: {
            "text": "Когда тебя что-то цепляет — ты скорее…",
            "left": "Пробую много всего понемногу",
            "right": "Ухожу в одну очень глубоко",
            "invert": False,
        },
        6: {
            "text": "Человек рядом говорит то, с чем ты категорически не согласен. Ты…",
            "left": "Слушаю, не реагирую — его право",
            "right": "Не могу не возразить, молчание = согласие",
            "invert": False,
        },
        8: {
            "text": "Когда нужно понять нового человека — ты опираешься на…",
            "left": "Интуицию и ощущения",
            "right": "Наблюдения и факты",
            "invert": False,
        },
        10: {
            "text": "Когда ты думаешь о своей жизни — куда смотришь чаще?",
            "left": "На то, что есть и было",
            "right": "На то, что будет и может быть",
            "invert": False,
        },
    }
    for order, spec in specs.items():
        q = db.scalar(select(Question).where(Question.pack == PACK, Question.order_index == order))
        if q is None or q.qtype != "likert":
            continue
        q.text = spec["text"]
        q.likert_left_label = spec["left"]
        q.likert_right_label = spec["right"]
        q.likert_bipolar_invert = spec["invert"]
        hints = LIKERT_HINTS_PLUS.get(order)
        if hints:
            q.likert_hints_json = json.dumps(hints, ensure_ascii=False)
    db.commit()


def seed_onboarding_plus_pack(db) -> None:
    """Идемпотентно: оси + 10 вопросов pack=onboarding_plus."""
    if not _plus_needs_refresh(db):
        apply_onboarding_plus_labels(db)
        return
    _clear_pack_questions(db, PACK)
    slug_to_axis = _ensure_plus_axes(db)
    for it in PLUS_ITEMS:
        hints_list = LIKERT_HINTS_PLUS.get(it["order"])
        likert_hints_json = json.dumps(hints_list, ensure_ascii=False) if hints_list else None
        q = Question(
            pack=PACK,
            qtype=it["qtype"],
            text=it["text"],
            order_index=it["order"],
            option_a=it.get("option_a"),
            option_b=it.get("option_b"),
            likert_min=1,
            likert_max=10,
            likert_left_label=it.get("likert_left_label"),
            likert_right_label=it.get("likert_right_label"),
            likert_bipolar_invert=bool(it.get("likert_bipolar_invert", False)),
            likert_hints_json=likert_hints_json,
            choice_score_invert=bool(it.get("choice_score_invert", False)),
        )
        db.add(q)
        db.flush()
        for slug in it["axes"]:
            ax = slug_to_axis[slug]
            db.execute(
                insert(question_axis_link).values(
                    question_id=q.id,
                    axis_id=ax.id,
                    weight=1.0,
                )
            )
    db.commit()
    apply_onboarding_plus_labels(db)
