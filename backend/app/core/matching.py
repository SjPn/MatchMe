"""v0 matching: axis scores from answers + rule-based insight strings."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.answer import Answer
from app.models.question import Question, question_axis_link
from app.models.question import QuestionAxis


def _normalize_likert(value: float, q: Question) -> float:
    lo, hi = float(q.likert_min), float(q.likert_max)
    if hi <= lo:
        return 0.5
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


def _answer_scalar(answer: Answer, q: Question) -> float | None:
    if q.qtype == "likert" and answer.value_numeric is not None:
        return _normalize_likert(float(answer.value_numeric), q)
    if q.qtype == "binary":
        inv = bool(getattr(q, "choice_score_invert", False))
        if answer.value_choice == "a":
            return 1.0 if inv else 0.0
        if answer.value_choice == "b":
            return 0.0 if inv else 1.0
    if q.qtype == "forced_choice":
        inv = bool(getattr(q, "choice_score_invert", False))
        if answer.value_choice == "a":
            return 1.0 if inv else 0.0
        if answer.value_choice == "b":
            return 0.0 if inv else 1.0
    return None


def compute_user_axis_scores(db: Session, user_id: int) -> dict[int, float]:
    """Returns axis_id -> score in [0, 1]."""
    answers = (
        db.query(Answer)
        .options(selectinload(Answer.question))
        .filter(Answer.user_id == user_id)
        .all()
    )

    axis_num: dict[int, float] = {}
    axis_den: dict[int, float] = {}

    for ans in answers:
        q = ans.question
        val = _answer_scalar(ans, q)
        if val is None:
            continue
        rows = db.execute(
            select(question_axis_link.c.axis_id, question_axis_link.c.weight).where(
                question_axis_link.c.question_id == q.id
            )
        ).all()
        for axis_id, w in rows:
            wf = float(w)
            aid = int(axis_id)
            axis_num[aid] = axis_num.get(aid, 0.0) + val * wf
            axis_den[aid] = axis_den.get(aid, 0.0) + wf

    out: dict[int, float] = {}
    for ax_id, num in axis_num.items():
        den = axis_den.get(ax_id, 0.0)
        out[ax_id] = num / den if den > 0 else 0.5
    return out


def _axis_scores_from_answers_and_links(
    answers: list[Answer],
    links_by_question: dict[int, list[tuple[int, float]]],
) -> dict[int, float]:
    """Те же правила, что в compute_user_axis_scores, но связи вопрос→ось уже загружены."""
    axis_num: dict[int, float] = {}
    axis_den: dict[int, float] = {}
    for ans in answers:
        q = ans.question
        val = _answer_scalar(ans, q)
        if val is None:
            continue
        for axis_id, w in links_by_question.get(q.id, []):
            wf = float(w)
            aid = int(axis_id)
            axis_num[aid] = axis_num.get(aid, 0.0) + val * wf
            axis_den[aid] = axis_den.get(aid, 0.0) + wf
    out: dict[int, float] = {}
    for ax_id, num in axis_num.items():
        den = axis_den.get(ax_id, 0.0)
        out[ax_id] = num / den if den > 0 else 0.5
    return out


def compute_user_axis_scores_batch(db: Session, user_ids: list[int]) -> dict[int, dict[int, float]]:
    """
    Один проход по ответам для многих пользователей (для ленты вместо N×2 отдельных запросов).
    """
    if not user_ids:
        return {}
    uid_set = list(dict.fromkeys(user_ids))  # порядок + уникальные id
    answers = (
        db.query(Answer)
        .options(selectinload(Answer.question))
        .filter(Answer.user_id.in_(uid_set))
        .all()
    )
    by_uid: dict[int, list[Answer]] = defaultdict(list)
    for a in answers:
        by_uid[a.user_id].append(a)

    qids = {a.question_id for a in answers}
    links_by_question: dict[int, list[tuple[int, float]]] = defaultdict(list)
    if qids:
        link_rows = db.execute(
            select(
                question_axis_link.c.question_id,
                question_axis_link.c.axis_id,
                question_axis_link.c.weight,
            ).where(question_axis_link.c.question_id.in_(qids))
        ).all()
        for qid, axis_id, w in link_rows:
            links_by_question[int(qid)].append((int(axis_id), float(w)))

    return {uid: _axis_scores_from_answers_and_links(by_uid.get(uid, []), links_by_question) for uid in uid_set}


@dataclass
class AxisPairRow:
    axis_id: int
    slug: str
    name: str
    similarity: float
    distance: float


def axis_pair_rows_from_scores(
    scores_a: dict[int, float],
    scores_b: dict[int, float],
    axes: list[QuestionAxis],
) -> list[AxisPairRow]:
    """Построить строки сравнения по осям без запросов к БД (для ленты с батч-скорами)."""
    rows: list[AxisPairRow] = []
    for ax in axes:
        if ax.id not in scores_a or ax.id not in scores_b:
            continue
        sa, sb = scores_a[ax.id], scores_b[ax.id]
        dist = abs(sa - sb)
        sim = 1.0 - dist
        rows.append(AxisPairRow(axis_id=ax.id, slug=ax.slug, name=ax.name, similarity=sim, distance=dist))
    return rows


def _gather_axis_rows(
    db: Session,
    user_a_id: int,
    user_b_id: int,
    *,
    scores_a: dict[int, float] | None = None,
    axes: list[QuestionAxis] | None = None,
) -> list[AxisPairRow]:
    sa = scores_a if scores_a is not None else compute_user_axis_scores(db, user_a_id)
    sb = compute_user_axis_scores(db, user_b_id)
    axis_list = axes if axes is not None else db.query(QuestionAxis).all()
    return axis_pair_rows_from_scores(sa, sb, axis_list)


def _base_percent_from_rows(rows: list[AxisPairRow]) -> float:
    if not rows:
        return 50.0
    return round(100.0 * (sum(r.similarity for r in rows) / len(rows)), 1)


def weighted_match_percent(
    rows: list[AxisPairRow],
    weights_by_slug: dict[str, float],
    soft_priority_slugs: list[str],
    dealbreaker_slugs: list[str] | None = None,
    *,
    soft_dist_threshold: float = 0.28,
    max_penalty_per_axis: float = 14.0,
    dealbreaker_distance: float = 0.34,
    dealbreaker_cap: float = 26.0,
) -> tuple[float, list[str], bool]:
    """
    Взвешенная близость по осям + мягкий штраф + жёсткий dealbreaker (OkCupid-style).
    Возвращает (процент 0–100, пояснения, сработал ли dealbreaker).
    """
    penalty_notes: list[str] = []
    dealbreaker_hit = False
    if not rows:
        return 50.0, penalty_notes, dealbreaker_hit

    wsum = 0.0
    acc = 0.0
    for r in rows:
        w = weights_by_slug.get(r.slug)
        if w is None:
            w = 1.0
        if w <= 0:
            continue
        acc += w * r.similarity
        wsum += w

    if wsum <= 0:
        base_w = 100.0 * (sum(r.similarity for r in rows) / len(rows))
    else:
        base_w = 100.0 * (acc / wsum)

    penalty_total = 0.0
    by_slug = {r.slug: r for r in rows}
    for slug in soft_priority_slugs:
        r = by_slug.get(slug)
        if r is None:
            continue
        if r.distance > soft_dist_threshold:
            excess = r.distance - soft_dist_threshold
            p = min(max_penalty_per_axis, 100.0 * excess * 0.85)
            penalty_total += p
            penalty_notes.append(
                f"по «{r.name}» заметное расхождение (важная для вас ось) — штраф к скору"
            )

    final = max(0.0, min(100.0, base_w - penalty_total))

    for slug in dealbreaker_slugs or []:
        r = by_slug.get(slug)
        if r is None:
            continue
        if r.distance > dealbreaker_distance:
            dealbreaker_hit = True
            final = min(final, dealbreaker_cap)
            penalty_notes.append(
                f"«{r.name}» отмечена как dealbreaker: при сильном расхождении совместимость сильно ограничена."
            )

    return round(final, 1), penalty_notes, dealbreaker_hit


def _comparison_extras(rows: list[AxisPairRow]) -> tuple[str, list[dict], list[dict]]:
    """Заголовок «почему совпали», структурированные общие черты, промпты для разговора по различиям."""
    if not rows:
        return "Пока недостаточно общих осей для развёрнутого сравнения.", [], []

    strong = sorted([r for r in rows if r.distance < 0.18], key=lambda r: -r.similarity)[:8]
    headline_parts = [r.name for r in strong[:3]]
    if headline_parts:
        headline = "Вы близки по темам: " + ", ".join(headline_parts)
        if len(strong) > 3:
            headline += " — и ещё по нескольким осям."
        else:
            headline += "."
    else:
        headline = "Есть и близкие, и отличающиеся темы — смотрите блоки ниже."

    shared_traits: list[dict] = [
        {
            "axis": r.name,
            "slug": r.slug,
            "summary": f"Схожий «склад» по «{r.name}» (близость ~{int(round(r.similarity * 100))}%).",
            "strength": "high" if r.similarity >= 0.86 else "medium",
            "detail": f"близкие позиции по «{r.name}»",
        }
        for r in strong
    ]

    mid = [r for r in rows if 0.20 <= r.distance <= 0.55]
    mid.sort(key=lambda r: -r.distance)
    conversation_prompts: list[dict] = []
    for r in mid[:2]:
        conversation_prompts.append(
            {
                "axis": r.name,
                "slug": r.slug,
                "prompt": (
                    f"Что для вас важнее в теме «{r.name}»? Расскажите по очереди — у вас разный акцент, "
                    f"это нормальный повод для разговора."
                ),
                "note": "Умеренное расхождение — удобный лёдокол.",
                "detail": f"разные акценты по «{r.name}»",
            }
        )

    return headline, shared_traits, conversation_prompts


def _insights_from_axis_rows(rows: list[AxisPairRow]) -> tuple[list[dict], list[dict]]:
    agreements: list[dict] = []
    differences: list[dict] = []
    for r in rows:
        if r.distance < 0.15:
            agreements.append(
                {
                    "axis": r.name,
                    "slug": r.slug,
                    "detail": f"близкие позиции по «{r.name}»",
                }
            )
        elif r.distance > 0.45:
            differences.append(
                {
                    "axis": r.name,
                    "slug": r.slug,
                    "detail": f"разные взгляды на «{r.name}»",
                }
            )
    return agreements[:5], differences[:5]


def compare_users(
    db: Session,
    user_a_id: int,
    user_b_id: int,
    *,
    scores_a: dict[int, float] | None = None,
    axes: list[QuestionAxis] | None = None,
) -> tuple[float, list[dict], list[dict], str, list[dict], list[dict]]:
    """
    Returns (match_percent_0_100, agreements[], differences[], headline, shared_traits, conversation_prompts).
    """
    rows = _gather_axis_rows(db, user_a_id, user_b_id, scores_a=scores_a, axes=axes)
    pct = _base_percent_from_rows(rows)
    agreements, differences = _insights_from_axis_rows(rows)
    headline, traits, prompts = _comparison_extras(rows)
    return pct, agreements, differences, headline, traits, prompts


def compare_users_weighted(
    db: Session,
    viewer_id: int,
    other_id: int,
    weights_by_slug: dict[str, float],
    soft_priority_slugs: list[str],
    dealbreaker_slugs: list[str] | None = None,
    *,
    scores_a: dict[int, float] | None = None,
    axes: list[QuestionAxis] | None = None,
) -> tuple[float, float, list[dict], list[dict], list[str], str, list[dict], list[dict], bool]:
    """
    (weighted_pct, base_pct, agreements, differences, penalty_notes, headline, shared_traits, conversation_prompts, dealbreaker_hit)
    """
    rows = _gather_axis_rows(db, viewer_id, other_id, scores_a=scores_a, axes=axes)
    base_pct = _base_percent_from_rows(rows)
    w_pct, notes, db_hit = weighted_match_percent(
        rows, weights_by_slug, soft_priority_slugs, dealbreaker_slugs
    )
    agree, diff = _insights_from_axis_rows(rows)
    headline, traits, prompts = _comparison_extras(rows)
    return w_pct, base_pct, agree, diff, notes, headline, traits, prompts, db_hit


def compare_users_from_axis_rows(rows: list[AxisPairRow]) -> tuple[float, list[dict], list[dict], str, list[dict], list[dict]]:
    """Сравнение по уже посчитанным осям (лента с батч-скорами)."""
    pct = _base_percent_from_rows(rows)
    agreements, differences = _insights_from_axis_rows(rows)
    headline, traits, prompts = _comparison_extras(rows)
    return pct, agreements, differences, headline, traits, prompts


def compare_users_weighted_from_axis_rows(
    rows: list[AxisPairRow],
    weights_by_slug: dict[str, float],
    soft_priority_slugs: list[str],
    dealbreaker_slugs: list[str] | None = None,
) -> tuple[float, float, list[dict], list[dict], list[str], str, list[dict], list[dict], bool]:
    base_pct = _base_percent_from_rows(rows)
    w_pct, notes, db_hit = weighted_match_percent(
        rows, weights_by_slug, soft_priority_slugs, dealbreaker_slugs
    )
    agree, diff = _insights_from_axis_rows(rows)
    headline, traits, prompts = _comparison_extras(rows)
    return w_pct, base_pct, agree, diff, notes, headline, traits, prompts, db_hit
