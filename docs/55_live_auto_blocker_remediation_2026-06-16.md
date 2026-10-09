# Live Auto Blocker Remediation - 2026-06-16

## Current Decision

`LIVE_AUTO` must remain disabled.

The one-time `0177N0` live order round trip proved the official Toss route can submit a manually approved small order, but it is not evidence that unattended automatic trading is ready.

## Pilot Scope Approved 2026-06-16

The owner approved a limited pilot scope:

- markets: `KR`, `US`
- asset kinds: `stock`, `etf`
- broker/data scope: Toss Securities official API only
- evidence window: `3` days for dry-run, paper, read-only reconciliation, and heartbeat
- forbidden: margin, credit, short, derivatives, non-Toss official API routes
- pilot order limits:
  - max single order: KRW `20,000`
  - max daily order: KRW `50,000`
  - max daily loss: KRW `20,000`

## Already Resolved

- Broker/order reconciliation for the `0177N0` test is clean after the user manually sold the position.
- `reconciliation-check`: `ok`, difference count `0`.
- Legacy Toss read-only reports were archived out of active alert scanning.
- `alerts_check.json` no longer counts itself.
- Phase20 no longer hardcodes Toss official API as blocked when current official OpenAPI/reconciliation evidence exists.
- Phase20 is now `ok`: the Toss live order API item reflects the verified manual one-time live route, while unattended `LIVE_AUTO` remains governed by promotion evidence.
- `strategy_readiness_multifactor_qvm` now has enough PAPER candidates after widening the sample to 10 symbols and treats rejected low-trade symbols as warnings rather than live blockers.
- Lab-only `strategy_readiness_scalping_simulation.json` is excluded from alert aggregation because scalping is not in the active live promotion universe; its source report remains blocked for audit.
- `data_entitlements` is `ok` for the approved KR/US stock/ETF Toss official API pilot scope.
- `governance_report` is `ok` after the signed pilot approval was recorded.
- `heartbeat_audit` is `ok` under the approved 3-day pilot evidence window after daemon heartbeat was separated from live-readiness blockers.
- Global hedge-fund readiness reports remain blocked as source reports but are excluded from pilot alert aggregation.
- Daily safe evidence collection cron is installed:
  - cron: `Atlas Investment daily promotion evidence collect`
  - id: `ebc3e7e8-3763-4009-9f53-ca8a780ad71f`
  - schedule: weekdays `16:50` Asia/Seoul
  - command: `.venv/bin/python -m atlas_investment.cli promotion-evidence-collect --symbol 0177N0`
  - normal delivery: none
  - failure alert: after 1 error, 6h cooldown

## Remaining Critical Blockers

### 1. Data Entitlements

Current:

- provider_count: `1`
- verified provider: Toss official OpenAPI KR/US stock/ETF pilot scope
- pilot status: `ok`

Still missing for the global hedge-fund track:

- US/EU/JP/HK/CN/EM market rights
- bond/future/option/FX/commodity data rights
- survivorship-bias-free historical security master
- corporate-action-adjusted historical market data

Resolution:

- Use Toss official API only for the pilot scope.
- Add licensed institutional market-data providers only before claiming global multi-asset readiness.

### 2. Promotion Evidence

Current:

- dry_run: `1 / 3` business days
- paper: `1 / 3` business days
- read-only reconciliation: `1 / 3` business days
- manual small-order trials: `1 / 1`
- manual live promotion approval: `ok`

Resolution:

- Let the daily evidence cron accumulate real days.
- Do not backfill or fabricate dates.
- Only create `data/evidence/live_promotion_approval.json` after all evidence gates pass and the owner explicitly approves.

### 3. Governance Approval

Current:

- live promotion approval record is `ok` for `kr_us_stock_etf_pilot`.

Resolution:

- Keep `data/evidence/live_promotion_approval.json` scoped to the pilot.
- Do not reuse this approval for global multi-asset live_auto.

### 4. Heartbeat Evidence

Current:

- latest heartbeat: `ok`
- distinct UTC days: `17 / 3`
- pilot status: `ok`

Resolution:

- Continue daily supervised collection.
- Do not override historical heartbeat gaps.

### 5. Strategy Readiness

Blocked:

- `strategy_readiness_scalping_simulation`

Approved for paper:

- `strategy_readiness_multifactor_qvm`

Reasons:

- Multifactor QVM has 2 approved PAPER candidates; low-trade rejected symbols are warnings.
- Scalping PAPER candidates are still insufficient.
- Scalping requires realtime quote/order/fill/amend/cancel validation before live use.

Resolution:

- Keep these strategies in paper/lab mode.
- Use real-time data and longer paper history before promotion.
- Do not promote scalping until cancel/amend behavior is tested.
- Keep lab-only strategy reports out of live alert aggregation unless the strategy is explicitly added to the active live promotion universe.

### 6. Global Hedge-Fund Readiness

Current:

- status: blocked
- main blockers:
  - global universe coverage
  - global asset-class coverage
  - live broker readiness
  - data quality
  - live promotion gate

Resolution:

- Treat this as a long-term institutional-readiness track, not a prerequisite for one manually approved small live order.
- Do not use a fully global hedge-fund gate to justify turning on local unattended trading.

## Next Review

Run after each market day:

```bash
.venv/bin/python -m atlas_investment.cli promotion-evidence-collect --symbol 0177N0
.venv/bin/python -m atlas_investment.cli promotion-evidence
.venv/bin/python -m atlas_investment.cli alerts-check
.venv/bin/python -m atlas_investment.cli hedgefund-readiness
```

## Non-Negotiable Rule

No `LIVE_AUTO` until all of the following are true:

- promotion evidence is `ok`
- reconciliation is `ok`
- data entitlement scope is explicit and adequate for the traded universe
- strategy readiness is `ok` for the exact strategy universe
- manual approval JSON is valid and explicit
- 미수/신용 remains blocked
