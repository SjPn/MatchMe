"""Load axes + onboarding questions (idempotent). Run from backend/: python seed.py"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import delete, func, insert, select, update

from app.database import SessionLocal
from app.models.answer import Answer
from app.models.discussion import DiscussionPost
from app.models.question import Question, QuestionAxis, question_axis_link
from app.models.user import User
from app.seed_data.likert_scale_hints import LIKERT_HINTS_BY_ORDER
from app.seed_data.onboarding_plus import seed_onboarding_plus_pack


def apply_likert_labels(db) -> None:
    """Подписи биполярной шкалы по order_index (можно вызывать поверх уже засеянной БД)."""
    specs: dict[int, dict] = {
        2: {
            "text": "План против импровизации — где ты?",
            "left": "Импровизация",
            "right": "План и порядок",
            "invert": False,
        },
        4: {
            "text": "Личное время vs карьера и доход — как совместишь ползунок?",
            "left": "Личное время",
            "right": "Карьера и доход",
            "invert": False,
        },
        6: {
            "text": "Менять работу или город ради роста дохода — насколько это про тебя?",
            "left": "Не менять всё из-за денег",
            "right": "Смена ради дохода",
            "invert": False,
        },
        7: {
            "text": "Если друг поступает плохо, но не просит совета — ты…",
            "left": "Промолчу, это его выбор",
            "right": "Скажу прямо, что думаю",
            "invert": False,
        },
        8: {
            "text": "Жизнь резко меняется — новая работа, переезд, конец отношений. Ты скорее…",
            "left": "Теряюсь, нужно время",
            "right": "Быстро нахожу новую точку опоры",
            "invert": False,
        },
        10: {
            "text": "Тебе говорят: «Попробуй сделать это иначе, чем привык». Твоя первая реакция?",
            "left": "Сопротивление",
            "right": "Любопытство",
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


def _onboarding_needs_refresh(db) -> bool:
    n = db.scalar(select(func.count()).select_from(Question).where(Question.pack == "onboarding")) or 0
    if n != 10:
        return True
    t = db.scalar(
        select(Question.text).where(Question.pack == "onboarding", Question.order_index == 1).limit(1)
    )
    return not (t and "мечты" in t)


def _clear_onboarding_questions(db) -> None:
    ids = list(db.scalars(select(Question.id).where(Question.pack == "onboarding")).all())
    if not ids:
        return
    user_ids = list(db.scalars(select(Answer.user_id).where(Answer.question_id.in_(ids)).distinct()).all())
    db.execute(delete(Answer).where(Answer.question_id.in_(ids)))
    db.execute(delete(question_axis_link).where(question_axis_link.c.question_id.in_(ids)))
    db.query(Question).filter(Question.pack == "onboarding").delete(synchronize_session=False)
    if user_ids:
        db.execute(update(User).where(User.id.in_(user_ids)).values(onboarding_step="registered"))
    db.commit()


def _ensure_axes(db, axes_data: list[tuple[str, str, str]]) -> None:
    for slug, name, desc in axes_data:
        if db.scalar(select(QuestionAxis.id).where(QuestionAxis.slug == slug)) is None:
            db.add(QuestionAxis(slug=slug, name=name, description=desc))
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
        axes_data = [
            ("freedom_stability", "Свобода vs стабильность", "Насколько важна свобода выбора против предсказуемости."),
            ("risk", "Риск", "Отношение к риску и неопределённости."),
            ("money", "Деньги и работа", "Приоритет карьеры, денег, усилий."),
            ("social", "Социальность", "Энергия от людей vs уединение."),
            ("order_chaos", "Порядок vs хаос", "Структура, планы vs импровизация."),
            (
                "honesty_directness",
                "Честность vs дипломатия",
                "Прямота и открытость vs сглаживание и такт.",
            ),
            ("adaptability", "Адаптивность к переменам", "Как быстро находишь опору после резких изменений."),
        ]
        _ensure_axes(db, axes_data)

        if not _onboarding_needs_refresh(db):
            print("Onboarding pack v2 already present, skip insert.")
            apply_likert_labels(db)
            print("Likert UI labels updated.")
            seed_discussion_if_empty(db)
        else:
            _clear_onboarding_questions(db)
            slug_to_axis: dict[str, QuestionAxis] = {a.slug: a for a in db.query(QuestionAxis).all()}

            items: list[dict] = [
            {
                "order": 1,
                "qtype": "forced_choice",
                "text": "Тебе предложили работу мечты — но она в другом городе и без гарантий. Ты…",
                "option_a": "Соглашусь, несмотря на неопределённость",
                "option_b": "Подожду чего-то более предсказуемого",
                "axes": ["freedom_stability", "risk"],
                "choice_score_invert": True,
            },
            {
                "order": 2,
                "qtype": "likert",
                "text": "План против импровизации — где ты?",
                "axes": ["order_chaos"],
                "likert_left_label": "Импровизация",
                "likert_right_label": "План и порядок",
                "likert_bipolar_invert": False,
            },
            {
                "order": 3,
                "qtype": "forced_choice",
                "text": "Что ближе?",
                "option_a": "Вечер с незнакомыми людьми",
                "option_b": "Вечер один (а), даже если скучно",
                "axes": ["social"],
                "choice_score_invert": True,
            },
            {
                "order": 4,
                "qtype": "likert",
                "text": "Личное время vs карьера и доход — как совместишь ползунок?",
                "axes": ["money"],
                "likert_left_label": "Личное время",
                "likert_right_label": "Карьера и доход",
                "likert_bipolar_invert": False,
            },
            {
                "order": 5,
                "qtype": "forced_choice",
                "text": "Отстаиваешь позицию до конца",
                "option_a": "Отстаиваешь позицию до конца",
                "option_b": "Ищешь компромисс ради мира",
                "axes": ["order_chaos", "social"],
                "choice_score_invert": True,
            },
            {
                "order": 6,
                "qtype": "likert",
                "text": "Менять работу или город ради роста дохода — насколько это про тебя?",
                "axes": ["money", "risk"],
                "likert_left_label": "Не менять всё из-за денег",
                "likert_right_label": "Смена ради дохода",
                "likert_bipolar_invert": False,
            },
            {
                "order": 7,
                "qtype": "likert",
                "text": "Если друг поступает плохо, но не просит совета — ты…",
                "axes": ["honesty_directness", "social"],
                "likert_left_label": "Промолчу, это его выбор",
                "likert_right_label": "Скажу прямо, что думаю",
                "likert_bipolar_invert": False,
            },
            {
                "order": 8,
                "qtype": "likert",
                "text": "Жизнь резко меняется — новая работа, переезд, конец отношений. Ты скорее…",
                "axes": ["adaptability", "risk"],
                "likert_left_label": "Теряюсь, нужно время",
                "likert_right_label": "Быстро нахожу новую точку опоры",
                "likert_bipolar_invert": False,
            },
            {
                "order": 9,
                "qtype": "forced_choice",
                "text": "После насыщенного разговора с новым человеком ты…",
                "option_a": "Ещё долго думаю о нём, анализирую сказанное",
                "option_b": "Отпускаю быстро — было приятно, и хватит",
                "axes": ["social", "honesty_directness"],
                "choice_score_invert": False,
            },
            {
                "order": 10,
                "qtype": "likert",
                "text": "Тебе говорят: «Попробуй сделать это иначе, чем привык». Твоя первая реакция?",
                "axes": ["order_chaos", "adaptability"],
                "likert_left_label": "Сопротивление",
                "likert_right_label": "Любопытство",
                "likert_bipolar_invert": False,
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
            print(f"Seeded {len(items)} onboarding questions (v2).")
            apply_likert_labels(db)
            print("Likert UI labels synced.")
            seed_discussion_if_empty(db)

        seed_onboarding_plus_pack(db)
        print("Onboarding plus pack (10 questions) synced.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
