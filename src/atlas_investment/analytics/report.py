from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Any

from atlas_investment.models import BacktestResult


def _default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def save_backtest_result(result: BacktestResult, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(asdict(result), file, ensure_ascii=False, indent=2, default=_default)
    return path


def summarize_backtest(result: BacktestResult) -> dict[str, float | int | str]:
    return {
        "strategy": result.strategy,
        "symbol": result.symbol,
        "initial_cash": result.initial_cash,
        "final_equity": round(result.final_equity, 2),
        "total_return_pct": round(result.total_return_pct, 2),
        "max_drawdown_pct": round(result.max_drawdown_pct, 2),
        "trade_count": result.trade_count,
        "win_rate_pct": round(result.win_rate_pct, 2),
    }

