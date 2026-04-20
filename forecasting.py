from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray
import pandas as pd

__all__ = ["forecast_values", "forecast_sales"]


def forecast_values(values: Sequence[float], periods: int = 5) -> list[float]:
    if periods < 1:
        raise ValueError("periods must be at least 1")

    y: NDArray[np.float64] = np.asarray(values, dtype=np.float64)
    if y.ndim != 1 or len(y) == 0:
        raise ValueError("values must be a non-empty one-dimensional sequence")
    if len(y) == 1:
        return [float(y[0])] * periods

    index: NDArray[np.float64] = np.arange(len(y), dtype=np.float64)
    slope, intercept = np.polyfit(index, y, deg=1)

    future_index: NDArray[np.float64] = np.arange(
        len(y), len(y) + periods, dtype=np.float64
    )
    predictions = (slope * future_index) + intercept

    return predictions.tolist()


def forecast_sales(df: pd.DataFrame, column: str = "Amount", periods: int = 5) -> list[float]:
    values = pd.to_numeric(df[column], errors="coerce").dropna()
    return forecast_values(values.tolist(), periods=periods)
