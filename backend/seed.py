"""Load axes + onboarding questions (idempotent). Run from backend/: python seed.py"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import insert, select

from app.database import SessionLocal
from app.models.discussion import DiscussionPost
from app.models.question import Question, QuestionAxis, question_axis_link
from app.seed_data.likert_scale_hints import LIKERT_HINTS_BY_ORDER


def apply_likert_labels(db) -> None:
    """Подписи биполярной шкалы по order_index (можно вызывать поверх уже засеянной БД)."""
    specs: dict[int, dict] = {
        1: {
            "text": "Между этими крайностями — где ты? (По центру — нейтрально.)",
            "left": "Свобода выбора",
            "right": "Стабильность и предсказуемость",
            "invert": True,
        },
        2: {
            "text": "Когда видишь потенциальную выгоду, как ты к этому относишься?",
            "left": "Осторожность",
            "right": "Риск ради выгоды",
            "invert": False,
        },
        4: {
            "text": "Как ты относишься к обмену свободы на финансовую стабильность?",
            "left": "Свобода и гибкость",
            "right": "Финансовая стабильность",
            "invert": False,
        },
        5: {
            "text": "План против импровизации — где ты?",
            "left": "Импровизация",
            "right": "План и порядок",
            "invert": False,
        },
        7: {
            "text": "Личное время vs карьера и доход — как сместишь ползунок?",
            "left": "Личное время",
            "right": "Карьера и доход",
            "invert": False,
        },
        9: {
            "text": "От общения с новыми людьми ты…",
            "left": "Уединение",
            "right": "Новые люди",
            "invert": False,
        },
        10: {
            "text": "Насколько тебе важна жёсткая структура дня?",
            "left": "Гибкий день",
            "right": "Чёткая структура",
            "invert": False,
        },
        11: {
            "text": "Менять работу или город ради роста дохода — насколько это про тебя?",
            "left": "Не менять всё из-за денег",
            "right": "Смена ради дохода",
            "invert": False,
        },
    }
    for order, spec in specs.items():
        q = db.scalar(
            select(Question).where(Question.pack == "onboarding", Question.order_index == order)
        )
        if q is None or q.qtype != "likert":
            continue
        if "text" in spec:
            q.text = spec["text"]
        q.likert_left_label = spec["left"]
        q.likert_right_label = spec["right"]
        q.likert_bipolar_invert = spec["invert"]
        hints = LIKERT_HINTS_BY_ORDER.get(order)
        if hints is not None:
            q.likert_hints_json = json.dumps(hints, ensure_ascii=False)
    db.commit()


def seed_discussion_if_empty(db) -> None:
    """Системные посты ленты обсуждений (идемпотентно)."""
    try:
        if db.scalar(select(DiscussionPost.id).limit(1)):
            return
    except Exception:
        return
    now = datetime.now(timezone.utc)
    posts = [
        DiscussionPost(
            author_id=None,
            title="Как вы восстанавливаетесь после перегрузки людьми?",
            body=(
                "Небольшой тред от MatchMe: поделитесь честно — что помогает вернуть ресурс, "
                "если неделя была социально плотной? Без советов «просто отдохни» — конкретика приветствуется."
            ),
            theme_axis_slugs_json=json.dumps(["social", "order_chaos"], ensure_ascii=False),
            is_system=True,
            created_at=now,
        ),
        DiscussionPost(
            author_id=None,
            title="Свобода vs стабильность в 2026",
            body=(
                "Где вы сейчас сместили бы акцент: предсказуемость или гибкость? "
                "Системный пост — обсуждают те, чей профиль близок к «нейтральной зоне» по этой теме."
            ),
            theme_axis_slugs_json=json.dumps(["freedom_stability"], ensure_ascii=False),
            is_system=True,
            created_at=now,
        ),
    ]
    for p in posts:
        db.add(p)
    db.commit()
    print(f"Seeded {len(posts)} system discussion posts.")


def run() -> None:
    db = SessionLocal()
    try:
        if db.scalar(select(Question.id).where(Question.pack == "onboarding").limit(1)):
            print("Onboarding questions already present, skip insert.")
            apply_likert_labels(db)
            print("Likert UI labels updated.")
            seed_discussion_if_empty(db)
            return

        axes_data = [
            ("freedom_stability", "Свобода vs стабильность", "Насколько важна свобода выбора против предсказуемости."),
            ("risk", "Риск", "Отношение к риску и неопределённости."),
            ("money", "Деньги и работа", "Приоритет карьеры, денег, усилий."),
            ("social", "Социальность", "Энергия от людей vs уединение."),
            ("order_chaos", "Порядок vs хаос", "Структура, планы vs импровизация."),
        ]
        slug_to_axis: dict[str, QuestionAxis] = {}
        for slug, name, desc in axes_data:
            ax = QuestionAxis(slug=slug, name=name, description=desc)
            db.add(ax)
            db.flush()
            slug_to_axis[slug] = ax

        items: list[dict] = [
            {
                "order": 1,
                "qtype": "likert",
                "text": "Между этими крайностями — где ты? (По центру — нейтрально, ни то ни другое.)",
                "axes": ["freedom_stability"],
                "likert_left_label": "Свобода выбора",
                "likert_right_label": "Стабильность и предсказуемость",
                "likert_bipolar_invert": True,
            },
            {
                "order": 2,
                "qtype": "likert",
                "text": "Когда видишь потенциальную выгоду, как ты к этому относишься?",
                "axes": ["risk"],
                "likert_left_label": "Осторожность",
                "likert_right_label": "Риск ради выгоды",
                "likert_bipolar_invert": False,
            },
            {
                "order": 3,
                "qtype": "forced_choice",
                "text": "Что ближе?",
                "option_a": "Вечер с незнакомыми людьми",
                "option_b": "Вечер один(а), даже если скучно",
                "axes": ["social"],
            },
            {
                "order": 4,
                "qtype": "likert",
                "text": "Как ты относишься к обмену свободы на финансовую стабильность?",
                "axes": ["money", "freedom_stability"],
                "likert_left_label": "Свобода и гибкость",
                "likert_right_label": "Финансовая стабильность",
                "likert_bipolar_invert": False,
            },
            {
                "order": 5,
                "qtype": "likert",
                "text": "План против импровизации — где ты?",
                "axes": ["order_chaos"],
                "likert_left_label": "Импровизация",
                "likert_right_label": "План и порядок",
                "likert_bipolar_invert": False,
            },
            {
                "order": 6,
                "qtype": "binary",
                "text": "Лучше контролировать ситуацию, чем «плыть по течению»?",
                "option_a": "Контролировать",
                "option_b": "Плыть по течению",
                "axes": ["order_chaos", "risk"],
            },
            {
                "order": 7,
                "qtype": "likert",
                "text": "Личное время vs карьера и доход — как сместишь ползунок?",
                "axes": ["money"],
                "likert_left_label": "Личное время",
                "likert_right_label": "Карьера и доход",
                "likert_bipolar_invert": False,
            },
            {
                "order": 8,
                "qtype": "forced_choice",
                "text": "Что важнее в жизни прямо сейчас?",
                "option_a": "Ощущение безопасности",
                "option_b": "Ощущение свободы",
                "axes": ["freedom_stability", "risk"],
            },
            {
                "order": 9,
                "qtype": "likert",
                "text": "От общения с новыми людьми ты…",
                "axes": ["social"],
                "likert_left_label": "Уединение",
                "likert_right_label": "Новые люди",
                "likert_bipolar_invert": False,
            },
            {
                "order": 10,
                "qtype": "likert",
                "text": "Насколько тебе важна жёсткая структура дня?",
                "axes": ["order_chaos"],
                "likert_left_label": "Гибкий день",
                "likert_right_label": "Чёткая структура",
                "likert_bipolar_invert": False,
            },
            {
                "order": 11,
                "qtype": "likert",
                "text": "Менять работу или город ради роста дохода — насколько это про тебя?",
                "axes": ["money", "risk"],
                "likert_left_label": "Не менять всё из-за денег",
                "likert_right_label": "Смена ради дохода",
                "likert_bipolar_invert": False,
            },
            {
                "order": 12,
                "qtype": "forced_choice",
                "text": "В спорной ситуации ты скорее…",
                "option_a": "Отстаиваешь позицию до конца",
                "option_b": "Ищешь компромисс ради мира",
                "axes": ["order_chaos", "social"],
            },
        ]

        for it in items:
            hints_list = LIKERT_HINTS_BY_ORDER.get(it["order"])
            likert_hints_json = (
                json.dumps(hints_list, ensure_ascii=False) if hints_list is not None else None
            )
            q = Question(
                pack="onboarding",
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
        print(f"Seeded {len(items)} onboarding questions.")
        apply_likert_labels(db)
        print("Likert UI labels synced.")
        seed_discussion_if_empty(db)
    finally:
        db.close()


if __name__ == "__main__":
    run()
