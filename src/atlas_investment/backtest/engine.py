from __future__ import annotations

from atlas_investment.cost_policy import CostPolicy
from atlas_investment.models import Asset, BacktestResult, BacktestTrade, Candle, Side, Signal
from atlas_investment.strategy.base import StrategyPlugin
from atlas_investment.technical.indicators import max_drawdown


class BacktestEngine:
    def __init__(
        self,
        initial_cash: float = 10_000_000,
        fee_rate: float = 0.0005,
        slippage_rate: float = 0.0005,
        execution_lag_bars: int = 1,
    ) -> None:
        self.initial_cash = initial_cash
        self.fee_rate = fee_rate
        self.slippage_rate = slippage_rate
        self.execution_lag_bars = max(1, execution_lag_bars)
        self.sell_tax_rate = 0.0
        self.fx_spread_rate = 0.0

    @classmethod
    def from_cost_policy(cls, asset: Asset, policy: CostPolicy, initial_cash: float = 10_000_000) -> "BacktestEngine":
        market_policy = policy.market(asset.market)
        engine = cls(initial_cash=initial_cash, fee_rate=market_policy.commission_rate, slippage_rate=market_policy.slippage_rate)
        engine.sell_tax_rate = market_policy.sell_tax_rate
        engine.fx_spread_rate = market_policy.fx_spread_rate
        return engine

    def run(self, asset: Asset, candles: list[Candle], strategy: StrategyPlugin) -> BacktestResult:
        cash = self.initial_cash
        quantity = 0.0
        avg_price = 0.0
        trades: list[BacktestTrade] = []
        closed_pnls: list[float] = []
        equity_curve: list[dict[str, float | str]] = []
        pending_signal: tuple[int, Signal] | None = None
        active_stop_loss = -0.08
        active_take_profit = 0.18

        for index, candle in enumerate(candles):
            price = candle.close
            if pending_signal is not None and pending_signal[0] == index:
                signal = pending_signal[1]
                pending_signal = None
                if signal.stance == "buy" and quantity == 0 and signal.score >= 68:
                    budget = cash * min(signal.target_weight or 0.03, 0.12)
                    buy_price = candle.open * (1 + self.slippage_rate)
                    buy_quantity = int(budget // buy_price)
                    cost = buy_quantity * buy_price
                    fee = cost * (self.fee_rate + self.fx_spread_rate)
                    if buy_quantity > 0 and cost + fee <= cash:
                        cash -= cost + fee
                        quantity = float(buy_quantity)
                        avg_price = buy_price
                        active_stop_loss = signal.stop_loss_pct if signal.stop_loss_pct is not None else -0.08
                        active_take_profit = signal.take_profit_pct if signal.take_profit_pct is not None else 0.18
                        trades.append(BacktestTrade(asset.symbol, Side.BUY, quantity, buy_price, candle.date, "; ".join(signal.reasons), strategy.name))
                elif signal.stance == "sell" and quantity > 0:
                    sell_price = candle.open * (1 - self.slippage_rate)
                    proceeds = quantity * sell_price
                    fee = proceeds * (self.fee_rate + self.sell_tax_rate + self.fx_spread_rate)
                    cash += proceeds - fee
                    closed_pnls.append((sell_price - avg_price) * quantity - fee)
                    trades.append(BacktestTrade(asset.symbol, Side.SELL, quantity, sell_price, candle.date, "; ".join(signal.reasons), strategy.name))
                    quantity = 0.0
                    avg_price = 0.0

            if quantity > 0:
                unrealized = (price / avg_price) - 1 if avg_price else 0
                if unrealized <= active_stop_loss or unrealized >= active_take_profit:
                    sell_price = price * (1 - self.slippage_rate)
                    proceeds = quantity * sell_price
                    fee = proceeds * (self.fee_rate + self.sell_tax_rate + self.fx_spread_rate)
                    cash += proceeds - fee
                    reason = "손절 조건 도달" if unrealized <= active_stop_loss else "익절 조건 도달"
                    closed_pnls.append((sell_price - avg_price) * quantity - fee)
                    trades.append(BacktestTrade(asset.symbol, Side.SELL, quantity, sell_price, candle.date, reason, strategy.name))
                    quantity = 0.0
                    avg_price = 0.0

            signal = strategy.generate_signal(asset, candles, index)
            execution_index = index + self.execution_lag_bars
            if signal and execution_index < len(candles):
                if signal.stance == "buy" and quantity == 0 and pending_signal is None and signal.score >= 68:
                    pending_signal = (execution_index, signal)
                elif signal.stance == "sell" and quantity > 0 and pending_signal is None:
                    pending_signal = (execution_index, signal)

            equity = cash + quantity * price
            equity_curve.append({"date": candle.date, "equity": equity})

        if quantity > 0 and candles:
            last = candles[-1]
            sell_price = last.close * (1 - self.slippage_rate)
            proceeds = quantity * sell_price
            fee = proceeds * (self.fee_rate + self.sell_tax_rate + self.fx_spread_rate)
            cash += proceeds - fee
            closed_pnls.append((sell_price - avg_price) * quantity - fee)
            trades.append(BacktestTrade(asset.symbol, Side.SELL, quantity, sell_price, last.date, "백테스트 종료 청산", strategy.name))
            equity_curve[-1] = {"date": last.date, "equity": cash}

        final_equity = equity_curve[-1]["equity"] if equity_curve else self.initial_cash
        equity_values = [float(point["equity"]) for point in equity_curve]
        wins = [pnl for pnl in closed_pnls if pnl > 0]
        win_rate = (len(wins) / len(closed_pnls) * 100) if closed_pnls else 0.0
        return BacktestResult(
            strategy=strategy.name,
            symbol=asset.symbol,
            initial_cash=self.initial_cash,
            final_equity=float(final_equity),
            total_return_pct=(float(final_equity) / self.initial_cash - 1) * 100,
            max_drawdown_pct=max_drawdown(equity_values) * 100,
            trade_count=len(trades),
            win_rate_pct=win_rate,
            trades=trades,
            equity_curve=equity_curve,
        )
