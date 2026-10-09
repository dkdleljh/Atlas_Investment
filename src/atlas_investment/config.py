from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RiskPolicy:
    kill_switch: bool
    allow_live_trading: bool
    allow_margin_trading: bool
    allow_credit_trading: bool
    allow_leveraged_inverse: bool
    min_cash_ratio: float
    max_single_position_weight: float
    max_leveraged_inverse_weight: float
    max_daily_order_amount_krw: float
    max_daily_loss_krw: float
    max_open_positions: int
    min_score_to_buy: int
    min_score_to_sell: int
    usdkrw_reference_rate: float = 1380.0


@dataclass(frozen=True)
class StrategyConfig:
    base_order_amount_krw: float
    target_position_weight: float
    markets: list[str]
    enabled_strategies: list[str]


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_risk_policy(path: Path) -> RiskPolicy:
    return RiskPolicy(**load_json(path))


def load_strategy_config(path: Path) -> StrategyConfig:
    return StrategyConfig(**load_json(path))
