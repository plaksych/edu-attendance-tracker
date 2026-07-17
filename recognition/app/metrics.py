"""Метрики устойчивости счёта и сравнение с эталонной разметкой."""

from __future__ import annotations

import statistics
from dataclasses import dataclass


@dataclass(frozen=True)
class CountMetrics:
    count_stddev: float
    absolute_error: int | None
    relative_error: float | None
    within_tolerance: bool | None


def calculate_count_metrics(
    counts: list[int], reference_people_count: int | None, tolerance_people: int
) -> CountMetrics:
    """Возвращает метрики ряда кадров и опционального ручного эталона."""
    if not counts:
        raise ValueError("для расчёта метрик нужен хотя бы один кадр")

    count_stddev = statistics.pstdev(counts) if len(counts) > 1 else 0.0
    if reference_people_count is None:
        return CountMetrics(
            count_stddev=count_stddev,
            absolute_error=None,
            relative_error=None,
            within_tolerance=None,
        )

    detected = round(statistics.median(counts))
    absolute_error = abs(detected - reference_people_count)
    return CountMetrics(
        count_stddev=count_stddev,
        absolute_error=absolute_error,
        relative_error=(
            absolute_error / reference_people_count
            if reference_people_count > 0
            else None
        ),
        within_tolerance=absolute_error <= tolerance_people,
    )
