from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .research import (
    BacktestResult,
    PricePoint,
    RebalanceComparison,
    RollingMetricPoint,
    ValuePoint,
    aligned_dates,
    build_price_table,
    calculate_performance_metrics,
    calculate_relative_metrics,
    correlation,
    normalize_weights,
    periodic_returns,
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
class CandidateScreenRow:
    ticker: str
    role: str
    bucket: str
    replace_for: str
    candidate_type: str
    priority: str
    latest_price_date: date | None
    observations: int
    total_return: float | None
    cagr: float | None
    sharpe_ratio: float | None
    max_drawdown: float | None
    current_drawdown: float | None
    return_63: float | None
    return_126: float | None
    return_252: float | None
    vol_adjusted_momentum_126: float | None
    above_200_day_average: bool | None
    correlation_to_incumbent: float | None
    correlation_to_benchmark: float | None
    beta_to_benchmark: float | None
    replacement_status: str | None
    cagr_delta: float | None
    sharpe_delta: float | None
    max_drawdown_delta: float | None
    reason_codes: tuple[str, ...]
    notes: str


@dataclass(frozen=True)
class CandidateRoleSummary:
    role: str
    bucket: str
    incumbents: tuple[str, ...]
    incumbent_priority: str
    best_challenger: str | None
    best_challenger_priority: str | None
    recommended_action: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class CandidateScreenReport:
    as_of: date | None
    benchmark_symbol: str
    windows: tuple[int, ...]
    summaries: tuple[CandidateRoleSummary, ...]
    rows: tuple[CandidateScreenRow, ...]


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


def run_candidate_screen(
    strategy: HierarchicalStrategy,
    price_points: list[PricePoint],
    candidates: list[AssetUniverseItem],
    *,
    benchmark_symbol: str = "QQQ",
    benchmark_weights: dict[str, float] | None = None,
    initial_value: float = 100000.0,
    annualization_periods: int = 252,
    risk_free_rate: float = 0.0,
    windows: tuple[int, ...] = (63, 126, 252),
    max_candidates: int | None = None,
) -> CandidateScreenReport:
    if any(window <= 0 for window in windows):
        raise ValueError("Screen windows must be positive.")
    normalized_benchmark = benchmark_symbol.upper().strip()
    screened_items = candidate_items_for_screen(candidates, max_candidates)
    replacement_tests = {
        (result.ticker, result.replace_for): result
        for result in run_candidate_tests(
            strategy,
            price_points,
            [item for item in screened_items if item.replacement_symbol],
            benchmark_weights=benchmark_weights,
            initial_value=initial_value,
            annualization_periods=annualization_periods,
            risk_free_rate=risk_free_rate,
            max_candidates=None,
        )
    }
    price_table = build_price_table(price_points)
    rows = tuple(
        build_candidate_screen_row(
            price_table,
            item,
            benchmark_symbol=normalized_benchmark,
            annualization_periods=annualization_periods,
            risk_free_rate=risk_free_rate,
            windows=windows,
            replacement_result=replacement_tests.get((item.symbol, item.replacement_symbol)),
        )
        for item in screened_items
    )
    latest_dates = [row.latest_price_date for row in rows if row.latest_price_date is not None]
    return CandidateScreenReport(
        as_of=max(latest_dates) if latest_dates else None,
        benchmark_symbol=normalized_benchmark,
        windows=tuple(windows),
        summaries=build_role_summaries(rows),
        rows=rows,
    )


def candidate_items_for_screen(
    candidates: list[AssetUniverseItem],
    max_candidates: int | None,
) -> list[AssetUniverseItem]:
    if max_candidates is None:
        return list(candidates)
    if max_candidates < 0:
        raise ValueError("Maximum candidates cannot be negative.")
    incumbents = [item for item in candidates if not item.replacement_symbol]
    challengers = [item for item in candidates if item.replacement_symbol]
    return incumbents + challengers[:max_candidates]


def build_candidate_screen_row(
    price_table: dict[date, dict[str, float]],
    item: AssetUniverseItem,
    *,
    benchmark_symbol: str,
    annualization_periods: int,
    risk_free_rate: float,
    windows: tuple[int, ...],
    replacement_result: CandidateTestResult | None,
) -> CandidateScreenRow:
    symbol = item.symbol
    candidate_type = "incumbent" if not item.replacement_symbol else "challenger"
    valid_dates = [day for day in sorted(price_table) if symbol in price_table[day]]
    if len(valid_dates) < 2:
        return no_data_screen_row(item, candidate_type, replacement_result, "Insufficient price history for screening.")

    values = tuple(ValuePoint(day, price_table[day][symbol]) for day in valid_dates)
    metrics = calculate_performance_metrics(
        values,
        annualization_periods=annualization_periods,
        risk_free_rate=risk_free_rate,
    )
    prices = [point.value for point in values]
    window_returns = {window: window_return(values, window) for window in windows}
    current_drawdown = (prices[-1] / max(prices)) - 1.0
    vol_adjusted_126 = vol_adjusted_momentum(values, 126, annualization_periods)
    above_200 = above_moving_average(values, 200)
    incumbent_corr = paired_return_correlation(price_table, symbol, item.replacement_symbol)
    benchmark_relative = paired_relative_metrics(price_table, symbol, benchmark_symbol, annualization_periods)
    benchmark_corr = None if benchmark_relative is None else benchmark_relative.correlation
    benchmark_beta = None if benchmark_relative is None else benchmark_relative.beta
    reason_codes = screen_reason_codes(
        candidate_type=candidate_type,
        role=item.role,
        replacement_result=replacement_result,
        return_126=window_returns.get(126),
        above_200=above_200,
        current_drawdown=current_drawdown,
        correlation_to_incumbent=incumbent_corr,
        beta_to_benchmark=benchmark_beta,
    )
    priority = classify_screen_priority(
        role=item.role,
        candidate_type=candidate_type,
        replacement_result=replacement_result,
        return_126=window_returns.get(126),
        above_200=above_200,
        current_drawdown=current_drawdown,
        correlation_to_incumbent=incumbent_corr,
        beta_to_benchmark=benchmark_beta,
    )
    return CandidateScreenRow(
        ticker=symbol,
        role=item.role,
        bucket=item.bucket,
        replace_for=item.replacement_symbol,
        candidate_type=candidate_type,
        priority=priority,
        latest_price_date=values[-1].observation_date,
        observations=len(values),
        total_return=metrics.total_return,
        cagr=metrics.cagr,
        sharpe_ratio=metrics.sharpe_ratio,
        max_drawdown=metrics.max_drawdown,
        current_drawdown=current_drawdown,
        return_63=window_returns.get(63),
        return_126=window_returns.get(126),
        return_252=window_returns.get(252),
        vol_adjusted_momentum_126=vol_adjusted_126,
        above_200_day_average=above_200,
        correlation_to_incumbent=incumbent_corr,
        correlation_to_benchmark=benchmark_corr,
        beta_to_benchmark=benchmark_beta,
        replacement_status=None if replacement_result is None else replacement_result.status,
        cagr_delta=None if replacement_result is None else replacement_result.cagr_delta,
        sharpe_delta=None if replacement_result is None else replacement_result.sharpe_delta,
        max_drawdown_delta=None if replacement_result is None else replacement_result.max_drawdown_delta,
        reason_codes=reason_codes,
        notes=screen_notes(candidate_type, replacement_result, item.notes),
    )


def no_data_screen_row(
    item: AssetUniverseItem,
    candidate_type: str,
    replacement_result: CandidateTestResult | None,
    notes: str,
) -> CandidateScreenRow:
    return CandidateScreenRow(
        ticker=item.symbol,
        role=item.role,
        bucket=item.bucket,
        replace_for=item.replacement_symbol,
        candidate_type=candidate_type,
        priority="no_data",
        latest_price_date=None,
        observations=0,
        total_return=None,
        cagr=None,
        sharpe_ratio=None,
        max_drawdown=None,
        current_drawdown=None,
        return_63=None,
        return_126=None,
        return_252=None,
        vol_adjusted_momentum_126=None,
        above_200_day_average=None,
        correlation_to_incumbent=None,
        correlation_to_benchmark=None,
        beta_to_benchmark=None,
        replacement_status=None if replacement_result is None else replacement_result.status,
        cagr_delta=None if replacement_result is None else replacement_result.cagr_delta,
        sharpe_delta=None if replacement_result is None else replacement_result.sharpe_delta,
        max_drawdown_delta=None if replacement_result is None else replacement_result.max_drawdown_delta,
        reason_codes=("insufficient_price_history",),
        notes=notes,
    )


def window_return(values: tuple[ValuePoint, ...], window: int) -> float | None:
    if len(values) <= window:
        return None
    return (values[-1].value / values[-1 - window].value) - 1.0


def vol_adjusted_momentum(
    values: tuple[ValuePoint, ...],
    window: int,
    annualization_periods: int,
) -> float | None:
    if len(values) <= window:
        return None
    returns = periodic_returns([point.value for point in values[-window - 1:]])
    volatility = sample_volatility(returns, annualization_periods)
    if volatility <= 0:
        return None
    return ((values[-1].value / values[-1 - window].value) - 1.0) / volatility


def sample_volatility(returns: list[float], annualization_periods: int) -> float:
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    variance = sum((item - mean) ** 2 for item in returns) / (len(returns) - 1)
    return variance ** 0.5 * (annualization_periods ** 0.5)


def above_moving_average(values: tuple[ValuePoint, ...], window: int) -> bool | None:
    if len(values) < window:
        return None
    average = sum(point.value for point in values[-window:]) / window
    return values[-1].value > average


def paired_return_correlation(
    price_table: dict[date, dict[str, float]],
    left_symbol: str,
    right_symbol: str,
) -> float | None:
    if not right_symbol:
        return None
    valid_dates, _ = aligned_dates(price_table, {left_symbol, right_symbol})
    if len(valid_dates) < 3:
        return None
    left_returns = [
        (price_table[current][left_symbol] / price_table[previous][left_symbol]) - 1.0
        for previous, current in zip(valid_dates, valid_dates[1:])
    ]
    right_returns = [
        (price_table[current][right_symbol] / price_table[previous][right_symbol]) - 1.0
        for previous, current in zip(valid_dates, valid_dates[1:])
    ]
    return correlation(left_returns, right_returns)


def paired_relative_metrics(
    price_table: dict[date, dict[str, float]],
    symbol: str,
    benchmark_symbol: str,
    annualization_periods: int,
):
    if not benchmark_symbol:
        return None
    valid_dates, _ = aligned_dates(price_table, {symbol, benchmark_symbol})
    if len(valid_dates) < 3:
        return None
    symbol_values = tuple(ValuePoint(day, price_table[day][symbol]) for day in valid_dates)
    benchmark_values = tuple(ValuePoint(day, price_table[day][benchmark_symbol]) for day in valid_dates)
    return calculate_relative_metrics(symbol_values, benchmark_values, annualization_periods=annualization_periods)


def screen_reason_codes(
    *,
    candidate_type: str,
    role: str,
    replacement_result: CandidateTestResult | None,
    return_126: float | None,
    above_200: bool | None,
    current_drawdown: float,
    correlation_to_incumbent: float | None,
    beta_to_benchmark: float | None,
) -> tuple[str, ...]:
    codes: list[str] = []

    if candidate_type == "incumbent":
        codes.append("current_champion")
    elif replacement_result is None:
        codes.append("no_replacement_test")
    else:
        codes.append(f"replacement_{replacement_result.status}")
        if replacement_result.sharpe_delta is not None:
            if replacement_result.sharpe_delta > 0:
                codes.append("better_sharpe")
            elif replacement_result.sharpe_delta < 0:
                codes.append("weaker_sharpe")
        if replacement_result.max_drawdown_delta is not None:
            if replacement_result.max_drawdown_delta > 0:
                codes.append("better_drawdown")
            elif replacement_result.max_drawdown_delta < 0:
                codes.append("worse_drawdown")
        if replacement_result.cagr_delta is not None:
            if replacement_result.cagr_delta > 0:
                codes.append("better_cagr")
            elif replacement_result.cagr_delta < 0:
                codes.append("lower_cagr")

    if return_126 is None:
        codes.append("insufficient_126d_history")
    elif return_126 >= 0:
        codes.append("positive_126d_momentum")
    else:
        codes.append("negative_126d_momentum")

    if above_200 is None:
        codes.append("insufficient_trend_history")
    elif above_200:
        codes.append("above_200d_average")
    else:
        codes.append("below_200d_average")

    if current_drawdown <= -0.20:
        codes.append("deep_current_drawdown")

    if correlation_to_incumbent is not None:
        if correlation_to_incumbent <= 0.60:
            codes.append("low_incumbent_correlation")
        elif correlation_to_incumbent >= 0.85:
            codes.append("high_incumbent_correlation")

    if beta_to_benchmark is not None:
        if beta_to_benchmark <= 0.25:
            codes.append("low_benchmark_beta")
        elif beta_to_benchmark >= 1.20:
            codes.append("high_benchmark_beta")

    role_group = candidate_role_group(role)
    if role_group == "cash" and current_drawdown > -0.005:
        codes.append("capital_stability")
    if role_group == "hedge" and beta_to_benchmark is not None and beta_to_benchmark <= 0.35:
        codes.append("hedge_like_beta")
    if role_group == "satellite" and beta_to_benchmark is not None and beta_to_benchmark >= 1.0:
        codes.append("satellite_beta")

    return tuple(codes)


def classify_screen_priority(
    *,
    role: str,
    candidate_type: str,
    replacement_result: CandidateTestResult | None,
    return_126: float | None,
    above_200: bool | None,
    current_drawdown: float,
    correlation_to_incumbent: float | None,
    beta_to_benchmark: float | None,
) -> str:
    if candidate_type == "incumbent":
        if current_drawdown <= -0.20 or above_200 is False:
            return "monitor"
        return "incumbent"
    if replacement_result is None or replacement_result.status == "no_data":
        return "no_data"
    if replacement_result.status == "reject":
        return "reject"

    trend_ok = above_200 is not False and (return_126 is None or return_126 >= 0)
    if not trend_ok or current_drawdown <= -0.20:
        return "watch" if replacement_result.status == "pass" else "reject"

    role_group = candidate_role_group(role)
    sharpe_delta = replacement_result.sharpe_delta or 0.0
    drawdown_delta = replacement_result.max_drawdown_delta or 0.0
    cagr_delta = replacement_result.cagr_delta or 0.0

    if role_group == "cash":
        if replacement_result.status == "pass" and current_drawdown > -0.005 and drawdown_delta >= -0.001:
            return "high"
        return "watch" if replacement_result.status in {"pass", "watch"} else "reject"

    if role_group == "hedge":
        differentiated = correlation_to_incumbent is None or correlation_to_incumbent <= 0.75
        low_beta = beta_to_benchmark is None or beta_to_benchmark <= 0.35
        if replacement_result.status == "pass" and differentiated and low_beta and (sharpe_delta > 0 or drawdown_delta > 0):
            return "high"
        return "watch" if replacement_result.status in {"pass", "watch"} else "reject"

    if role_group == "core_equity":
        not_too_hot = beta_to_benchmark is None or beta_to_benchmark <= 0.95
        if replacement_result.status == "pass" and not_too_hot and cagr_delta >= -0.01 and (sharpe_delta > 0 or drawdown_delta > 0.005):
            return "high"
        return "watch" if replacement_result.status in {"pass", "watch"} else "reject"

    if role_group == "satellite":
        if replacement_result.status == "pass" and (sharpe_delta >= 0 or cagr_delta > 0):
            return "high"
        return "watch" if replacement_result.status in {"pass", "watch"} else "reject"

    if replacement_result.status == "pass":
        return "high"
    if replacement_result.status in {"pass", "watch"}:
        return "watch"
    return "reject"


def candidate_role_group(role: str) -> str:
    normalized = role.lower().strip()
    if normalized in {"t_bill_liquidity"}:
        return "cash"
    if normalized in {"managed_futures", "duration_hedge", "stagflation_overlay"}:
        return "hedge"
    if normalized in {"fcf_value_anchor", "dividend_quality_core", "ai_adopter"}:
        return "core_equity"
    if normalized in {"semis_hardware", "robotics_embodied_ai", "power_grid_cooling", "broad_ai_stack"}:
        return "satellite"
    return "general"


def screen_notes(
    candidate_type: str,
    replacement_result: CandidateTestResult | None,
    base_notes: str,
) -> str:
    if candidate_type == "incumbent":
        return base_notes or "Current role champion; monitor against challengers."
    if replacement_result is None:
        return base_notes or "Candidate needs a same-role replacement test."
    if replacement_result.status == "pass":
        return "Candidate passed replacement math; require role, liquidity, and persistence review."
    if replacement_result.status == "watch":
        return "Candidate improved at least one dimension but has tradeoffs."
    if replacement_result.status == "reject":
        return "Candidate failed the current replacement screen."
    return replacement_result.notes


def build_role_summaries(rows: tuple[CandidateScreenRow, ...]) -> tuple[CandidateRoleSummary, ...]:
    grouped: dict[str, list[CandidateScreenRow]] = {}
    role_order: list[str] = []
    for row in rows:
        if row.role not in grouped:
            grouped[row.role] = []
            role_order.append(row.role)
        grouped[row.role].append(row)

    summaries: list[CandidateRoleSummary] = []
    for role in role_order:
        role_rows = grouped[role]
        incumbents = [row for row in role_rows if row.candidate_type == "incumbent"]
        challengers = [row for row in role_rows if row.candidate_type == "challenger"]
        best = best_challenger(challengers)
        incumbent_priority = summarize_incumbent_priority(incumbents)
        summaries.append(
            CandidateRoleSummary(
                role=role,
                bucket=role_rows[0].bucket,
                incumbents=tuple(row.ticker for row in incumbents),
                incumbent_priority=incumbent_priority,
                best_challenger=None if best is None else best.ticker,
                best_challenger_priority=None if best is None else best.priority,
                recommended_action=summary_action(incumbent_priority, best),
                reason_codes=summary_reason_codes(incumbents, best),
            )
        )
    return tuple(summaries)


def best_challenger(rows: list[CandidateScreenRow]) -> CandidateScreenRow | None:
    if not rows:
        return None
    return sorted(rows, key=screen_row_sort_key, reverse=True)[0]


def screen_row_sort_key(row: CandidateScreenRow) -> tuple[float, float, float, float, float]:
    priority_rank = {"high": 4.0, "watch": 3.0, "reject": 1.0, "no_data": 0.0}.get(row.priority, 0.0)
    return (
        priority_rank,
        row.sharpe_delta if row.sharpe_delta is not None else -99.0,
        row.max_drawdown_delta if row.max_drawdown_delta is not None else -99.0,
        row.return_126 if row.return_126 is not None else -99.0,
        row.cagr_delta if row.cagr_delta is not None else -99.0,
    )


def summarize_incumbent_priority(rows: list[CandidateScreenRow]) -> str:
    if not rows:
        return "none"
    if any(row.priority == "monitor" for row in rows):
        return "monitor"
    return "incumbent"


def summary_action(incumbent_priority: str, best: CandidateScreenRow | None) -> str:
    if best is None:
        if incumbent_priority == "monitor":
            return "Review incumbent; no challenger is currently available in this role."
        return "Maintain incumbent and keep monitoring the role."
    if incumbent_priority == "monitor" and best.priority in {"high", "watch"}:
        return "Prioritize this role for quarterly review."
    if best.priority == "high":
        return "Promote best challenger to a quarterly review memo."
    if best.priority == "watch":
        return "Keep challenger on watch list and require more evidence."
    if best.priority == "no_data":
        return "Maintain incumbent; collect more candidate history."
    return "Maintain incumbent; challenger currently fails the screen."


def summary_reason_codes(
    incumbents: list[CandidateScreenRow],
    best: CandidateScreenRow | None,
) -> tuple[str, ...]:
    codes: list[str] = []
    if any(row.priority == "monitor" for row in incumbents):
        codes.append("incumbent_monitor")
    if best is not None:
        codes.append(f"best_{best.priority}")
        for code in best.reason_codes:
            if code not in codes:
                codes.append(code)
    return tuple(codes)


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
