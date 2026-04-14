"""Парсинг и нормализация JSON-настроек ленты (веса осей, мягкие приоритеты, dealbreaker-оси)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.question import QuestionAxis


def default_feed_prefs() -> tuple[dict[str, float], list[str], list[str]]:
    return {}, [], []


def parse_feed_preferences_json(raw: str | None) -> tuple[dict[str, float], list[str], list[str]]:
    if not raw or not raw.strip():
        return default_feed_prefs()
    try:
        data: Any = json.loads(raw)
    except json.JSONDecodeError:
        return default_feed_prefs()
    if not isinstance(data, dict):
        return default_feed_prefs()
    weights_in = data.get("axis_weights") or data.get("weights") or {}
    soft = data.get("soft_priority_slugs") or data.get("soft_priority") or []
    deal_in = data.get("dealbreaker_slugs") or []
    if not isinstance(weights_in, dict):
        weights_in = {}
    if not isinstance(soft, list):
        soft = []
    if not isinstance(deal_in, list):
        deal_in = []
    weights: dict[str, float] = {}
    for k, v in weights_in.items():
        if not isinstance(k, str):
            continue
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        fv = max(0.0, min(3.0, fv))
        weights[k.strip()] = fv
    soft_slugs = [str(x).strip() for x in soft if isinstance(x, str) and str(x).strip()][:8]
    deal_slugs = [str(x).strip() for x in deal_in if isinstance(x, str) and str(x).strip()][:5]
    return weights, soft_slugs, deal_slugs


def validate_prefs_against_db(
    db: Session,
    weights: dict[str, float],
    soft: list[str],
    dealbreakers: list[str],
) -> tuple[dict[str, float], list[str], list[str]]:
    """Оставляем только slug, существующие в БД."""
    axes = db.query(QuestionAxis).all()
    slugs = {a.slug for a in axes}
    w = {k: v for k, v in weights.items() if k in slugs}
    s = [x for x in soft if x in slugs]
    d = [x for x in dealbreakers if x in slugs][:5]
    return w, s, d


def serialize_feed_preferences(
    weights: dict[str, float], soft: list[str], dealbreakers: list[str]
) -> str:
    return json.dumps(
        {
            "axis_weights": weights,
            "soft_priority_slugs": soft,
            "dealbreaker_slugs": dealbreakers,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
