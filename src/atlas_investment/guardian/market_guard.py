from __future__ import annotations

from atlas_investment.config import RiskPolicy


class MarketGuard:
    def can_start_cycle(self, policy: RiskPolicy) -> tuple[bool, str]:
        if policy.kill_switch:
            return False, "킬스위치가 켜져 있습니다."
        return True, "시장 감시 가드 통과"

