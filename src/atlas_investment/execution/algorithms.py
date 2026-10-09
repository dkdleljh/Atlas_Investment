from __future__ import annotations

from dataclasses import dataclass

from atlas_investment.models import OrderIntent, TradingMode


@dataclass(frozen=True)
class ExecutionSlice:
    sequence: int
    symbol: str
    quantity: float
    participation_rate: float
    earliest_minute: int
    latest_minute: int
    order_type: str
    notes: list[str]


@dataclass(frozen=True)
class AlgorithmicExecutionPlan:
    algorithm: str
    status: str
    order_count: int
    slice_count: int
    total_quantity: float
    slices: list[ExecutionSlice]
    risk_notes: list[str]


class AlgorithmicExecutionPlanner:
    """Builds deterministic VWAP/TWAP/POV/adaptive slice plans without sending orders."""

    def plan(
        self,
        orders: list[OrderIntent],
        algorithm: str,
        mode: TradingMode,
        slices_per_order: int = 6,
        participation_rate: float = 0.08,
    ) -> AlgorithmicExecutionPlan:
        algorithm = algorithm.lower()
        if algorithm not in {"twap", "vwap", "pov", "adaptive"}:
            return AlgorithmicExecutionPlan(algorithm, "blocked", len(orders), 0, 0.0, [], [f"지원하지 않는 집행 알고리즘입니다: {algorithm}"])
        if mode == TradingMode.LIVE_AUTO:
            return AlgorithmicExecutionPlan(algorithm, "blocked", len(orders), 0, 0.0, [], ["공식 브로커 API, 실시간 호가, 미체결 정정/취소가 검증되기 전까지 실시간 알고리즘 집행은 차단합니다."])
        slices_per_order = max(1, min(slices_per_order, 24))
        participation_rate = max(0.001, min(participation_rate, 0.25))
        slices: list[ExecutionSlice] = []
        sequence = 1
        for order in orders:
            weights = self._slice_weights(algorithm, slices_per_order)
            total_weight = sum(weights)
            remaining = order.quantity
            for index, weight in enumerate(weights):
                quantity = order.quantity * weight / total_weight if index < slices_per_order - 1 else remaining
                remaining -= quantity
                slice_participation = participation_rate if algorithm in {"pov", "adaptive"} else 0.0
                slices.append(
                    ExecutionSlice(
                        sequence=sequence,
                        symbol=order.asset.symbol,
                        quantity=round(quantity, 6),
                        participation_rate=slice_participation,
                        earliest_minute=index * 5,
                        latest_minute=(index + 1) * 5,
                        order_type=order.order_type.value,
                        notes=self._slice_notes(algorithm),
                    )
                )
                sequence += 1
        risk_notes = [
            "모든 slice는 주문 상태 머신/idempotency 저장소와 pre-trade batch risk를 통과해야 합니다.",
            "부분체결, 정정, 취소, 장중 변동성 중단 조건은 공식 API 연결 후 별도 실증이 필요합니다.",
        ]
        return AlgorithmicExecutionPlan(algorithm, "simulated", len(orders), len(slices), round(sum(item.quantity for item in slices), 6), slices, risk_notes)

    @staticmethod
    def _slice_weights(algorithm: str, slices_per_order: int) -> list[float]:
        if algorithm == "vwap" and slices_per_order > 1:
            return [1.2 if index in {0, slices_per_order - 1} else 1.0 for index in range(slices_per_order)]
        if algorithm == "adaptive" and slices_per_order > 1:
            midpoint = (slices_per_order - 1) / 2
            return [1.0 + abs(index - midpoint) / max(midpoint, 1.0) * 0.35 for index in range(slices_per_order)]
        return [1.0 for _ in range(slices_per_order)]

    @staticmethod
    def _slice_notes(algorithm: str) -> list[str]:
        if algorithm == "twap":
            return ["시간 균등 분할 집행 후보입니다."]
        if algorithm == "vwap":
            return ["거래량 곡선 프록시 기반 집행 후보입니다. 실제 거래량 곡선으로 교체해야 합니다."]
        if algorithm == "adaptive":
            return ["VWAP 곡선과 POV 참여율을 혼합한 adaptive 집행 후보입니다. 실시간 스프레드/호가 기반 정정은 공식 API 연결 후 활성화합니다."]
        return ["목표 시장 참여율 기반 집행 후보입니다. 실시간 거래량 피드가 필요합니다."]
