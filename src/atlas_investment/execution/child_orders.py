from __future__ import annotations

from dataclasses import dataclass

from atlas_investment.execution.algorithms import AlgorithmicExecutionPlan, ExecutionSlice
from atlas_investment.models import TradingMode


@dataclass(frozen=True)
class ChildOrderExecution:
    sequence: int
    symbol: str
    planned_quantity: float
    filled_quantity: float
    status: str
    notes: list[str]


@dataclass(frozen=True)
class ChildOrderExecutionReport:
    status: str
    mode: str
    algorithm: str
    planned_slices: int
    filled_slices: int
    planned_quantity: float
    filled_quantity: float
    children: list[ChildOrderExecution]
    risk_notes: list[str]


class PaperChildOrderManager:
    """Simulates child-order lifecycle without touching a live broker."""

    def execute_plan(
        self,
        plan: AlgorithmicExecutionPlan,
        mode: TradingMode,
        fill_ratio: float = 1.0,
    ) -> ChildOrderExecutionReport:
        if plan.status != "simulated":
            return self._blocked(plan, mode, ["상위 집행 계획이 simulated 상태가 아닙니다."])
        if mode == TradingMode.LIVE_AUTO:
            return self._blocked(plan, mode, ["공식 브로커 API 전까지 child order live routing은 차단합니다."])
        if mode == TradingMode.OFF:
            return self._blocked(plan, mode, ["OFF 모드에서는 child order를 만들지 않습니다."])

        fill_ratio = max(0.0, min(fill_ratio, 1.0))
        children = [self._simulate_child(item, mode, fill_ratio) for item in plan.slices]
        filled_quantity = round(sum(child.filled_quantity for child in children), 6)
        filled_slices = sum(1 for child in children if child.status == "filled")
        status = "simulated" if mode == TradingMode.PAPER else "validated"
        notes = list(plan.risk_notes)
        if fill_ratio < 1:
            notes.append("부분체결 시나리오입니다. 실제 API 연결 후 cancel/replace 정책 검증이 필요합니다.")
        return ChildOrderExecutionReport(
            status=status,
            mode=mode.value,
            algorithm=plan.algorithm,
            planned_slices=plan.slice_count,
            filled_slices=filled_slices,
            planned_quantity=plan.total_quantity,
            filled_quantity=filled_quantity,
            children=children,
            risk_notes=notes,
        )

    @staticmethod
    def _simulate_child(item: ExecutionSlice, mode: TradingMode, fill_ratio: float) -> ChildOrderExecution:
        if mode == TradingMode.DRY_RUN:
            return ChildOrderExecution(item.sequence, item.symbol, item.quantity, 0.0, "validated", ["DRY_RUN은 검증만 수행하고 체결하지 않습니다."])
        filled = round(item.quantity * fill_ratio, 6)
        status = "filled" if filled >= item.quantity else "partially_filled" if filled > 0 else "submitted"
        return ChildOrderExecution(item.sequence, item.symbol, item.quantity, filled, status, item.notes)

    @staticmethod
    def _blocked(plan: AlgorithmicExecutionPlan, mode: TradingMode, reasons: list[str]) -> ChildOrderExecutionReport:
        return ChildOrderExecutionReport(
            status="blocked",
            mode=mode.value,
            algorithm=plan.algorithm,
            planned_slices=plan.slice_count,
            filled_slices=0,
            planned_quantity=plan.total_quantity,
            filled_quantity=0.0,
            children=[],
            risk_notes=reasons + plan.risk_notes,
        )
