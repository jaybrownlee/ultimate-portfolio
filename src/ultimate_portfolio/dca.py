from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import calendar
import math

from .strategy import HierarchicalStrategy


DEFENSIVE_ENTRY_SYMBOLS = ("COWZ", "DBMF", "SGOV")


@dataclass(frozen=True)
class DcaAllocation:
    scheduled_date: date
    phase: str
    ticker: str
    amount: float


@dataclass(frozen=True)
class DcaSchedule:
    total_cash: float
    initial_deploy_pct: float
    months: int
    allocations: tuple[DcaAllocation, ...]

    @property
    def total_allocated(self) -> float:
        return sum(allocation.amount for allocation in self.allocations)


def build_dca_schedule(
    strategy: HierarchicalStrategy,
    total_cash: float,
    start_date: date,
    *,
    months: int = 6,
    initial_deploy_pct: float = 0.25,
    defensive_symbols: tuple[str, ...] = DEFENSIVE_ENTRY_SYMBOLS,
) -> DcaSchedule:
    if total_cash <= 0:
        raise ValueError("Total cash must be positive.")
    if not 1 <= months <= 6:
        raise ValueError("DCA months must be between 1 and 6.")
    if not 0 < initial_deploy_pct < 1:
        raise ValueError("Initial deploy percent must be between 0 and 1.")

    targets = strategy.total_target_weights()
    normalized_defensive = tuple(symbol.upper().strip() for symbol in defensive_symbols)
    missing = [symbol for symbol in normalized_defensive if symbol not in targets]
    if missing:
        raise ValueError(f"Defensive entry symbols are not in the strategy: {', '.join(missing)}.")

    initial_cash = total_cash * initial_deploy_pct
    defensive_weight = sum(targets[symbol] for symbol in normalized_defensive)
    if defensive_weight <= 0:
        raise ValueError("Defensive entry symbols must have positive target weight.")

    allocations: list[DcaAllocation] = []
    initial_by_symbol: dict[str, float] = {symbol: 0.0 for symbol in targets}
    for symbol in normalized_defensive:
        amount = initial_cash * (targets[symbol] / defensive_weight)
        initial_by_symbol[symbol] = amount
        allocations.append(DcaAllocation(start_date, "initial_defensive_core", symbol, amount))

    final_targets = {symbol: total_cash * weight for symbol, weight in targets.items()}
    gaps = {symbol: max(final_targets[symbol] - initial_by_symbol.get(symbol, 0.0), 0.0) for symbol in targets}
    gap_total = sum(gaps.values())
    remaining_cash = total_cash - initial_cash

    if not math.isclose(gap_total, remaining_cash, abs_tol=0.01):
        scale = remaining_cash / gap_total if gap_total else 0.0
        gaps = {symbol: amount * scale for symbol, amount in gaps.items()}

    for month in range(1, months + 1):
        scheduled_date = add_months(start_date, month)
        for symbol in sorted(gaps):
            amount = gaps[symbol] / months
            if amount > 0.005:
                allocations.append(DcaAllocation(scheduled_date, "monthly_dca", symbol, amount))

    return DcaSchedule(
        total_cash=total_cash,
        initial_deploy_pct=initial_deploy_pct,
        months=months,
        allocations=tuple(allocations),
    )


def add_months(day: date, months: int) -> date:
    month_index = day.month - 1 + months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day.day, last_day))
