import random
from typing import (
    TypeVar,
    Sequence,
)

__all__: tuple[str, ...] = ("random_with_weights",)

T = TypeVar("T")


def _ensure_adds_to_whole(weights: Sequence[float]) -> Sequence[float]:
    sum_weights = sum(weights)
    dividend = 100 if sum_weights > 1 else 1
    max_weight: float = dividend / sum_weights
    return list(map(lambda w: w * max_weight, weights))


def random_with_weights(items: Sequence[T], weights: Sequence[float]) -> T:
    weights = _ensure_adds_to_whole(weights)
    choice = random.choices(items, weights=weights)[0]
    return choice
