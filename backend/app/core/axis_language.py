"""Общие подписи полюсов и короткие фразы «как я думаю» для карточек профиля."""

from __future__ import annotations

from typing import Any


AXIS_POLES: dict[str, tuple[str, str]] = {
    "freedom_stability": ("Свобода выбора", "Стабильность и предсказуемость"),
    "risk": ("Осторожность", "Риск ради выгоды"),
    "money": ("Личное время", "Карьера и доход"),
    "social": ("Уединение", "Новые люди"),
    "order_chaos": ("Импровизация", "План и порядок"),
    "honesty_directness": ("Сглаживать и молчать", "Говорить прямо"),
    "adaptability": ("Теряюсь при переменах", "Быстро адаптируюсь"),
    "justice": ("Итог важнее формальных правил", "Нарушение правил — проблема"),
    "autonomy": ("Опора на «своих» и совет", "Решаю самостоятельно"),
    "emotion_logic": ("Интуиция и ощущения", "Логика и факты"),
    "depth_breadth": ("Много тем понемногу", "Одна тема глубоко"),
    "future_past": ("Проверенное и настоящее", "Новое и будущее"),
}


def lean_label(score_0_1: float, left: str, right: str) -> str:
    if score_0_1 <= 0.40:
        return f"скорее {left.lower()}"
    if score_0_1 >= 0.60:
        return f"скорее {right.lower()}"
    return "скорее нейтрально"


def mind_profile_lines(
    scores: dict[int, float],
    axes_by_id: dict[int, Any],
    *,
    limit: int = 4,
) -> list[str]:
    """2–4 короткие фразы по осям для карточки «склад ума»."""
    lines: list[str] = []
    for ax_id in sorted(scores.keys()):
        if len(lines) >= limit:
            break
        ax = axes_by_id.get(ax_id)
        if ax is None:
            continue
        s = float(scores[ax_id])
        left, right = AXIS_POLES.get(ax.slug, ("Левый полюс", "Правый полюс"))
        lean = lean_label(s, left, right)
        lines.append(f"«{ax.name}»: {lean}.")
    return lines


def snippet_around_match(text: str, query: str, radius: int = 48) -> str:
    """Фрагмент текста вокруг первого вхождения подстроки (без регистра)."""
    if not text or not query:
        return ""
    t = text.strip()
    q = query.strip()
    if not q:
        return t[: 2 * radius] + ("…" if len(t) > 2 * radius else "")
    low = t.lower()
    idx = low.find(q.lower())
    if idx < 0:
        return t[: 2 * radius] + ("…" if len(t) > 2 * radius else "")
    start = max(0, idx - radius)
    end = min(len(t), idx + len(q) + radius)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(t) else ""
    return prefix + t[start:end].strip() + suffix
