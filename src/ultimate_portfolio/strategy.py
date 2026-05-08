from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import calendar
import math


@dataclass(frozen=True)
class Position:
    ticker: str
    market_value: float
    shares: float | None = None
    price: float | None = None

    def __post_init__(self) -> None:
        if not self.ticker.strip():
            raise ValueError("Ticker cannot be blank.")
        if self.market_value < 0:
            raise ValueError(f"{self.ticker}: market value cannot be negative.")
        if self.shares is not None and self.shares < 0:
            raise ValueError(f"{self.ticker}: shares cannot be negative.")
        if self.price is not None and self.price <= 0:
            raise ValueError(f"{self.ticker}: price must be positive.")

    @property
    def symbol(self) -> str:
        return self.ticker.upper().strip()


@dataclass(frozen=True)
class HoldingTarget:
    ticker: str
    bucket_weight: float

    def __post_init__(self) -> None:
        if not self.ticker.strip():
            raise ValueError("Holding target ticker cannot be blank.")
        if self.bucket_weight < 0:
            raise ValueError(f"{self.ticker}: bucket weight cannot be negative.")

    @property
    def symbol(self) -> str:
        return self.ticker.upper().strip()


@dataclass(frozen=True)
class BucketConfig:
    name: str
    target_weight: float
    holdings: tuple[HoldingTarget, ...]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Bucket name cannot be blank.")
        if self.target_weight <= 0:
            raise ValueError(f"{self.name}: target weight must be positive.")
        if not self.holdings:
            raise ValueError(f"{self.name}: at least one holding is required.")
        weight_sum = sum(holding.bucket_weight for holding in self.holdings)
        if not math.isclose(weight_sum, 1.0, abs_tol=1e-9):
            raise ValueError(f"{self.name}: holding weights must sum to 1.0, got {weight_sum:.6f}.")

    @classmethod
    def from_bucket_weights(cls, name: str, target_weight: float, weights: dict[str, float]) -> BucketConfig:
        total = sum(weights.values())
        if total <= 0:
            raise ValueError(f"{name}: weights must sum to a positive value.")
        holdings = tuple(HoldingTarget(ticker, weight / total) for ticker, weight in weights.items())
        return cls(name=name, target_weight=target_weight, holdings=holdings)

    @classmethod
    def from_portfolio_weights(cls, name: str, target_weight: float, weights: dict[str, float]) -> BucketConfig:
        total = sum(weights.values())
        if not math.isclose(total, target_weight, abs_tol=1e-9):
            raise ValueError(
                f"{name}: portfolio weights must sum to the bucket target "
                f"({target_weight:.6f}), got {total:.6f}."
            )
        holdings = tuple(HoldingTarget(ticker, weight / target_weight) for ticker, weight in weights.items())
        return cls(name=name, target_weight=target_weight, holdings=holdings)

    @property
    def symbol_to_internal_weight(self) -> dict[str, float]:
        return {holding.symbol: holding.bucket_weight for holding in self.holdings}

    @property
    def symbols(self) -> set[str]:
        return set(self.symbol_to_internal_weight)


@dataclass(frozen=True)
class BucketAllocation:
    name: str
    current_value: float
    target_weight: float
    current_weight: float
    drift: float


@dataclass(frozen=True)
class TradeOrder:
    ticker: str
    current_value: float
    target_value: float
    trade_value: float
    price: float | None = None

    @property
    def share_delta(self) -> float | None:
        if self.price is None:
            return None
        return self.trade_value / self.price

    @property
    def side(self) -> str:
        if self.trade_value > 0.005:
            return "BUY"
        if self.trade_value < -0.005:
            return "SELL"
        return "HOLD"


@dataclass(frozen=True)
class AnalysisResult:
    as_of: date
    total_value: float
    satellite_weight: float
    satellite_drift: float
    boundary_triggered: bool
    calendar_sweep_due: bool
    current_drawdown: float | None
    circuit_breaker_triggered: bool
    rebalance_mode: str
    buckets: tuple[BucketAllocation, ...]
    orders: tuple[TradeOrder, ...]
    review_notes: tuple[str, ...] = ()

    @property
    def has_trades(self) -> bool:
        return any(not math.isclose(order.trade_value, 0.0, abs_tol=0.005) for order in self.orders)


class HierarchicalStrategy:
    def __init__(
        self,
        buckets: tuple[BucketConfig, ...],
        *,
        satellite_bucket: str = "satellite",
        drift_threshold: float = 0.05,
        circuit_breaker_drawdown: float = 0.20,
        circuit_breaker_destination: str = "SGOV",
        expected_core_return: float = 0.112,
        expected_satellite_return: float = 0.285,
        benchmark_weights: dict[str, float] | None = None,
    ) -> None:
        if drift_threshold <= 0:
            raise ValueError("Drift threshold must be positive.")
        if circuit_breaker_drawdown <= 0:
            raise ValueError("Circuit breaker drawdown must be positive.")
        if not buckets:
            raise ValueError("At least one bucket is required.")
        target_sum = sum(bucket.target_weight for bucket in buckets)
        if not math.isclose(target_sum, 1.0, abs_tol=1e-9):
            raise ValueError(f"Bucket target weights must sum to 1.0, got {target_sum:.6f}.")

        seen_symbols: set[str] = set()
        for bucket in buckets:
            overlap = seen_symbols & bucket.symbols
            if overlap:
                raise ValueError(f"Tickers can only appear in one bucket: {', '.join(sorted(overlap))}.")
            seen_symbols |= bucket.symbols

        satellite = next((bucket for bucket in buckets if bucket.name == satellite_bucket), None)
        if satellite is None:
            raise ValueError(f"Satellite bucket '{satellite_bucket}' not found.")
        if circuit_breaker_destination.upper() not in seen_symbols:
            raise ValueError(f"Circuit breaker destination '{circuit_breaker_destination}' must be a strategy holding.")

        self.buckets = buckets
        self.satellite_bucket = satellite_bucket
        self.drift_threshold = drift_threshold
        self.circuit_breaker_drawdown = circuit_breaker_drawdown
        self.circuit_breaker_destination = circuit_breaker_destination.upper()
        self.expected_core_return = expected_core_return
        self.expected_satellite_return = expected_satellite_return
        self.benchmark_weights = benchmark_weights or {"VBIAX": 0.80, "QQQ": 0.20}
        self._bucket_by_name = {bucket.name: bucket for bucket in buckets}
        self._symbol_to_bucket = {
            symbol: bucket.name
            for bucket in buckets
            for symbol in bucket.symbols
        }

    @property
    def symbols(self) -> set[str]:
        return set(self._symbol_to_bucket)

    @property
    def total_expected_return(self) -> float:
        core = self._bucket_by_name["core"].target_weight * self.expected_core_return
        satellite = self._bucket_by_name[self.satellite_bucket].target_weight * self.expected_satellite_return
        return core + satellite

    def analyze(
        self,
        positions: list[Position],
        as_of: date,
        *,
        force_sweep: bool = False,
        auto_calendar_sweep: bool = True,
        full_rebalance: bool = False,
        peak_value: float | None = None,
        enforce_circuit_breaker: bool = True,
    ) -> AnalysisResult:
        values, prices = self._collapse_positions(positions)
        total_value = sum(values.values())
        if total_value <= 0:
            raise ValueError("Portfolio total value must be positive.")

        bucket_values = self._bucket_values(values)
        buckets = tuple(
            BucketAllocation(
                name=bucket.name,
                current_value=bucket_values[bucket.name],
                target_weight=bucket.target_weight,
                current_weight=bucket_values[bucket.name] / total_value,
                drift=(bucket_values[bucket.name] / total_value) - bucket.target_weight,
            )
            for bucket in self.buckets
        )

        current_drawdown = self._current_drawdown(total_value, peak_value)
        circuit_breaker_triggered = (
            enforce_circuit_breaker
            and current_drawdown is not None
            and current_drawdown <= -self.circuit_breaker_drawdown + 1e-12
        )

        satellite = self._bucket_by_name[self.satellite_bucket]
        satellite_weight = bucket_values[self.satellite_bucket] / total_value
        satellite_drift = satellite_weight - satellite.target_weight
        boundary_triggered = abs(satellite_drift) >= self.drift_threshold - 1e-12
        calendar_sweep_due = force_sweep or (auto_calendar_sweep and is_calendar_quarter_end(as_of))
        review_notes: list[str] = []

        if circuit_breaker_triggered:
            rebalance_mode = "circuit_breaker"
            target_values = self._circuit_breaker_targets(values)
            review_notes.append(
                "Total portfolio drawdown breached the uncle point; move satellite exposure to SGOV and run a hardware-cycle review."
            )
        elif full_rebalance or (boundary_triggered and calendar_sweep_due):
            rebalance_mode = "full"
            target_values = self._full_targets(total_value)
        elif boundary_triggered:
            rebalance_mode = "boundary"
            target_values = self._boundary_targets(values, bucket_values, total_value)
        elif calendar_sweep_due:
            rebalance_mode = "internal"
            target_values = self._internal_sweep_targets(bucket_values)
        else:
            rebalance_mode = "hold"
            target_values = {symbol: values.get(symbol, 0.0) for symbol in self.symbols}

        orders = tuple(
            TradeOrder(
                ticker=symbol,
                current_value=values.get(symbol, 0.0),
                target_value=target_values.get(symbol, 0.0),
                trade_value=target_values.get(symbol, 0.0) - values.get(symbol, 0.0),
                price=prices.get(symbol),
            )
            for symbol in sorted(self.symbols)
        )

        return AnalysisResult(
            as_of=as_of,
            total_value=total_value,
            satellite_weight=satellite_weight,
            satellite_drift=satellite_drift,
            boundary_triggered=boundary_triggered,
            calendar_sweep_due=calendar_sweep_due,
            current_drawdown=current_drawdown,
            circuit_breaker_triggered=circuit_breaker_triggered,
            rebalance_mode=rebalance_mode,
            buckets=buckets,
            orders=orders,
            review_notes=tuple(review_notes),
        )

    def total_target_weights(self) -> dict[str, float]:
        targets: dict[str, float] = {}
        for bucket in self.buckets:
            for holding in bucket.holdings:
                targets[holding.symbol] = bucket.target_weight * holding.bucket_weight
        return targets

    def bucket_for_symbol(self, symbol: str) -> str:
        normalized = symbol.upper().strip()
        if normalized not in self._symbol_to_bucket:
            raise ValueError(f"Unknown ticker for this strategy: {normalized}.")
        return self._symbol_to_bucket[normalized]

    def _collapse_positions(self, positions: list[Position]) -> tuple[dict[str, float], dict[str, float]]:
        values = {symbol: 0.0 for symbol in self.symbols}
        prices: dict[str, float] = {}
        unknown: set[str] = set()
        for position in positions:
            symbol = position.symbol
            if symbol not in self.symbols:
                unknown.add(symbol)
                continue
            values[symbol] += position.market_value
            if position.price is not None:
                prices[symbol] = position.price

        if unknown:
            raise ValueError(f"Unknown ticker(s) for this strategy: {', '.join(sorted(unknown))}.")
        return values, prices

    def _bucket_values(self, values: dict[str, float]) -> dict[str, float]:
        totals = {bucket.name: 0.0 for bucket in self.buckets}
        for symbol, value in values.items():
            totals[self._symbol_to_bucket[symbol]] += value
        return totals

    def _full_targets(self, total_value: float) -> dict[str, float]:
        targets: dict[str, float] = {}
        for bucket in self.buckets:
            bucket_target_value = total_value * bucket.target_weight
            for holding in bucket.holdings:
                targets[holding.symbol] = bucket_target_value * holding.bucket_weight
        return targets

    def _boundary_targets(
        self,
        values: dict[str, float],
        bucket_values: dict[str, float],
        total_value: float,
    ) -> dict[str, float]:
        targets: dict[str, float] = {}
        for bucket in self.buckets:
            current_bucket_value = bucket_values[bucket.name]
            target_bucket_value = total_value * bucket.target_weight
            if current_bucket_value > 0:
                for holding in bucket.holdings:
                    current_value = values.get(holding.symbol, 0.0)
                    targets[holding.symbol] = target_bucket_value * (current_value / current_bucket_value)
            else:
                for holding in bucket.holdings:
                    targets[holding.symbol] = target_bucket_value * holding.bucket_weight
        return targets

    def _internal_sweep_targets(self, bucket_values: dict[str, float]) -> dict[str, float]:
        targets: dict[str, float] = {}
        for bucket in self.buckets:
            current_bucket_value = bucket_values[bucket.name]
            for holding in bucket.holdings:
                targets[holding.symbol] = current_bucket_value * holding.bucket_weight
        return targets

    def _circuit_breaker_targets(self, values: dict[str, float]) -> dict[str, float]:
        targets = dict(values)
        satellite_value = 0.0
        for symbol, bucket_name in self._symbol_to_bucket.items():
            if bucket_name == self.satellite_bucket:
                satellite_value += values.get(symbol, 0.0)
                targets[symbol] = 0.0
        targets[self.circuit_breaker_destination] += satellite_value
        return targets

    def _current_drawdown(self, total_value: float, peak_value: float | None) -> float | None:
        if peak_value is None:
            return None
        if peak_value <= 0:
            raise ValueError("Peak value must be positive when provided.")
        return (total_value / peak_value) - 1.0


def is_calendar_quarter_end(day: date) -> bool:
    return day.month in {3, 6, 9, 12} and day.day == calendar.monthrange(day.year, day.month)[1]


def build_default_strategy(*, stagflation_overlay: bool = False) -> HierarchicalStrategy:
    core_weights = {
        "COWZ": 0.35,
        "WMT": 0.05,
        "JPM": 0.05,
        "DE": 0.05,
        "DBMF": 0.25,
        "SGOV": 0.125,
        "TLT": 0.125,
    }
    if stagflation_overlay:
        core_weights["SGOV"] -= 0.025
        core_weights["TLT"] -= 0.025
        core_weights["GLDM"] = 0.05

    return HierarchicalStrategy(
        buckets=(
            BucketConfig.from_bucket_weights("core", 0.80, core_weights),
            BucketConfig.from_bucket_weights(
                "satellite",
                0.20,
                {
                    "SPRX": 0.40,
                    "ARKQ": 0.35,
                    "ELFY": 0.15,
                    "BAI": 0.10,
                },
            ),
        ),
        satellite_bucket="satellite",
        drift_threshold=0.05,
        circuit_breaker_drawdown=0.20,
        circuit_breaker_destination="SGOV",
        expected_core_return=0.112,
        expected_satellite_return=0.285,
        benchmark_weights={"VANGUARD_BALANCED": 0.80, "NASDAQ_100": 0.20},
    )


DEFAULT_STRATEGY = build_default_strategy()
