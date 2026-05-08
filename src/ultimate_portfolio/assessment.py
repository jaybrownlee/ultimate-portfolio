from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .research import (
    BacktestResult,
    PricePoint,
    RebalanceComparison,
    RollingMetricPoint,
    aligned_dates,
    build_price_table,
    normalize_weights,
    rolling_metrics,
    run_strategy_backtest,
    run_weighted_backtest,
)
from .strategy import AnalysisResult, HierarchicalStrategy, Position


@dataclass(frozen=True)
class AssessmentFlag:
    severity: str
    topic: str
    message: str
    suggested_action: str


@dataclass(frozen=True)
class RecommendedHolding:
    bucket: str
    ticker: str
    role: str
    bucket_weight: float
    portfolio_weight: float


@dataclass(frozen=True)
class DailyCheck:
    as_of: date
    analysis: AnalysisResult
    status: str
    flags: tuple[AssessmentFlag, ...]
    recommended_action: str
    satellite_lower_boundary: float
    satellite_upper_boundary: float
    boundary_warning_band: float
    drawdown_warning: float


@dataclass(frozen=True)
class MonthlyAssessment:
    as_of: date
    analysis: AnalysisResult
    backtest: BacktestResult
    recommended_portfolio: tuple[RecommendedHolding, ...]
    rolling_63: tuple[RollingMetricPoint, ...]
    rolling_126: tuple[RollingMetricPoint, ...]
    satellite_relative_strength_63: float | None
    flags: tuple[AssessmentFlag, ...]
    recommended_action: str


@dataclass(frozen=True)
class AssetUniverseItem:
    ticker: str
    role: str
    bucket: str
    replace_for: str
    allowed_min_weight: float
    allowed_max_weight: float
    notes: str = ""

    @property
    def symbol(self) -> str:
        return self.ticker.upper().strip()

    @property
    def replacement_symbol(self) -> str:
        return self.replace_for.upper().strip()


@dataclass(frozen=True)
class CandidateTestResult:
    ticker: str
    replace_for: str
    role: str
    bucket: str
    status: str
    baseline_cagr: float | None
    candidate_cagr: float | None
    cagr_delta: float | None
    baseline_sharpe: float | None
    candidate_sharpe: float | None
    sharpe_delta: float | None
    baseline_max_drawdown: float | None
    candidate_max_drawdown: float | None
    max_drawdown_delta: float | None
    baseline_beta: float | None
    candidate_beta: float | None
    notes: str


@dataclass(frozen=True)
class QuarterlyReview:
    as_of: date
    monthly_assessment: MonthlyAssessment
    rebalance_comparisons: tuple[RebalanceComparison, ...]
    candidate_tests: tuple[CandidateTestResult, ...]
    decision_checklist: tuple[str, ...]


def run_daily_check(
    strategy: HierarchicalStrategy,
    positions: list[Position],
    as_of: date,
    *,
    peak_value: float | None = None,
    boundary_warning_band: float = 0.005,
    drawdown_warning: float = 0.18,
) -> DailyCheck:
    if boundary_warning_band < 0:
        raise ValueError("Boundary warning band cannot be negative.")
    if drawdown_warning <= 0:
        raise ValueError("Drawdown warning must be positive.")
    if drawdown_warning >= strategy.circuit_breaker_drawdown:
        raise ValueError("Drawdown warning should be below the circuit-breaker drawdown.")

    analysis = strategy.analyze(positions, as_of, peak_value=peak_value)
    satellite_target = next(
        bucket.target_weight
        for bucket in strategy.buckets
        if bucket.name == strategy.satellite_bucket
    )
    lower_boundary = satellite_target - strategy.drift_threshold
    upper_boundary = satellite_target + strategy.drift_threshold
    flags = build_daily_check_flags(
        analysis,
        lower_boundary=lower_boundary,
        upper_boundary=upper_boundary,
        boundary_warning_band=boundary_warning_band,
        drawdown_warning=drawdown_warning,
        peak_value=peak_value,
    )
    status = daily_check_status(flags)
    return DailyCheck(
        as_of=as_of,
        analysis=analysis,
        status=status,
        flags=flags,
        recommended_action=daily_check_action(status),
        satellite_lower_boundary=lower_boundary,
        satellite_upper_boundary=upper_boundary,
        boundary_warning_band=boundary_warning_band,
        drawdown_warning=drawdown_warning,
    )


def build_daily_check_flags(
    analysis: AnalysisResult,
    *,
    lower_boundary: float,
    upper_boundary: float,
    boundary_warning_band: float,
    drawdown_warning: float,
    peak_value: float | None,
) -> tuple[AssessmentFlag, ...]:
    flags: list[AssessmentFlag] = []

    if analysis.circuit_breaker_triggered:
        flags.append(
            AssessmentFlag(
                "red",
                "circuit_breaker",
                "Total portfolio drawdown breached the 20% uncle point.",
                "Move satellite exposure to SGOV and run a structural hardware-cycle review before re-risking.",
            )
        )
    elif analysis.current_drawdown is not None and analysis.current_drawdown <= -drawdown_warning:
        flags.append(
            AssessmentFlag(
                "yellow",
                "drawdown_warning",
                "Total portfolio drawdown is near the 20% uncle point.",
                "Avoid adding risk and prepare the circuit-breaker review packet.",
            )
        )

    if analysis.boundary_triggered:
        flags.append(
            AssessmentFlag(
                "red",
                "master_boundary",
                "Satellite exposure breached the 15%/25% master boundary.",
                "Run the boundary rebalance process back to the 80/20 master allocation.",
            )
        )
    elif boundary_warning_band > 0:
        near_lower = analysis.satellite_weight <= lower_boundary + boundary_warning_band
        near_upper = analysis.satellite_weight >= upper_boundary - boundary_warning_band
        if near_lower or near_upper:
            flags.append(
                AssessmentFlag(
                    "yellow",
                    "master_boundary_warning",
                    "Satellite exposure is close to the 15%/25% master boundary.",
                    "Monitor drift, but do not rebalance across the boundary until the trigger actually fires.",
                )
            )

    if analysis.calendar_sweep_due:
        flags.append(
            AssessmentFlag(
                "yellow",
                "calendar_sweep",
                "The quarterly internal sweep is due.",
                "Run the quarterly review workflow rather than making ad hoc daily changes.",
            )
        )

    if peak_value is None:
        flags.append(
            AssessmentFlag(
                "info",
                "peak_value_missing",
                "Peak account value was not supplied, so live uncle-point monitoring is incomplete.",
                "Provide --peak-value when running against a real account.",
            )
        )

    if not any(flag.severity in {"red", "yellow"} for flag in flags):
        flags.append(
            AssessmentFlag(
                "green",
                "process",
                "No daily rule-based trigger fired.",
                "Hold the strategy and continue monitoring.",
            )
        )
    return tuple(flags)


def daily_check_status(flags: tuple[AssessmentFlag, ...]) -> str:
    severities = {flag.severity for flag in flags}
    if "red" in severities:
        return "action_required"
    if "yellow" in severities:
        return "watch"
    return "clear"


def daily_check_action(status: str) -> str:
    if status == "action_required":
        return "Action required: follow the rule-based rebalance or circuit-breaker SOP before making discretionary changes."
    if status == "watch":
        return "Watch: monitor the flagged issue, but do not make discretionary strategy changes from a daily check alone."
    return "Clear: no daily trigger requires action."


def run_monthly_assessment(
    strategy: HierarchicalStrategy,
    positions: list[Position],
    price_points: list[PricePoint],
    as_of: date,
    *,
    peak_value: float | None = None,
    benchmark_weights: dict[str, float] | None = None,
    initial_value: float = 100000.0,
    annualization_periods: int = 252,
    risk_free_rate: float = 0.0,
    force_sweep: bool = False,
    mode: str = "actual_current_portfolio",
) -> MonthlyAssessment:
    analysis = strategy.analyze(positions, as_of, force_sweep=force_sweep, peak_value=peak_value)
    backtest = run_strategy_backtest(
        strategy,
        price_points,
        initial_value=initial_value,
        rebalance_frequency="quarterly",
        annualization_periods=annualization_periods,
        risk_free_rate=risk_free_rate,
        benchmark_weights=benchmark_weights,
        mode=mode,
    )
    rolling_63 = rolling_metrics(
        backtest.portfolio_values,
        benchmark_values=backtest.benchmark_values,
        window=63,
        annualization_periods=annualization_periods,
        risk_free_rate=risk_free_rate,
    )
    rolling_126 = rolling_metrics(
        backtest.portfolio_values,
        benchmark_values=backtest.benchmark_values,
        window=126,
        annualization_periods=annualization_periods,
        risk_free_rate=risk_free_rate,
    )
    satellite_strength = calculate_satellite_relative_strength(
        strategy,
        price_points,
        benchmark_symbol="QQQ",
        window=63,
        annualization_periods=annualization_periods,
    )
    flags = build_assessment_flags(analysis, backtest, rolling_63, satellite_strength)
    return MonthlyAssessment(
        as_of=as_of,
        analysis=analysis,
        backtest=backtest,
        recommended_portfolio=build_recommended_portfolio(strategy),
        rolling_63=rolling_63,
        rolling_126=rolling_126,
        satellite_relative_strength_63=satellite_strength,
        flags=flags,
        recommended_action=recommended_action(flags),
    )


DEFAULT_HOLDING_ROLES = {
    "COWZ": "Free cash flow / anti-hype equity anchor",
    "WMT": "AI adopter basket: retail and logistics enhancer",
    "JPM": "AI adopter basket: financial services enhancer",
    "DE": "AI adopter basket: industrial automation enhancer",
    "DBMF": "Managed futures / trend-following shock absorber",
    "SGOV": "0-3 month T-bill liquidity and dry powder",
    "TLT": "Long-duration recession and deflation hedge",
    "GLDM": "Optional stagflation overlay",
    "SPRX": "High-conviction semiconductor and industrial hardware",
    "ARKQ": "Embodied AI, automation, and energy storage",
    "ELFY": "Power infrastructure and grid cooling",
    "BAI": "Broad global AI technology stack",
}


def build_recommended_portfolio(strategy: HierarchicalStrategy) -> tuple[RecommendedHolding, ...]:
    holdings: list[RecommendedHolding] = []
    for bucket in strategy.buckets:
        for holding in bucket.holdings:
            holdings.append(
                RecommendedHolding(
                    bucket=bucket.name,
                    ticker=holding.symbol,
                    role=DEFAULT_HOLDING_ROLES.get(holding.symbol, "Strategy holding"),
                    bucket_weight=holding.bucket_weight,
                    portfolio_weight=bucket.target_weight * holding.bucket_weight,
                )
            )
    return tuple(holdings)


def calculate_satellite_relative_strength(
    strategy: HierarchicalStrategy,
    price_points: list[PricePoint],
    *,
    benchmark_symbol: str = "QQQ",
    window: int = 63,
    annualization_periods: int = 252,
) -> float | None:
    satellite_weights = {
        symbol: weight
        for symbol, weight in strategy.total_target_weights().items()
        if strategy.bucket_for_symbol(symbol) == strategy.satellite_bucket
    }
    try:
        result = run_weighted_backtest(
            price_points,
            satellite_weights,
            benchmark_weights={benchmark_symbol: 1.0},
            initial_value=100000.0,
            rebalance_frequency="quarterly",
            annualization_periods=annualization_periods,
        )
    except ValueError:
        return None
    if len(result.portfolio_values) <= window or not result.benchmark_values:
        return None
    satellite_return = (result.portfolio_values[-1].value / result.portfolio_values[-1 - window].value) - 1.0
    benchmark_return = (result.benchmark_values[-1].value / result.benchmark_values[-1 - window].value) - 1.0
    return satellite_return - benchmark_return


def build_assessment_flags(
    analysis: AnalysisResult,
    backtest: BacktestResult,
    rolling_63: tuple[RollingMetricPoint, ...],
    satellite_relative_strength_63: float | None,
) -> tuple[AssessmentFlag, ...]:
    flags: list[AssessmentFlag] = []
    metrics = backtest.portfolio_metrics
    relative = backtest.relative_metrics
    latest_rolling = rolling_63[-1] if rolling_63 else None

    if analysis.circuit_breaker_triggered:
        flags.append(
            AssessmentFlag(
                "red",
                "circuit_breaker",
                "The portfolio drawdown breached the 20% uncle point.",
                "Move satellite exposure to SGOV and run a structural hardware-cycle review before re-risking.",
            )
        )
    elif analysis.current_drawdown is not None and analysis.current_drawdown <= -0.15:
        flags.append(
            AssessmentFlag(
                "yellow",
                "drawdown",
                "The portfolio is within 5 percentage points of the uncle point.",
                "Review hedge behavior and avoid adding satellite risk until drawdown stabilizes.",
            )
        )

    if analysis.boundary_triggered:
        flags.append(
            AssessmentFlag(
                "red",
                "master_boundary",
                "The satellite bucket breached the 15%/25% master boundary.",
                "Run the boundary rebalance back to 80/20 unless there is a documented execution constraint.",
            )
        )

    if analysis.calendar_sweep_due:
        flags.append(
            AssessmentFlag(
                "yellow",
                "calendar_sweep",
                "The quarterly internal sweep is due.",
                "Realign holdings inside each bucket without crossing the 80/20 boundary unless the master trigger fired.",
            )
        )

    if latest_rolling and latest_rolling.sharpe_ratio is not None and latest_rolling.sharpe_ratio < 0:
        flags.append(
            AssessmentFlag(
                "yellow",
                "rolling_sharpe",
                "The latest 63-period Sharpe is below zero.",
                "Investigate whether the weakness is broad market noise, hedge drag, or thesis deterioration.",
            )
        )

    if satellite_relative_strength_63 is not None and satellite_relative_strength_63 <= -0.10:
        flags.append(
            AssessmentFlag(
                "red",
                "satellite_relative_strength",
                "Satellite exposure is lagging QQQ by more than 10% over the latest 63 periods.",
                "Review the satellite thesis and consider whether position concentration should be reduced.",
            )
        )
    elif satellite_relative_strength_63 is not None and satellite_relative_strength_63 <= -0.05:
        flags.append(
            AssessmentFlag(
                "yellow",
                "satellite_relative_strength",
                "Satellite exposure is lagging QQQ by more than 5% over the latest 63 periods.",
                "Add the satellite sleeve to the quarterly watch list.",
            )
        )

    if relative and relative.correlation is not None and relative.beta is not None:
        if relative.correlation >= 0.90 and relative.beta >= 0.95:
            flags.append(
                AssessmentFlag(
                    "yellow",
                    "benchmark_coupling",
                    "Portfolio beta and correlation are both high versus the benchmark blend.",
                    "Check whether the hedge sleeve is still diversifying or merely diluting equity beta.",
                )
            )

    if metrics.max_drawdown <= -0.18 and not any(flag.topic == "circuit_breaker" for flag in flags):
        flags.append(
            AssessmentFlag(
                "yellow",
                "historical_drawdown",
                "Backtest max drawdown is close to the 20% uncle point.",
                "Use proxy-regime evidence and stress tests before increasing risk.",
            )
        )

    if not flags:
        flags.append(
            AssessmentFlag(
                "green",
                "process",
                "No rule-based action flags were triggered.",
                "Hold the strategy and continue monthly monitoring.",
            )
        )
    return tuple(flags)


def recommended_action(flags: tuple[AssessmentFlag, ...]) -> str:
    severities = {flag.severity for flag in flags}
    if "red" in severities:
        return "Action required: follow the rule-based rebalance or circuit-breaker process before making discretionary changes."
    if "yellow" in severities:
        return "Watch list: document the issue, avoid discretionary trades, and revisit during the next quarterly review."
    return "Hold: no portfolio changes recommended from the monthly process."


def run_candidate_tests(
    strategy: HierarchicalStrategy,
    price_points: list[PricePoint],
    candidates: list[AssetUniverseItem],
    *,
    benchmark_weights: dict[str, float] | None = None,
    initial_value: float = 100000.0,
    annualization_periods: int = 252,
    risk_free_rate: float = 0.0,
    max_candidates: int | None = None,
) -> tuple[CandidateTestResult, ...]:
    base_weights = strategy.total_target_weights()
    tested: list[CandidateTestResult] = []
    for item in candidates:
        if max_candidates is not None and len(tested) >= max_candidates:
            break
        if not item.replacement_symbol or item.replacement_symbol == item.symbol:
            continue
        if item.replacement_symbol not in base_weights:
            tested.append(no_data_candidate(item, f"{item.replacement_symbol} is not a current strategy holding."))
            continue
        candidate_weights = replacement_weights(base_weights, item.replacement_symbol, item.symbol)
        try:
            shared_points = complete_price_points_for_symbols(
                price_points,
                set(base_weights) | {item.symbol} | set(benchmark_weights or {}),
            )
            baseline = run_strategy_backtest(
                strategy,
                shared_points,
                initial_value=initial_value,
                rebalance_frequency="quarterly",
                annualization_periods=annualization_periods,
                risk_free_rate=risk_free_rate,
                benchmark_weights=benchmark_weights,
            )
            candidate = run_weighted_backtest(
                shared_points,
                candidate_weights,
                benchmark_weights=benchmark_weights,
                initial_value=initial_value,
                rebalance_frequency="quarterly",
                annualization_periods=annualization_periods,
                risk_free_rate=risk_free_rate,
                mode=f"candidate_{item.symbol}_for_{item.replacement_symbol}",
            )
        except ValueError as exc:
            tested.append(no_data_candidate(item, str(exc)))
            continue
        tested.append(candidate_result(item, baseline, candidate))
    return tuple(tested)


def complete_price_points_for_symbols(price_points: list[PricePoint], required_symbols: set[str]) -> list[PricePoint]:
    normalized = {symbol.upper().strip() for symbol in required_symbols if symbol.strip()}
    price_table = build_price_table(price_points)
    valid_dates, _ = aligned_dates(price_table, normalized)
    if len(valid_dates) < 2:
        raise ValueError("At least two complete price dates are required for the candidate and baseline.")
    valid = set(valid_dates)
    return [point for point in price_points if point.observation_date in valid and point.symbol in normalized]


def replacement_weights(base_weights: dict[str, float], replace_for: str, candidate: str) -> dict[str, float]:
    weights = dict(base_weights)
    replacement_weight = weights.pop(replace_for)
    weights[candidate] = weights.get(candidate, 0.0) + replacement_weight
    return normalize_weights(weights)


def no_data_candidate(item: AssetUniverseItem, notes: str) -> CandidateTestResult:
    return CandidateTestResult(
        ticker=item.symbol,
        replace_for=item.replacement_symbol,
        role=item.role,
        bucket=item.bucket,
        status="no_data",
        baseline_cagr=None,
        candidate_cagr=None,
        cagr_delta=None,
        baseline_sharpe=None,
        candidate_sharpe=None,
        sharpe_delta=None,
        baseline_max_drawdown=None,
        candidate_max_drawdown=None,
        max_drawdown_delta=None,
        baseline_beta=None,
        candidate_beta=None,
        notes=notes,
    )


def candidate_result(item: AssetUniverseItem, baseline: BacktestResult, candidate: BacktestResult) -> CandidateTestResult:
    baseline_metrics = baseline.portfolio_metrics
    candidate_metrics = candidate.portfolio_metrics
    baseline_sharpe = baseline_metrics.sharpe_ratio
    candidate_sharpe = candidate_metrics.sharpe_ratio
    sharpe_delta = None if baseline_sharpe is None or candidate_sharpe is None else candidate_sharpe - baseline_sharpe
    mdd_delta = candidate_metrics.max_drawdown - baseline_metrics.max_drawdown
    cagr_delta = candidate_metrics.cagr - baseline_metrics.cagr
    baseline_beta = None if baseline.relative_metrics is None else baseline.relative_metrics.beta
    candidate_beta = None if candidate.relative_metrics is None else candidate.relative_metrics.beta
    status = classify_candidate(cagr_delta, sharpe_delta, mdd_delta)
    notes = "Same-role replacement test; review liquidity, taxes, and thesis fit before acting."
    return CandidateTestResult(
        ticker=item.symbol,
        replace_for=item.replacement_symbol,
        role=item.role,
        bucket=item.bucket,
        status=status,
        baseline_cagr=baseline_metrics.cagr,
        candidate_cagr=candidate_metrics.cagr,
        cagr_delta=cagr_delta,
        baseline_sharpe=baseline_sharpe,
        candidate_sharpe=candidate_sharpe,
        sharpe_delta=sharpe_delta,
        baseline_max_drawdown=baseline_metrics.max_drawdown,
        candidate_max_drawdown=candidate_metrics.max_drawdown,
        max_drawdown_delta=mdd_delta,
        baseline_beta=baseline_beta,
        candidate_beta=candidate_beta,
        notes=notes,
    )


def classify_candidate(cagr_delta: float, sharpe_delta: float | None, max_drawdown_delta: float) -> str:
    if sharpe_delta is not None and sharpe_delta >= 0 and max_drawdown_delta >= -0.01 and cagr_delta >= -0.005:
        return "pass"
    if (sharpe_delta is not None and sharpe_delta > 0) or max_drawdown_delta > 0 or cagr_delta > 0:
        return "watch"
    return "reject"


def run_quarterly_review(
    strategy: HierarchicalStrategy,
    positions: list[Position],
    price_points: list[PricePoint],
    candidates: list[AssetUniverseItem],
    as_of: date,
    *,
    peak_value: float | None = None,
    benchmark_weights: dict[str, float] | None = None,
    initial_value: float = 100000.0,
    annualization_periods: int = 252,
    risk_free_rate: float = 0.0,
    mode: str = "actual_current_portfolio",
    max_candidates: int | None = 20,
) -> QuarterlyReview:
    monthly = run_monthly_assessment(
        strategy,
        positions,
        price_points,
        as_of,
        peak_value=peak_value,
        benchmark_weights=benchmark_weights,
        initial_value=initial_value,
        annualization_periods=annualization_periods,
        risk_free_rate=risk_free_rate,
        force_sweep=True,
        mode=mode,
    )
    comparisons = tuple()
    try:
        from .research import compare_rebalance_frequencies

        comparisons = compare_rebalance_frequencies(
            strategy,
            price_points,
            benchmark_weights=benchmark_weights,
            initial_value=initial_value,
            annualization_periods=annualization_periods,
            risk_free_rate=risk_free_rate,
        )
    except ValueError:
        comparisons = tuple()
    candidate_tests = run_candidate_tests(
        strategy,
        price_points,
        candidates,
        benchmark_weights=benchmark_weights,
        initial_value=initial_value,
        annualization_periods=annualization_periods,
        risk_free_rate=risk_free_rate,
        max_candidates=max_candidates,
    )
    return QuarterlyReview(
        as_of=as_of,
        monthly_assessment=monthly,
        rebalance_comparisons=comparisons,
        candidate_tests=candidate_tests,
        decision_checklist=DEFAULT_DECISION_CHECKLIST,
    )


DEFAULT_DECISION_CHECKLIST = (
    "Did any rule-based trigger fire, or is this a discretionary change?",
    "Which evidence mode supports the decision: actual-current, proxy-regime, or thesis-inception?",
    "Does the change improve the same role without breaking the 80/20 hierarchy?",
    "Did Sharpe, drawdown, beta, correlation, and CVaR improve or at least remain acceptable?",
    "Are taxes, spreads, liquidity, and position sizing acceptable?",
    "What rejected alternative should be recorded in the decision log?",
)
