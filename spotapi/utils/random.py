"""Weighted random selection."""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from typing import TypeVar

__all__ = ("random_with_weights",)

T = TypeVar("T")


def random_with_weights(items: Sequence[T], weights: Sequence[float]) -> T:
    """Choose one item according to its non-negative relative weight.

    Raises:
        ValueError: If the input is empty, lengths differ, weights are
            non-finite or negative, or all weights are zero.
    """
    if not items or len(items) != len(weights):
        raise ValueError("items and weights must be nonempty and equally sized")

    if any(not math.isfinite(w) or w < 0 for w in weights) or not any(weights):
        raise ValueError("weights must be finite, non-negative and not all zero")

    return random.choices(items, weights=weights, k=1)[0]
