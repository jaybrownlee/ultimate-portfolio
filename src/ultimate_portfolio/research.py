from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
import random
import statistics

from .risk import calculate_max_drawdown, percentile
from .strategy import HierarchicalStrategy


@dataclass(frozen=True)
class PricePoint:
    observation_date: date
    ticker: str
    price: float

    def __post_init__(self) -> None:
        if not self.ticker.strip():
            raise ValueError("Price ticker cannot be blank.")
        if self.price <= 0:
            raise ValueError(f"{self.ticker}: price must be positive.")

    @property
    def symbol(self) -> str:
        return self.ticker.upper().strip()


@dataclass(frozen=True)
class ValuePoint:
    observation_date: date
    value: float


@dataclass(frozen=True)
class DrawdownStats:
    max_drawdown: float
    peak_date: date
    trough_date: date
    recovery_date: date | None
    drawdown_periods: int


@dataclass(frozen=True)
class PerformanceMetrics:
    start_date: date
    end_date: date
    periods: int
    start_value: float
    end_value: float
    total_return: float
    cagr: float
    annualized_volatility: float
    sharpe_ratio: float | None
    sortino_ratio: float | None
    calmar_ratio: float | None
    max_drawdown: float
    drawdown_peak_date: date
    drawdown_trough_date: date
    drawdown_recovery_date: date | None
    drawdown_periods: int
    var_95: float
    cvar_95: float
    best_period_return: float
    worst_period_return: float
    positive_period_rate: float


@dataclass(frozen=True)
class RelativeMetrics:
    benchmark_total_return: float
    active_return: float
    tracking_error: float | None
    information_ratio: float | None
    beta: float | None
    correlation: float | None


@dataclass(frozen=True)
class BacktestResult:
    mode: str
    rebalance_frequency: str
    initial_value: float
    annualization_periods: int
    weights: dict[str, float]
    benchmark_weights: dict[str, float]
    portfolio_values: tuple[ValuePoint, ...]
    benchmark_values: tuple[ValuePoint, ...]
    portfolio_metrics: PerformanceMetrics
    benchmark_metrics: PerformanceMetrics | None
    relative_metrics: RelativeMetrics | None
    skipped_dates: tuple[date, ...]


@dataclass(frozen=True)
class RollingMetricPoint:
    observation_date: date
    window: int
    total_return: float
    annualized_volatility: float
    sharpe_ratio: float | None
    benchmark_total_return: float | None
    correlation: float | None


@dataclass(frozen=True)
class RebalanceComparison:
    frequency: str
    total_return: float
    cagr: float
    annualized_volatility: float
    sharpe_ratio: float | None
    max_drawdown: float
    active_return: float | None
    information_ratio: float | None


@dataclass(frozen=True)
class SymbolContribution:
    ticker: str
    bucket: str | None
    weight: float
    cumulative_return: float
    arithmetic_return_contribution: float
    annualized_return_contribution: float
    standalone_volatility: float
    volatility_contribution: float | None


@dataclass(frozen=True)
class BucketContribution:
    bucket: str
    weight: float
    arithmetic_return_contribution: float
    annualized_return_contribution: float
    volatility_contribution: float | None


@dataclass(frozen=True)
class ContributionReport:
    portfolio_volatility: float
    symbol_contributions: tuple[SymbolContribution, ...]
    bucket_contributions: tuple[BucketContribution, ...]


@dataclass(frozen=True)
class HistoricalMonteCarloAssumptions:
    paths: int = 5000
    periods: int = 252
    starting_value: float = 100000.0
    method: str = "bootstrap"
    block_size: int = 21
    student_t_df: float = 5.0
    seed: int | None = 7


@dataclass(frozen=True)
class HistoricalMonteCarloResult:
    method: str
    paths: int
    periods: int
    starting_value: float
    median_ending_value: float
    percentile_5_ending_value: float
    percentile_95_ending_value: float
    probability_of_loss: float
    median_max_drawdown: float
    average_max_drawdown: float


def run_strategy_backtest(
    strategy: HierarchicalStrategy,
    price_points: list[PricePoint],
    *,
    initial_value: float = 100000.0,
    rebalance_frequency: str = "quarterly",
    annualization_periods: int = 252,
    risk_free_rate: float = 0.0,
    benchmark_weights: dict[str, float] | None = None,
    mode: str = "actual_current_portfolio",
) -> BacktestResult:
    return run_weighted_backtest(
        price_points,
        strategy.total_target_weights(),
        benchmark_weights=benchmark_weights,
        initial_value=initial_value,
        rebalance_frequency=rebalance_frequency,
        annualization_periods=annualization_periods,
        risk_free_rate=risk_free_rate,
        mode=mode,
    )


def apply_proxy_map(price_points: list[PricePoint], proxy_map: dict[str, str]) -> list[PricePoint]:
    if not proxy_map:
        return price_points
    normalized_map = {target.upper().strip(): proxy.upper().strip() for target, proxy in proxy_map.items()}
    mapped: list[PricePoint] = []
    for point in price_points:
        mapped.append(point)
        for target, proxy in normalized_map.items():
            if point.symbol == proxy:
                mapped.append(PricePoint(point.observation_date, target, point.price))
    return mapped


def compare_rebalance_frequencies(
    strategy: HierarchicalStrategy,
    price_points: list[PricePoint],
    *,
    benchmark_weights: dict[str, float] | None = None,
    initial_value: float = 100000.0,
    annualization_periods: int = 252,
    risk_free_rate: float = 0.0,
    frequencies: tuple[str, ...] = ("none", "monthly", "quarterly", "yearly"),
) -> tuple[RebalanceComparison, ...]:
    comparisons: list[RebalanceComparison] = []
    for frequency in frequencies:
        result = run_strategy_backtest(
            strategy,
            price_points,
            benchmark_weights=benchmark_weights,
            initial_value=initial_value,
            rebalance_frequency=frequency,
            annualization_periods=annualization_periods,
            risk_free_rate=risk_free_rate,
        )
        metrics = result.portfolio_metrics
        comparisons.append(
            RebalanceComparison(
                frequency=frequency,
                total_return=metrics.total_return,
                cagr=metrics.cagr,
                annualized_volatility=metrics.annualized_volatility,
                sharpe_ratio=metrics.sharpe_ratio,
                max_drawdown=metrics.max_drawdown,
                active_return=None if result.relative_metrics is None else result.relative_metrics.active_return,
                information_ratio=None if result.relative_metrics is None else result.relative_metrics.information_ratio,
            )
        )
    return tuple(comparisons)


def run_weighted_backtest(
    price_points: list[PricePoint],
    weights: dict[str, float],
    *,
    benchmark_weights: dict[str, float] | None = None,
    initial_value: float = 100000.0,
    rebalance_frequency: str = "quarterly",
    annualization_periods: int = 252,
    risk_free_rate: float = 0.0,
    mode: str = "weighted_allocation",
) -> BacktestResult:
    normalized_weights = normalize_weights(weights)
    normalized_benchmark = normalize_weights(benchmark_weights or {})
    if initial_value <= 0:
        raise ValueError("Initial value must be positive.")
    if annualization_periods <= 0:
        raise ValueError("Annualization periods must be positive.")
    if rebalance_frequency not in {"none", "monthly", "quarterly", "yearly"}:
        raise ValueError("Rebalance frequency must be one of none, monthly, quarterly, yearly.")

    price_table = build_price_table(price_points)
    required_symbols = set(normalized_weights) | set(normalized_benchmark)
    valid_dates, skipped_dates = aligned_dates(price_table, required_symbols)
    if len(valid_dates) < 2:
        raise ValueError("At least two complete price dates are required for a backtest.")

    portfolio_values = simulate_rebalanced_values(
        price_table,
        valid_dates,
        normalized_weights,
        initial_value=initial_value,
        rebalance_frequency=rebalance_frequency,
    )

    benchmark_values: tuple[ValuePoint, ...] = ()
    benchmark_metrics = None
    relative_metrics = None
    if normalized_benchmark:
        benchmark_values = simulate_rebalanced_values(
            price_table,
            valid_dates,
            normalized_benchmark,
            initial_value=initial_value,
            rebalance_frequency=rebalance_frequency,
        )
        benchmark_metrics = calculate_performance_metrics(
            benchmark_values,
            annualization_periods=annualization_periods,
            risk_free_rate=risk_free_rate,
        )
        relative_metrics = calculate_relative_metrics(
            portfolio_values,
            benchmark_values,
            annualization_periods=annualization_periods,
        )

    return BacktestResult(
        mode=mode,
        rebalance_frequency=rebalance_frequency,
        initial_value=initial_value,
        annualization_periods=annualization_periods,
        weights=normalized_weights,
        benchmark_weights=normalized_benchmark,
        portfolio_values=portfolio_values,
        benchmark_values=benchmark_values,
        portfolio_metrics=calculate_performance_metrics(
            portfolio_values,
            annualization_periods=annualization_periods,
            risk_free_rate=risk_free_rate,
        ),
        benchmark_metrics=benchmark_metrics,
        relative_metrics=relative_metrics,
        skipped_dates=tuple(skipped_dates),
    )


def simulate_rebalanced_values(
    price_table: dict[date, dict[str, float]],
    valid_dates: list[date],
    weights: dict[str, float],
    *,
    initial_value: float,
    rebalance_frequency: str,
) -> tuple[ValuePoint, ...]:
    first_date = valid_dates[0]
    shares = allocate_shares(initial_value, weights, price_table[first_date])
    values: list[ValuePoint] = []
    previous_date = first_date

    for current_date in valid_dates:
        current_value = portfolio_value(shares, price_table[current_date])
        if should_rebalance(previous_date, current_date, rebalance_frequency):
            shares = allocate_shares(current_value, weights, price_table[current_date])
            current_value = portfolio_value(shares, price_table[current_date])
        values.append(ValuePoint(current_date, current_value))
        previous_date = current_date

    return tuple(values)


def calculate_performance_metrics(
    values: tuple[ValuePoint, ...],
    *,
    annualization_periods: int = 252,
    risk_free_rate: float = 0.0,
) -> PerformanceMetrics:
    if len(values) < 2:
        raise ValueError("At least two values are required for performance metrics.")
    raw_values = [point.value for point in values]
    returns = periodic_returns(raw_values)
    drawdown = calculate_drawdown_stats(values)
    periods = len(returns)
    total_return = (raw_values[-1] / raw_values[0]) - 1.0
    years = periods / annualization_periods
    cagr = (raw_values[-1] / raw_values[0]) ** (1 / years) - 1.0 if years > 0 else 0.0
    volatility = annualized_volatility(returns, annualization_periods)
    sharpe = sharpe_ratio(returns, risk_free_rate=risk_free_rate, annualization_periods=annualization_periods)
    sortino = sortino_ratio(returns, risk_free_rate=risk_free_rate, annualization_periods=annualization_periods)
    calmar = cagr / abs(drawdown.max_drawdown) if drawdown.max_drawdown < 0 else None
    sorted_returns = sorted(returns)
    var_95 = percentile(sorted_returns, 0.05)
    cvar_tail = [item for item in returns if item <= var_95]
    cvar_95 = statistics.fmean(cvar_tail) if cvar_tail else var_95

    return PerformanceMetrics(
        start_date=values[0].observation_date,
        end_date=values[-1].observation_date,
        periods=periods,
        start_value=raw_values[0],
        end_value=raw_values[-1],
        total_return=total_return,
        cagr=cagr,
        annualized_volatility=volatility,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        calmar_ratio=calmar,
        max_drawdown=drawdown.max_drawdown,
        drawdown_peak_date=drawdown.peak_date,
        drawdown_trough_date=drawdown.trough_date,
        drawdown_recovery_date=drawdown.recovery_date,
        drawdown_periods=drawdown.drawdown_periods,
        var_95=var_95,
        cvar_95=cvar_95,
        best_period_return=max(returns),
        worst_period_return=min(returns),
        positive_period_rate=sum(item > 0 for item in returns) / len(returns),
    )


def calculate_relative_metrics(
    portfolio_values: tuple[ValuePoint, ...],
    benchmark_values: tuple[ValuePoint, ...],
    *,
    annualization_periods: int = 252,
) -> RelativeMetrics:
    if len(portfolio_values) != len(benchmark_values):
        raise ValueError("Portfolio and benchmark value series must be aligned.")
    portfolio_returns = periodic_returns([point.value for point in portfolio_values])
    benchmark_returns = periodic_returns([point.value for point in benchmark_values])
    active_returns = [left - right for left, right in zip(portfolio_returns, benchmark_returns)]
    tracking = annualized_volatility(active_returns, annualization_periods)
    info = annualized_mean(active_returns, annualization_periods) / tracking if tracking > 0 else None
    benchmark_variance = sample_variance(benchmark_returns)
    beta = sample_covariance(portfolio_returns, benchmark_returns) / benchmark_variance if benchmark_variance > 0 else None
    corr = correlation(portfolio_returns, benchmark_returns)

    return RelativeMetrics(
        benchmark_total_return=(benchmark_values[-1].value / benchmark_values[0].value) - 1.0,
        active_return=(portfolio_values[-1].value / portfolio_values[0].value)
        - (benchmark_values[-1].value / benchmark_values[0].value),
        tracking_error=tracking if tracking > 0 else None,
        information_ratio=info,
        beta=beta,
        correlation=corr,
    )


def rolling_metrics(
    portfolio_values: tuple[ValuePoint, ...],
    *,
    benchmark_values: tuple[ValuePoint, ...] = (),
    window: int = 63,
    annualization_periods: int = 252,
    risk_free_rate: float = 0.0,
) -> tuple[RollingMetricPoint, ...]:
    if window < 2:
        raise ValueError("Rolling window must be at least 2 periods.")
    if len(portfolio_values) <= window:
        return ()
    if benchmark_values and len(benchmark_values) != len(portfolio_values):
        raise ValueError("Portfolio and benchmark values must be aligned.")

    portfolio_returns = periodic_returns([point.value for point in portfolio_values])
    benchmark_returns = periodic_returns([point.value for point in benchmark_values]) if benchmark_values else []
    rows: list[RollingMetricPoint] = []
    for end_index in range(window, len(portfolio_returns) + 1):
        portfolio_window = portfolio_returns[end_index - window:end_index]
        benchmark_window = benchmark_returns[end_index - window:end_index] if benchmark_returns else []
        benchmark_total = None
        corr = None
        if benchmark_window:
            benchmark_total = (benchmark_values[end_index].value / benchmark_values[end_index - window].value) - 1.0
            corr = correlation(portfolio_window, benchmark_window)
        rows.append(
            RollingMetricPoint(
                observation_date=portfolio_values[end_index].observation_date,
                window=window,
                total_return=(portfolio_values[end_index].value / portfolio_values[end_index - window].value) - 1.0,
                annualized_volatility=annualized_volatility(portfolio_window, annualization_periods),
                sharpe_ratio=sharpe_ratio(
                    portfolio_window,
                    risk_free_rate=risk_free_rate,
                    annualization_periods=annualization_periods,
                ),
                benchmark_total_return=benchmark_total,
                correlation=corr,
            )
        )
    return tuple(rows)


def calculate_drawdown_stats(values: tuple[ValuePoint, ...]) -> DrawdownStats:
    raw_values = [point.value for point in values]
    max_drawdown = calculate_max_drawdown(raw_values)
    peak_value = raw_values[0]
    peak_index = 0
    trough_index = 0
    current_peak_index = 0
    for index, value in enumerate(raw_values):
        if value > peak_value:
            peak_value = value
            current_peak_index = index
        drawdown = (value / peak_value) - 1.0
        if math.isclose(drawdown, max_drawdown, abs_tol=1e-12):
            peak_index = current_peak_index
            trough_index = index
            break

    recovery_index = None
    peak_threshold = raw_values[peak_index]
    for index in range(trough_index + 1, len(raw_values)):
        if raw_values[index] >= peak_threshold:
            recovery_index = index
            break

    return DrawdownStats(
        max_drawdown=max_drawdown,
        peak_date=values[peak_index].observation_date,
        trough_date=values[trough_index].observation_date,
        recovery_date=None if recovery_index is None else values[recovery_index].observation_date,
        drawdown_periods=(len(values) - 1 - peak_index) if recovery_index is None else (recovery_index - peak_index),
    )


def build_price_table(price_points: list[PricePoint]) -> dict[date, dict[str, float]]:
    table: dict[date, dict[str, float]] = {}
    for point in price_points:
        table.setdefault(point.observation_date, {})[point.symbol] = point.price
    return table


def contribution_report(
    strategy: HierarchicalStrategy,
    price_points: list[PricePoint],
    *,
    annualization_periods: int = 252,
) -> ContributionReport:
    weights = normalize_weights(strategy.total_target_weights())
    price_table = build_price_table(price_points)
    valid_dates, _ = aligned_dates(price_table, set(weights))
    if len(valid_dates) < 2:
        raise ValueError("At least two complete price dates are required for contribution analysis.")

    symbol_returns = symbol_periodic_returns(price_table, valid_dates, set(weights))
    portfolio_returns = [
        sum(weights[symbol] * symbol_returns[symbol][index] for symbol in weights)
        for index in range(len(valid_dates) - 1)
    ]
    portfolio_vol = annualized_volatility(portfolio_returns, annualization_periods)
    symbol_rows: list[SymbolContribution] = []
    bucket_totals: dict[str, dict[str, float]] = {}

    for symbol in sorted(weights):
        returns = symbol_returns[symbol]
        arithmetic = sum(weights[symbol] * item for item in returns)
        annualized = statistics.fmean([weights[symbol] * item for item in returns]) * annualization_periods
        standalone_vol = annualized_volatility(returns, annualization_periods)
        vol_contribution = None
        if portfolio_vol > 0:
            vol_contribution = weights[symbol] * sample_covariance(returns, portfolio_returns) * annualization_periods / portfolio_vol
        bucket = strategy.bucket_for_symbol(symbol)
        totals = bucket_totals.setdefault(bucket, {"weight": 0.0, "arithmetic": 0.0, "annualized": 0.0, "vol": 0.0})
        totals["weight"] += weights[symbol]
        totals["arithmetic"] += arithmetic
        totals["annualized"] += annualized
        totals["vol"] += vol_contribution or 0.0
        symbol_rows.append(
            SymbolContribution(
                ticker=symbol,
                bucket=bucket,
                weight=weights[symbol],
                cumulative_return=(price_table[valid_dates[-1]][symbol] / price_table[valid_dates[0]][symbol]) - 1.0,
                arithmetic_return_contribution=arithmetic,
                annualized_return_contribution=annualized,
                standalone_volatility=standalone_vol,
                volatility_contribution=vol_contribution,
            )
        )

    bucket_rows = tuple(
        BucketContribution(
            bucket=bucket,
            weight=totals["weight"],
            arithmetic_return_contribution=totals["arithmetic"],
            annualized_return_contribution=totals["annualized"],
            volatility_contribution=None if portfolio_vol <= 0 else totals["vol"],
        )
        for bucket, totals in sorted(bucket_totals.items())
    )
    return ContributionReport(
        portfolio_volatility=portfolio_vol,
        symbol_contributions=tuple(symbol_rows),
        bucket_contributions=bucket_rows,
    )


def aligned_dates(
    price_table: dict[date, dict[str, float]],
    required_symbols: set[str],
) -> tuple[list[date], list[date]]:
    if not required_symbols:
        raise ValueError("At least one symbol is required.")
    valid_dates: list[date] = []
    skipped_dates: list[date] = []
    for observation_date in sorted(price_table):
        symbols = set(price_table[observation_date])
        if required_symbols.issubset(symbols):
            valid_dates.append(observation_date)
        else:
            skipped_dates.append(observation_date)
    return valid_dates, skipped_dates


def symbol_periodic_returns(
    price_table: dict[date, dict[str, float]],
    valid_dates: list[date],
    symbols: set[str],
) -> dict[str, list[float]]:
    returns = {symbol: [] for symbol in symbols}
    for previous_date, current_date in zip(valid_dates, valid_dates[1:]):
        for symbol in symbols:
            returns[symbol].append((price_table[current_date][symbol] / price_table[previous_date][symbol]) - 1.0)
    return returns


def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    if not weights:
        return {}
    normalized_keys = {symbol.upper().strip(): weight for symbol, weight in weights.items()}
    if any(not symbol for symbol in normalized_keys):
        raise ValueError("Weight symbols cannot be blank.")
    if any(weight < 0 for weight in normalized_keys.values()):
        raise ValueError("Weights cannot be negative.")
    total = sum(normalized_keys.values())
    if total <= 0:
        raise ValueError("Weights must sum to a positive value.")
    return {symbol: weight / total for symbol, weight in normalized_keys.items()}


def allocate_shares(total_value: float, weights: dict[str, float], prices: dict[str, float]) -> dict[str, float]:
    return {symbol: (total_value * weight) / prices[symbol] for symbol, weight in weights.items()}


def portfolio_value(shares: dict[str, float], prices: dict[str, float]) -> float:
    return sum(quantity * prices[symbol] for symbol, quantity in shares.items())


def should_rebalance(previous_date: date, current_date: date, frequency: str) -> bool:
    if frequency == "none":
        return False
    if current_date == previous_date:
        return False
    if frequency == "monthly":
        return current_date.month != previous_date.month or current_date.year != previous_date.year
    if frequency == "quarterly":
        previous_quarter = (previous_date.month - 1) // 3
        current_quarter = (current_date.month - 1) // 3
        return previous_quarter != current_quarter or current_date.year != previous_date.year
    if frequency == "yearly":
        return current_date.year != previous_date.year
    raise ValueError("Unsupported rebalance frequency.")


def periodic_returns(values: list[float]) -> list[float]:
    if len(values) < 2:
        raise ValueError("At least two values are required for returns.")
    returns: list[float] = []
    for previous, current in zip(values, values[1:]):
        if previous <= 0 or current <= 0:
            raise ValueError("Values must be positive for returns.")
        returns.append((current / previous) - 1.0)
    return returns


def run_historical_monte_carlo(
    returns: list[float],
    assumptions: HistoricalMonteCarloAssumptions,
) -> HistoricalMonteCarloResult:
    if len(returns) < 2:
        raise ValueError("At least two historical returns are required.")
    if assumptions.paths <= 0:
        raise ValueError("Monte Carlo paths must be positive.")
    if assumptions.periods <= 0:
        raise ValueError("Monte Carlo periods must be positive.")
    if assumptions.starting_value <= 0:
        raise ValueError("Starting value must be positive.")
    if assumptions.method not in {"bootstrap", "block_bootstrap", "student_t", "gaussian"}:
        raise ValueError("Method must be one of bootstrap, block_bootstrap, student_t, gaussian.")
    if assumptions.block_size <= 0:
        raise ValueError("Block size must be positive.")
    if assumptions.student_t_df <= 2:
        raise ValueError("Student-t degrees of freedom must be greater than 2.")

    rng = random.Random(assumptions.seed)
    ending_values: list[float] = []
    max_drawdowns: list[float] = []
    mean_return = statistics.fmean(returns)
    stdev = statistics.stdev(returns)

    for _ in range(assumptions.paths):
        path_returns = simulated_return_path(returns, assumptions, rng, mean_return, stdev)
        values = [assumptions.starting_value]
        for period_return in path_returns:
            values.append(values[-1] * (1 + max(period_return, -0.95)))
        ending_values.append(values[-1])
        max_drawdowns.append(calculate_max_drawdown(values))

    sorted_endings = sorted(ending_values)
    return HistoricalMonteCarloResult(
        method=assumptions.method,
        paths=assumptions.paths,
        periods=assumptions.periods,
        starting_value=assumptions.starting_value,
        median_ending_value=statistics.median(sorted_endings),
        percentile_5_ending_value=percentile(sorted_endings, 0.05),
        percentile_95_ending_value=percentile(sorted_endings, 0.95),
        probability_of_loss=sum(value < assumptions.starting_value for value in ending_values) / assumptions.paths,
        median_max_drawdown=statistics.median(max_drawdowns),
        average_max_drawdown=statistics.fmean(max_drawdowns),
    )


def simulated_return_path(
    returns: list[float],
    assumptions: HistoricalMonteCarloAssumptions,
    rng: random.Random,
    mean_return: float,
    stdev: float,
) -> list[float]:
    if assumptions.method == "bootstrap":
        return [rng.choice(returns) for _ in range(assumptions.periods)]
    if assumptions.method == "block_bootstrap":
        path: list[float] = []
        while len(path) < assumptions.periods:
            start = rng.randrange(0, len(returns))
            for offset in range(assumptions.block_size):
                path.append(returns[(start + offset) % len(returns)])
                if len(path) == assumptions.periods:
                    break
        return path
    if assumptions.method == "gaussian":
        return [rng.gauss(mean_return, stdev) for _ in range(assumptions.periods)]
    return [student_t_return(rng, mean_return, stdev, assumptions.student_t_df) for _ in range(assumptions.periods)]


def student_t_return(rng: random.Random, mean_return: float, stdev: float, df: float) -> float:
    normal = rng.gauss(0, 1)
    chi_square = rng.gammavariate(df / 2, 2)
    t_sample = normal / math.sqrt(chi_square / df)
    scale = stdev / math.sqrt(df / (df - 2))
    return mean_return + scale * t_sample


def annualized_mean(returns: list[float], periods_per_year: int) -> float:
    if not returns:
        raise ValueError("Returns are required.")
    return statistics.fmean(returns) * periods_per_year


def annualized_volatility(returns: list[float], periods_per_year: int) -> float:
    if len(returns) < 2:
        return 0.0
    return statistics.stdev(returns) * math.sqrt(periods_per_year)


def sharpe_ratio(returns: list[float], *, risk_free_rate: float, annualization_periods: int) -> float | None:
    if len(returns) < 2:
        return None
    period_risk_free = (1 + risk_free_rate) ** (1 / annualization_periods) - 1
    excess = [item - period_risk_free for item in returns]
    volatility = annualized_volatility(returns, annualization_periods)
    if volatility <= 0:
        return None
    return annualized_mean(excess, annualization_periods) / volatility


def sortino_ratio(returns: list[float], *, risk_free_rate: float, annualization_periods: int) -> float | None:
    if len(returns) < 2:
        return None
    period_risk_free = (1 + risk_free_rate) ** (1 / annualization_periods) - 1
    excess = [item - period_risk_free for item in returns]
    downside = [min(item, 0.0) for item in excess]
    downside_deviation = math.sqrt(statistics.fmean(item * item for item in downside)) * math.sqrt(annualization_periods)
    if downside_deviation <= 0:
        return None
    return annualized_mean(excess, annualization_periods) / downside_deviation


def sample_variance(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return statistics.variance(values)


def sample_covariance(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("Series must have equal length.")
    if len(left) < 2:
        return 0.0
    left_mean = statistics.fmean(left)
    right_mean = statistics.fmean(right)
    return sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right)) / (len(left) - 1)


def correlation(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right):
        raise ValueError("Series must have equal length.")
    left_stdev = statistics.stdev(left) if len(left) > 1 else 0.0
    right_stdev = statistics.stdev(right) if len(right) > 1 else 0.0
    if left_stdev <= 0 or right_stdev <= 0:
        return None
    return sample_covariance(left, right) / (left_stdev * right_stdev)
