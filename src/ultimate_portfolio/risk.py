from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
import random
import statistics

from .strategy import HierarchicalStrategy, Position


@dataclass(frozen=True)
class StressScenario:
    name: str
    description: str
    shocks: dict[str, float]


@dataclass(frozen=True)
class StressResult:
    name: str
    description: str
    total_value: float
    total_return: float
    satellite_weight: float
    boundary_triggered: bool
    circuit_breaker_triggered: bool
    rebalance_mode: str


@dataclass(frozen=True)
class MonteCarloAssumptions:
    years: int = 10
    paths: int = 5000
    starting_value: float = 100000.0
    core_expected_return: float = 0.112
    satellite_expected_return: float = 0.285
    core_volatility: float = 0.115
    satellite_volatility: float = 0.38
    core_satellite_correlation: float = 0.25
    sgov_return: float = 0.045
    sgov_volatility: float = 0.01
    seed: int | None = 7


@dataclass(frozen=True)
class MonteCarloResult:
    paths: int
    years: int
    starting_value: float
    median_ending_value: float
    percentile_5_ending_value: float
    percentile_95_ending_value: float
    probability_of_loss: float
    probability_circuit_breaker: float
    median_max_drawdown: float
    average_max_drawdown: float


@dataclass(frozen=True)
class ReviewObservation:
    observation_date: date
    portfolio_value: float
    benchmark_value: float | None = None
    satellite_value: float | None = None
    qqq_value: float | None = None


@dataclass(frozen=True)
class MonthlyReviewResult:
    start_date: date
    end_date: date
    portfolio_return: float
    benchmark_return: float | None
    active_return: float | None
    max_drawdown: float
    circuit_breaker_triggered: bool
    satellite_relative_strength: float | None
    review_flags: tuple[str, ...]


@dataclass(frozen=True)
class AdopterMetrics:
    ticker: str
    it_capex_growth: float
    sgna_intensity_change: float
    gross_margin_expansion_bps: float


@dataclass(frozen=True)
class AdopterScreenResult:
    ticker: str
    passed: bool
    score: int
    it_capex_growth_passed: bool
    sgna_intensity_passed: bool
    gross_margin_passed: bool


DEFAULT_STRESS_SCENARIOS = (
    StressScenario(
        name="high_rate_tech_selloff",
        description="Rates jump and long-duration growth derates; TLT and AI hardware are hit together.",
        shocks={
            "COWZ": -0.08,
            "WMT": -0.04,
            "JPM": -0.10,
            "DE": -0.12,
            "DBMF": 0.06,
            "SGOV": 0.01,
            "TLT": -0.18,
            "SPRX": -0.28,
            "ARKQ": -0.32,
            "ELFY": -0.24,
            "BAI": -0.30,
            "GLDM": 0.04,
        },
    ),
    StressScenario(
        name="ai_hardware_cycle_bust",
        description="AI infrastructure capex expectations reset and satellite holdings enter a hardware downcycle.",
        shocks={
            "COWZ": -0.10,
            "WMT": -0.06,
            "JPM": -0.12,
            "DE": -0.16,
            "DBMF": 0.08,
            "SGOV": 0.01,
            "TLT": 0.06,
            "SPRX": -0.45,
            "ARKQ": -0.42,
            "ELFY": -0.35,
            "BAI": -0.38,
            "GLDM": 0.03,
        },
    ),
    StressScenario(
        name="recession_deflation",
        description="Equities fall, Treasury duration rallies, and managed futures diversify the equity shock.",
        shocks={
            "COWZ": -0.18,
            "WMT": -0.08,
            "JPM": -0.22,
            "DE": -0.25,
            "DBMF": 0.10,
            "SGOV": 0.01,
            "TLT": 0.18,
            "SPRX": -0.30,
            "ARKQ": -0.34,
            "ELFY": -0.26,
            "BAI": -0.32,
            "GLDM": 0.02,
        },
    ),
    StressScenario(
        name="stagflation_rates_up",
        description="Inflation pressure hits duration and multiples while trend and gold-like exposure help.",
        shocks={
            "COWZ": -0.10,
            "WMT": -0.07,
            "JPM": -0.08,
            "DE": -0.14,
            "DBMF": 0.12,
            "SGOV": 0.01,
            "TLT": -0.20,
            "SPRX": -0.22,
            "ARKQ": -0.25,
            "ELFY": -0.18,
            "BAI": -0.24,
            "GLDM": 0.15,
        },
    ),
)


def run_stress_scenarios(
    strategy: HierarchicalStrategy,
    positions: list[Position],
    as_of: date,
    *,
    peak_value: float | None = None,
    scenarios: tuple[StressScenario, ...] = DEFAULT_STRESS_SCENARIOS,
) -> tuple[StressResult, ...]:
    values, _ = strategy._collapse_positions(positions)
    starting_value = sum(values.values())
    if starting_value <= 0:
        raise ValueError("Portfolio total value must be positive.")

    results: list[StressResult] = []
    for scenario in scenarios:
        stressed_positions = [
            Position(symbol, value * (1.0 + scenario.shocks.get(symbol, 0.0)))
            for symbol, value in values.items()
        ]
        result = strategy.analyze(stressed_positions, as_of, peak_value=peak_value or starting_value)
        results.append(
            StressResult(
                name=scenario.name,
                description=scenario.description,
                total_value=result.total_value,
                total_return=(result.total_value / starting_value) - 1.0,
                satellite_weight=result.satellite_weight,
                boundary_triggered=result.boundary_triggered,
                circuit_breaker_triggered=result.circuit_breaker_triggered,
                rebalance_mode=result.rebalance_mode,
            )
        )
    return tuple(results)


def run_monte_carlo(strategy: HierarchicalStrategy, assumptions: MonteCarloAssumptions) -> MonteCarloResult:
    if assumptions.years <= 0:
        raise ValueError("Monte Carlo years must be positive.")
    if assumptions.paths <= 0:
        raise ValueError("Monte Carlo paths must be positive.")
    if assumptions.starting_value <= 0:
        raise ValueError("Monte Carlo starting value must be positive.")
    if not -1 <= assumptions.core_satellite_correlation <= 1:
        raise ValueError("Correlation must be between -1 and 1.")

    rng = random.Random(assumptions.seed)
    months = assumptions.years * 12
    ending_values: list[float] = []
    max_drawdowns: list[float] = []
    circuit_breaker_count = 0

    monthly_core_mu = assumptions.core_expected_return / 12
    monthly_satellite_mu = assumptions.satellite_expected_return / 12
    monthly_sgov_mu = assumptions.sgov_return / 12
    monthly_core_vol = assumptions.core_volatility / math.sqrt(12)
    monthly_satellite_vol = assumptions.satellite_volatility / math.sqrt(12)
    monthly_sgov_vol = assumptions.sgov_volatility / math.sqrt(12)
    corr = assumptions.core_satellite_correlation
    corr_residual = math.sqrt(max(1 - corr * corr, 0.0))

    for _ in range(assumptions.paths):
        core_value = assumptions.starting_value * strategy._bucket_by_name["core"].target_weight
        satellite_value = assumptions.starting_value * strategy._bucket_by_name[strategy.satellite_bucket].target_weight
        peak = assumptions.starting_value
        max_drawdown = 0.0
        circuit_tripped = False

        for _month in range(months):
            z_core = rng.gauss(0, 1)
            z_satellite = corr * z_core + corr_residual * rng.gauss(0, 1)
            core_return = max(monthly_core_mu + monthly_core_vol * z_core, -0.95)
            if circuit_tripped:
                satellite_return = max(monthly_sgov_mu + monthly_sgov_vol * z_satellite, -0.95)
            else:
                satellite_return = max(monthly_satellite_mu + monthly_satellite_vol * z_satellite, -0.95)

            core_value *= 1 + core_return
            satellite_value *= 1 + satellite_return
            total_value = core_value + satellite_value
            peak = max(peak, total_value)
            drawdown = (total_value / peak) - 1.0
            max_drawdown = min(max_drawdown, drawdown)

            if not circuit_tripped and drawdown <= -strategy.circuit_breaker_drawdown:
                circuit_tripped = True
                core_value += satellite_value
                satellite_value = 0.0
                total_value = core_value

            if not circuit_tripped:
                satellite_weight = satellite_value / total_value if total_value else 0.0
                target_satellite = strategy._bucket_by_name[strategy.satellite_bucket].target_weight
                if abs(satellite_weight - target_satellite) >= strategy.drift_threshold - 1e-12:
                    core_value = total_value * strategy._bucket_by_name["core"].target_weight
                    satellite_value = total_value * target_satellite

        ending_values.append(core_value + satellite_value)
        max_drawdowns.append(max_drawdown)
        if circuit_tripped:
            circuit_breaker_count += 1

    sorted_endings = sorted(ending_values)
    return MonteCarloResult(
        paths=assumptions.paths,
        years=assumptions.years,
        starting_value=assumptions.starting_value,
        median_ending_value=statistics.median(sorted_endings),
        percentile_5_ending_value=percentile(sorted_endings, 0.05),
        percentile_95_ending_value=percentile(sorted_endings, 0.95),
        probability_of_loss=sum(value < assumptions.starting_value for value in ending_values) / assumptions.paths,
        probability_circuit_breaker=circuit_breaker_count / assumptions.paths,
        median_max_drawdown=statistics.median(max_drawdowns),
        average_max_drawdown=statistics.fmean(max_drawdowns),
    )


def review_history(
    observations: list[ReviewObservation],
    *,
    circuit_breaker_drawdown: float = 0.20,
) -> MonthlyReviewResult:
    if len(observations) < 2:
        raise ValueError("At least two review observations are required.")
    ordered = sorted(observations, key=lambda row: row.observation_date)
    start = ordered[0]
    end = ordered[-1]
    portfolio_return = (end.portfolio_value / start.portfolio_value) - 1.0
    max_drawdown = calculate_max_drawdown([row.portfolio_value for row in ordered])
    circuit = max_drawdown <= -circuit_breaker_drawdown + 1e-12

    benchmark_return = None
    active_return = None
    if start.benchmark_value and end.benchmark_value:
        benchmark_return = (end.benchmark_value / start.benchmark_value) - 1.0
        active_return = portfolio_return - benchmark_return

    satellite_relative_strength = None
    if start.satellite_value and end.satellite_value and start.qqq_value and end.qqq_value:
        satellite_return = (end.satellite_value / start.satellite_value) - 1.0
        qqq_return = (end.qqq_value / start.qqq_value) - 1.0
        satellite_relative_strength = satellite_return - qqq_return

    flags: list[str] = []
    if circuit:
        flags.append("Circuit breaker breached: move satellite to SGOV and run structural hardware-cycle review.")
    if satellite_relative_strength is not None and satellite_relative_strength < -0.05:
        flags.append("Satellite is lagging QQQ by more than 5%; review satellite thesis and position sizing.")
    if active_return is not None and active_return < -0.03:
        flags.append("Portfolio is trailing the benchmark blend by more than 3%; inspect hedge drag and adopter correlation.")

    return MonthlyReviewResult(
        start_date=start.observation_date,
        end_date=end.observation_date,
        portfolio_return=portfolio_return,
        benchmark_return=benchmark_return,
        active_return=active_return,
        max_drawdown=max_drawdown,
        circuit_breaker_triggered=circuit,
        satellite_relative_strength=satellite_relative_strength,
        review_flags=tuple(flags),
    )


def evaluate_adopter_metrics(metrics: AdopterMetrics) -> AdopterScreenResult:
    capex = metrics.it_capex_growth > 0.10
    sgna = metrics.sgna_intensity_change < 0
    margin = metrics.gross_margin_expansion_bps > 50
    score = sum((capex, sgna, margin))
    return AdopterScreenResult(
        ticker=metrics.ticker.upper().strip(),
        passed=score >= 2,
        score=score,
        it_capex_growth_passed=capex,
        sgna_intensity_passed=sgna,
        gross_margin_passed=margin,
    )


def calculate_max_drawdown(values: list[float]) -> float:
    if not values:
        raise ValueError("Values are required for max drawdown.")
    peak = values[0]
    max_drawdown = 0.0
    for value in values:
        if value <= 0:
            raise ValueError("Values must be positive for max drawdown.")
        peak = max(peak, value)
        max_drawdown = min(max_drawdown, (value / peak) - 1.0)
    return max_drawdown


def percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        raise ValueError("Values are required for percentile.")
    if pct <= 0:
        return sorted_values[0]
    if pct >= 1:
        return sorted_values[-1]
    index = (len(sorted_values) - 1) * pct
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return sorted_values[int(index)]
    weight = index - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight
