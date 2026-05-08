from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, is_dataclass
from datetime import date
import json
import sys
from pathlib import Path
from typing import Any

from .data import download_yahoo_chart_prices, download_yfinance_prices
from .dca import build_dca_schedule
from .research import (
    HistoricalMonteCarloAssumptions,
    PricePoint,
    apply_proxy_map,
    compare_rebalance_frequencies,
    contribution_report,
    periodic_returns,
    rolling_metrics,
    run_historical_monte_carlo,
    run_strategy_backtest,
)
from .risk import (
    AdopterMetrics,
    MonteCarloAssumptions,
    ReviewObservation,
    evaluate_adopter_metrics,
    review_history,
    run_monte_carlo,
    run_stress_scenarios,
)
from .strategy import AnalysisResult, HierarchicalStrategy, Position, build_default_strategy


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except (OSError, RuntimeError, ValueError, argparse.ArgumentTypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ultimate-portfolio",
        description="Stress test and automate the 80/20 AI infrastructure core/satellite strategy.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze", help="Analyze holdings and print rebalance guidance.")
    add_strategy_flags(analyze)
    analyze.add_argument("positions_csv", type=Path, help="CSV with ticker plus market_value, or shares and price.")
    analyze.add_argument("--as-of", type=parse_date, default=date.today(), help="Analysis date, YYYY-MM-DD.")
    analyze.add_argument("--force-sweep", action="store_true", help="Force the quarterly internal bucket sweep.")
    analyze.add_argument(
        "--no-auto-sweep",
        action="store_true",
        help="Do not automatically run the internal sweep on calendar quarter end.",
    )
    analyze.add_argument("--full", action="store_true", help="Force a full 80/20 and internal holding rebalance.")
    analyze.add_argument("--peak-value", type=float, help="Peak account value used for the 20% uncle-point test.")
    analyze.add_argument("--ignore-circuit-breaker", action="store_true", help="Do not apply the uncle-point override.")
    analyze.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    analyze.set_defaults(func=run_analyze)

    dca = subparsers.add_parser("dca", help="Build the 25% defensive entry plus monthly DCA schedule.")
    add_strategy_flags(dca)
    dca.add_argument("total_cash", type=parse_cash_amount, help="Cash to deploy.")
    dca.add_argument("--start", type=parse_date, default=date.today(), help="Deployment start date, YYYY-MM-DD.")
    dca.add_argument("--months", type=int, default=6, help="DCA duration, 1-6 months.")
    dca.add_argument("--initial-pct", type=float, default=0.25, help="Initial defensive-core deployment percent.")
    dca.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    dca.set_defaults(func=run_dca)

    stress = subparsers.add_parser("stress", help="Run deterministic scenario shocks and Monte Carlo simulation.")
    add_strategy_flags(stress)
    stress.add_argument("positions_csv", type=Path, help="Current holdings CSV.")
    stress.add_argument("--as-of", type=parse_date, default=date.today(), help="Analysis date, YYYY-MM-DD.")
    stress.add_argument("--peak-value", type=float, help="Peak account value for scenario circuit-breaker checks.")
    stress.add_argument("--years", type=int, default=10, help="Monte Carlo horizon in years.")
    stress.add_argument("--paths", type=int, default=5000, help="Monte Carlo path count.")
    stress.add_argument("--starting-value", type=float, help="Monte Carlo starting value. Defaults to CSV total value.")
    stress.add_argument("--core-vol", type=float, default=0.115, help="Annualized core volatility assumption.")
    stress.add_argument("--satellite-vol", type=float, default=0.38, help="Annualized satellite volatility assumption.")
    stress.add_argument("--correlation", type=float, default=0.25, help="Core/satellite return correlation assumption.")
    stress.add_argument("--seed", type=int, default=7, help="Monte Carlo random seed.")
    stress.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    stress.set_defaults(func=run_stress)

    backtest = subparsers.add_parser("backtest", help="Backtest the target allocation from a long-form price CSV.")
    add_strategy_flags(backtest)
    backtest.add_argument("prices_csv", type=Path, help="CSV with date, ticker, price columns.")
    backtest.add_argument("--initial-value", type=float, default=100000, help="Starting portfolio value.")
    backtest.add_argument(
        "--rebalance",
        choices=("none", "monthly", "quarterly", "yearly"),
        default="quarterly",
        help="Portfolio rebalance frequency.",
    )
    backtest.add_argument("--annualization", type=int, default=252, help="Periods per year, usually 252 for daily data.")
    backtest.add_argument("--risk-free-rate", type=float, default=0.0, help="Annual risk-free rate used for Sharpe and Sortino.")
    backtest.add_argument(
        "--benchmark",
        default="VBIAX:0.8,QQQ:0.2",
        help="Comma-separated benchmark weights, e.g. VBIAX:0.8,QQQ:0.2. Use empty string for no benchmark.",
    )
    backtest.add_argument(
        "--proxy-map",
        default="",
        help="Comma-separated target=proxy mappings for proxy-regime research, e.g. ELFY=GRID,BAI=QQQ.",
    )
    backtest.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    backtest.set_defaults(func=run_backtest)

    suite = subparsers.add_parser("research-suite", help="Run backtest, rolling diagnostics, rebalance comparison, attribution, and historical Monte Carlo.")
    add_strategy_flags(suite)
    suite.add_argument("prices_csv", type=Path, help="CSV with date, ticker, price columns.")
    suite.add_argument("--initial-value", type=float, default=100000, help="Starting portfolio value.")
    suite.add_argument("--annualization", type=int, default=252, help="Periods per year, usually 252 for daily data.")
    suite.add_argument("--risk-free-rate", type=float, default=0.0, help="Annual risk-free rate used for Sharpe and Sortino.")
    suite.add_argument("--benchmark", default="VBIAX:0.8,QQQ:0.2", help="Comma-separated benchmark weights.")
    suite.add_argument("--proxy-map", default="", help="Comma-separated target=proxy mappings for proxy-regime research.")
    suite.add_argument("--mc-paths", type=int, default=2000, help="Historical Monte Carlo path count.")
    suite.add_argument("--mc-periods", type=int, default=252, help="Historical Monte Carlo periods per path.")
    suite.add_argument("--report", type=Path, help="Optional Markdown report path.")
    suite.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    suite.set_defaults(func=run_research_suite)

    download = subparsers.add_parser("download-prices", help="Download adjusted close prices into backtest CSV format.")
    add_strategy_flags(download)
    download.add_argument("--tickers", help="Comma-separated tickers. Defaults to strategy holdings plus VBIAX and QQQ.")
    download.add_argument("--start", type=parse_date, required=True, help="Start date, YYYY-MM-DD.")
    download.add_argument("--end", type=parse_date, default=date.today(), help="End date, YYYY-MM-DD. Providers treat this as exclusive.")
    download.add_argument("--output", type=Path, default=Path("data/cache/prices.csv"), help="Output CSV path.")
    download.add_argument(
        "--provider",
        choices=("yahoo-chart", "yfinance"),
        default="yahoo-chart",
        help="Data provider. yahoo-chart uses the standard library; yfinance requires research extras.",
    )
    download.set_defaults(func=run_download_prices)

    review = subparsers.add_parser("review", help="Run the monthly review protocol from a history CSV.")
    review.add_argument("history_csv", type=Path, help="CSV with date, portfolio_value, and optional benchmark/satellite/qqq values.")
    review.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    review.set_defaults(func=run_review)

    screen = subparsers.add_parser("screen-adopters", help="Apply the 2-of-3 AI adopter quality screen.")
    screen.add_argument("metrics_csv", type=Path, help="CSV with ticker, it_capex_growth, sgna_intensity_change, gross_margin_expansion_bps.")
    screen.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    screen.set_defaults(func=run_screen_adopters)

    return parser


def add_strategy_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--stagflation-overlay",
        action="store_true",
        help="Shift 5% of the core from SGOV/TLT into GLDM.",
    )


def selected_strategy(args: argparse.Namespace) -> HierarchicalStrategy:
    return build_default_strategy(stagflation_overlay=getattr(args, "stagflation_overlay", False))


def run_analyze(args: argparse.Namespace) -> int:
    strategy = selected_strategy(args)
    positions = read_positions_csv(args.positions_csv)
    result = strategy.analyze(
        positions,
        args.as_of,
        force_sweep=args.force_sweep,
        auto_calendar_sweep=not args.no_auto_sweep,
        full_rebalance=args.full,
        peak_value=args.peak_value,
        enforce_circuit_breaker=not args.ignore_circuit_breaker,
    )
    if args.json:
        print(json.dumps(to_jsonable(result), indent=2, sort_keys=True))
    else:
        print_text_report(result, strategy)
    return 0


def run_dca(args: argparse.Namespace) -> int:
    schedule = build_dca_schedule(
        selected_strategy(args),
        args.total_cash,
        args.start,
        months=args.months,
        initial_deploy_pct=args.initial_pct,
    )
    if args.json:
        print(json.dumps(to_jsonable(schedule), indent=2, sort_keys=True))
    else:
        print_dca_schedule(schedule)
    return 0


def run_stress(args: argparse.Namespace) -> int:
    strategy = selected_strategy(args)
    positions = read_positions_csv(args.positions_csv)
    starting_value = args.starting_value or sum(position.market_value for position in positions)
    scenarios = run_stress_scenarios(strategy, positions, args.as_of, peak_value=args.peak_value)
    monte_carlo = run_monte_carlo(
        strategy,
        MonteCarloAssumptions(
            years=args.years,
            paths=args.paths,
            starting_value=starting_value,
            core_expected_return=strategy.expected_core_return,
            satellite_expected_return=strategy.expected_satellite_return,
            core_volatility=args.core_vol,
            satellite_volatility=args.satellite_vol,
            core_satellite_correlation=args.correlation,
            seed=args.seed,
        ),
    )
    if args.json:
        print(json.dumps({"scenarios": to_jsonable(scenarios), "monte_carlo": to_jsonable(monte_carlo)}, indent=2, sort_keys=True))
    else:
        print_stress_report(scenarios, monte_carlo)
    return 0


def run_backtest(args: argparse.Namespace) -> int:
    proxy_map = parse_proxy_map(args.proxy_map)
    price_points = apply_proxy_map(read_prices_csv(args.prices_csv), proxy_map)
    result = run_strategy_backtest(
        selected_strategy(args),
        price_points,
        initial_value=args.initial_value,
        rebalance_frequency=args.rebalance,
        annualization_periods=args.annualization,
        risk_free_rate=args.risk_free_rate,
        benchmark_weights=parse_weight_map(args.benchmark),
        mode="proxy_regime" if proxy_map else "actual_current_portfolio",
    )
    if args.json:
        print(json.dumps(to_jsonable(result), indent=2, sort_keys=True))
    else:
        print_backtest_report(result)
    return 0


def run_research_suite(args: argparse.Namespace) -> int:
    strategy = selected_strategy(args)
    benchmark_weights = parse_weight_map(args.benchmark)
    proxy_map = parse_proxy_map(args.proxy_map)
    price_points = apply_proxy_map(read_prices_csv(args.prices_csv), proxy_map)
    backtest = run_strategy_backtest(
        strategy,
        price_points,
        initial_value=args.initial_value,
        rebalance_frequency="quarterly",
        annualization_periods=args.annualization,
        risk_free_rate=args.risk_free_rate,
        benchmark_weights=benchmark_weights,
        mode="proxy_regime" if proxy_map else "actual_current_portfolio",
    )
    comparisons = compare_rebalance_frequencies(
        strategy,
        price_points,
        benchmark_weights=benchmark_weights,
        initial_value=args.initial_value,
        annualization_periods=args.annualization,
        risk_free_rate=args.risk_free_rate,
    )
    contribution = contribution_report(strategy, price_points, annualization_periods=args.annualization)
    rolling_63 = rolling_metrics(
        backtest.portfolio_values,
        benchmark_values=backtest.benchmark_values,
        window=63,
        annualization_periods=args.annualization,
        risk_free_rate=args.risk_free_rate,
    )
    rolling_126 = rolling_metrics(
        backtest.portfolio_values,
        benchmark_values=backtest.benchmark_values,
        window=126,
        annualization_periods=args.annualization,
        risk_free_rate=args.risk_free_rate,
    )
    portfolio_returns = periodic_returns([point.value for point in backtest.portfolio_values])
    monte_carlo = tuple(
        run_historical_monte_carlo(
            portfolio_returns,
            HistoricalMonteCarloAssumptions(
                paths=args.mc_paths,
                periods=args.mc_periods,
                starting_value=args.initial_value,
                method=method,
            ),
        )
        for method in ("bootstrap", "block_bootstrap", "student_t")
    )
    suite = {
        "backtest": backtest,
        "rebalance_comparisons": comparisons,
        "contribution": contribution,
        "rolling_63": rolling_63,
        "rolling_126": rolling_126,
        "historical_monte_carlo": monte_carlo,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(format_research_suite_markdown(suite), encoding="utf-8")
    if args.json:
        print(json.dumps(to_jsonable(suite), indent=2, sort_keys=True))
    else:
        print_research_suite_report(suite)
        if args.report:
            print(f"\nWrote report: {args.report}")
    return 0


def run_download_prices(args: argparse.Namespace) -> int:
    strategy = selected_strategy(args)
    if args.tickers:
        tickers = [ticker.strip() for ticker in args.tickers.split(",") if ticker.strip()]
    else:
        tickers = sorted(strategy.symbols | {"VBIAX", "QQQ"})
    if args.provider == "yahoo-chart":
        download_yahoo_chart_prices(tickers, args.start, args.end, args.output)
    else:
        download_yfinance_prices(tickers, args.start, args.end, args.output)
    print(f"Wrote prices for {len(tickers)} ticker(s) to {args.output}")
    return 0


def run_review(args: argparse.Namespace) -> int:
    result = review_history(read_review_csv(args.history_csv))
    if args.json:
        print(json.dumps(to_jsonable(result), indent=2, sort_keys=True))
    else:
        print_review_report(result)
    return 0


def run_screen_adopters(args: argparse.Namespace) -> int:
    results = tuple(evaluate_adopter_metrics(metrics) for metrics in read_adopter_metrics_csv(args.metrics_csv))
    if args.json:
        print(json.dumps(to_jsonable(results), indent=2, sort_keys=True))
    else:
        print_adopter_screen(results)
    return 0


def read_positions_csv(path: Path) -> list[Position]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("Positions CSV must include headers.")
        rows = list(reader)

    positions: list[Position] = []
    for row_number, row in enumerate(rows, start=2):
        normalized = normalize_row(row)
        ticker = normalized.get("ticker") or normalized.get("symbol")
        if not ticker:
            raise ValueError(f"Row {row_number}: missing ticker.")

        market_value_text = normalized.get("market_value") or normalized.get("value")
        shares_text = normalized.get("shares")
        price_text = normalized.get("price")

        if market_value_text:
            market_value = parse_cash_amount(market_value_text)
            price = parse_optional_float(price_text, f"Row {row_number}: price")
            shares = parse_optional_float(shares_text, f"Row {row_number}: shares")
        elif shares_text and price_text:
            shares = parse_float(shares_text, f"Row {row_number}: shares")
            price = parse_float(price_text, f"Row {row_number}: price")
            market_value = shares * price
        else:
            raise ValueError(f"Row {row_number}: provide market_value or both shares and price.")

        positions.append(Position(ticker=ticker, market_value=market_value, shares=shares, price=price))

    return positions


def read_prices_csv(path: Path) -> list[PricePoint]:
    points: list[PricePoint] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("Prices CSV must include headers.")
        for row_number, row in enumerate(reader, start=2):
            normalized = normalize_row(row)
            day = parse_date(required(normalized, "date", row_number))
            ticker = normalized.get("ticker") or normalized.get("symbol")
            if not ticker:
                raise ValueError(f"Row {row_number}: missing ticker.")
            price_text = normalized.get("price") or normalized.get("adj_close") or normalized.get("close")
            if not price_text:
                raise ValueError(f"Row {row_number}: missing price.")
            points.append(PricePoint(day, ticker, parse_float(price_text, f"Row {row_number}: price")))
    return points


def read_review_csv(path: Path) -> list[ReviewObservation]:
    observations: list[ReviewObservation] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("Review CSV must include headers.")
        for row_number, row in enumerate(reader, start=2):
            normalized = normalize_row(row)
            day = parse_date(normalized.get("date", ""))
            portfolio_value = parse_float(required(normalized, "portfolio_value", row_number), f"Row {row_number}: portfolio_value")
            observations.append(
                ReviewObservation(
                    observation_date=day,
                    portfolio_value=portfolio_value,
                    benchmark_value=parse_optional_float(normalized.get("benchmark_value"), f"Row {row_number}: benchmark_value"),
                    satellite_value=parse_optional_float(normalized.get("satellite_value"), f"Row {row_number}: satellite_value"),
                    qqq_value=parse_optional_float(normalized.get("qqq_value"), f"Row {row_number}: qqq_value"),
                )
            )
    return observations


def read_adopter_metrics_csv(path: Path) -> list[AdopterMetrics]:
    metrics: list[AdopterMetrics] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("Adopter metrics CSV must include headers.")
        for row_number, row in enumerate(reader, start=2):
            normalized = normalize_row(row)
            ticker = required(normalized, "ticker", row_number)
            metrics.append(
                AdopterMetrics(
                    ticker=ticker,
                    it_capex_growth=parse_float(required(normalized, "it_capex_growth", row_number), f"Row {row_number}: it_capex_growth"),
                    sgna_intensity_change=parse_float(
                        required(normalized, "sgna_intensity_change", row_number),
                        f"Row {row_number}: sgna_intensity_change",
                    ),
                    gross_margin_expansion_bps=parse_float(
                        required(normalized, "gross_margin_expansion_bps", row_number),
                        f"Row {row_number}: gross_margin_expansion_bps",
                    ),
                )
            )
    return metrics


def required(row: dict[str, str], key: str, row_number: int) -> str:
    value = row.get(key)
    if value is None or value == "":
        raise ValueError(f"Row {row_number}: missing {key}.")
    return value


def normalize_row(row: dict[str, str]) -> dict[str, str]:
    return {key.strip().lower(): value.strip() for key, value in row.items() if key is not None and value is not None}


def parse_weight_map(value: str) -> dict[str, float]:
    if not value.strip():
        return {}
    weights: dict[str, float] = {}
    for item in value.split(","):
        if not item.strip():
            continue
        if ":" not in item:
            raise ValueError(f"Weight entry must use TICKER:WEIGHT format, got {item!r}.")
        symbol, weight = item.split(":", 1)
        weights[symbol.upper().strip()] = parse_float(weight.strip(), f"weight for {symbol.strip()}")
    return weights


def parse_proxy_map(value: str) -> dict[str, str]:
    if not value.strip():
        return {}
    mapping: dict[str, str] = {}
    for item in value.split(","):
        if not item.strip():
            continue
        if "=" not in item:
            raise ValueError(f"Proxy entry must use TARGET=PROXY format, got {item!r}.")
        target, proxy = item.split("=", 1)
        target_symbol = target.upper().strip()
        proxy_symbol = proxy.upper().strip()
        if not target_symbol or not proxy_symbol:
            raise ValueError(f"Proxy entry must include both target and proxy, got {item!r}.")
        mapping[target_symbol] = proxy_symbol
    return mapping


def parse_cash_amount(value: str) -> float:
    return parse_float(value, "amount")


def parse_float(value: str, field: str) -> float:
    try:
        return float(value.replace(",", "").replace("$", ""))
    except ValueError as exc:
        raise ValueError(f"{field} must be numeric, got {value!r}.") from exc


def parse_optional_float(value: str | None, field: str) -> float | None:
    if not value:
        return None
    return parse_float(value, field)


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD format") from exc


def print_text_report(result: AnalysisResult, strategy: HierarchicalStrategy) -> None:
    print(f"As of: {result.as_of.isoformat()}")
    print(f"Total value: {format_money(result.total_value)}")
    print(f"Expected return target: {format_pct(strategy.total_expected_return)}")
    print(f"Mode: {result.rebalance_mode}")
    print(
        "Satellite: "
        f"{format_pct(result.satellite_weight)} "
        f"(drift {format_signed_pct(result.satellite_drift)}; "
        f"boundary {'triggered' if result.boundary_triggered else 'not triggered'})"
    )
    if result.current_drawdown is not None:
        print(
            "Uncle point: "
            f"{format_signed_pct(result.current_drawdown)} drawdown; "
            f"circuit breaker {'triggered' if result.circuit_breaker_triggered else 'not triggered'}"
        )
    print(f"Calendar sweep: {'due' if result.calendar_sweep_due else 'not due'}")
    for note in result.review_notes:
        print(f"Review note: {note}")
    print()

    print("Buckets")
    print(f"{'Bucket':<12} {'Current':>14} {'Actual':>10} {'Target':>10} {'Drift':>10}")
    for bucket in result.buckets:
        print(
            f"{bucket.name:<12} "
            f"{format_money(bucket.current_value):>14} "
            f"{format_pct(bucket.current_weight):>10} "
            f"{format_pct(bucket.target_weight):>10} "
            f"{format_signed_pct(bucket.drift):>10}"
        )
    print()

    print("Orders")
    print(f"{'Ticker':<8} {'Side':<6} {'Current':>14} {'Target':>14} {'Trade':>14} {'Shares':>12}")
    for order in result.orders:
        shares = "" if order.share_delta is None else f"{order.share_delta:,.4f}"
        print(
            f"{order.ticker:<8} "
            f"{order.side:<6} "
            f"{format_money(order.current_value):>14} "
            f"{format_money(order.target_value):>14} "
            f"{format_money(order.trade_value):>14} "
            f"{shares:>12}"
        )


def print_dca_schedule(schedule: Any) -> None:
    print(f"Total cash: {format_money(schedule.total_cash)}")
    print(f"Initial defensive deployment: {format_pct(schedule.initial_deploy_pct)}")
    print(f"DCA months: {schedule.months}")
    print()
    print(f"{'Date':<12} {'Phase':<24} {'Ticker':<8} {'Amount':>14}")
    for allocation in schedule.allocations:
        print(
            f"{allocation.scheduled_date.isoformat():<12} "
            f"{allocation.phase:<24} "
            f"{allocation.ticker:<8} "
            f"{format_money(allocation.amount):>14}"
        )
    print(f"{'Total':<46} {format_money(schedule.total_allocated):>14}")


def print_stress_report(scenarios: Any, monte_carlo: Any) -> None:
    print("Scenario Stress")
    print(f"{'Scenario':<28} {'Return':>10} {'Value':>14} {'Sat Wt':>10} {'Mode':<16}")
    for result in scenarios:
        print(
            f"{result.name:<28} "
            f"{format_signed_pct(result.total_return):>10} "
            f"{format_money(result.total_value):>14} "
            f"{format_pct(result.satellite_weight):>10} "
            f"{result.rebalance_mode:<16}"
        )
    print()
    print("Monte Carlo")
    print(f"Paths: {monte_carlo.paths:,} over {monte_carlo.years} years")
    print(f"Median ending value: {format_money(monte_carlo.median_ending_value)}")
    print(f"5th / 95th ending value: {format_money(monte_carlo.percentile_5_ending_value)} / {format_money(monte_carlo.percentile_95_ending_value)}")
    print(f"Probability of loss: {format_pct(monte_carlo.probability_of_loss)}")
    print(f"Probability uncle point trips: {format_pct(monte_carlo.probability_circuit_breaker)}")
    print(f"Median max drawdown: {format_signed_pct(monte_carlo.median_max_drawdown)}")
    print(f"Average max drawdown: {format_signed_pct(monte_carlo.average_max_drawdown)}")


def print_backtest_report(result: Any) -> None:
    metrics = result.portfolio_metrics
    print("Backtest")
    print(f"Mode: {result.mode}")
    print(f"Window: {metrics.start_date.isoformat()} to {metrics.end_date.isoformat()} ({metrics.periods} return periods)")
    print(f"Initial / final value: {format_money(metrics.start_value)} / {format_money(metrics.end_value)}")
    print(f"Rebalance: {result.rebalance_frequency}")
    if result.skipped_dates:
        print(f"Skipped incomplete price dates: {len(result.skipped_dates)}")
    print()
    print("Portfolio Metrics")
    print(f"Total return: {format_signed_pct(metrics.total_return)}")
    print(f"CAGR: {format_signed_pct(metrics.cagr)}")
    print(f"Annualized volatility: {format_pct(metrics.annualized_volatility)}")
    print(f"Sharpe: {format_ratio(metrics.sharpe_ratio)}")
    print(f"Sortino: {format_ratio(metrics.sortino_ratio)}")
    print(f"Calmar: {format_ratio(metrics.calmar_ratio)}")
    print(f"Max drawdown: {format_signed_pct(metrics.max_drawdown)}")
    print(
        "Drawdown window: "
        f"{metrics.drawdown_peak_date.isoformat()} to {metrics.drawdown_trough_date.isoformat()}"
        f"{'' if metrics.drawdown_recovery_date is None else ' recovered ' + metrics.drawdown_recovery_date.isoformat()}"
    )
    print(f"VaR 95%: {format_signed_pct(metrics.var_95)}")
    print(f"CVaR 95%: {format_signed_pct(metrics.cvar_95)}")
    print(f"Best / worst period: {format_signed_pct(metrics.best_period_return)} / {format_signed_pct(metrics.worst_period_return)}")
    print(f"Positive period rate: {format_pct(metrics.positive_period_rate)}")

    if result.benchmark_metrics is not None and result.relative_metrics is not None:
        benchmark = result.benchmark_metrics
        relative = result.relative_metrics
        print()
        print("Benchmark Metrics")
        print(f"Benchmark total return: {format_signed_pct(benchmark.total_return)}")
        print(f"Benchmark CAGR: {format_signed_pct(benchmark.cagr)}")
        print(f"Benchmark volatility: {format_pct(benchmark.annualized_volatility)}")
        print(f"Benchmark max drawdown: {format_signed_pct(benchmark.max_drawdown)}")
        print()
        print("Relative Metrics")
        print(f"Active return: {format_signed_pct(relative.active_return)}")
        print(f"Tracking error: {format_pct(relative.tracking_error or 0.0) if relative.tracking_error is not None else 'n/a'}")
        print(f"Information ratio: {format_ratio(relative.information_ratio)}")
        print(f"Beta: {format_ratio(relative.beta)}")
        print(f"Correlation: {format_ratio(relative.correlation)}")


def print_research_suite_report(suite: dict[str, Any]) -> None:
    print_backtest_report(suite["backtest"])
    print()
    print("Rebalance Comparison")
    print(f"{'Freq':<10} {'Return':>10} {'CAGR':>10} {'Vol':>10} {'Sharpe':>8} {'MDD':>10} {'Active':>10} {'IR':>8}")
    for row in suite["rebalance_comparisons"]:
        print(
            f"{row.frequency:<10} "
            f"{format_signed_pct(row.total_return):>10} "
            f"{format_signed_pct(row.cagr):>10} "
            f"{format_pct(row.annualized_volatility):>10} "
            f"{format_ratio(row.sharpe_ratio):>8} "
            f"{format_signed_pct(row.max_drawdown):>10} "
            f"{format_signed_pct(row.active_return):>10} "
            f"{format_ratio(row.information_ratio):>8}"
        )
    print()
    print("Rolling Diagnostics")
    print_latest_rolling("63-period", suite["rolling_63"])
    print_latest_rolling("126-period", suite["rolling_126"])
    print()
    print("Bucket Contribution")
    print(f"{'Bucket':<12} {'Weight':>10} {'Return Ctr':>12} {'Ann Ctr':>12} {'Vol Ctr':>10}")
    for row in suite["contribution"].bucket_contributions:
        print(
            f"{row.bucket:<12} "
            f"{format_pct(row.weight):>10} "
            f"{format_signed_pct(row.arithmetic_return_contribution):>12} "
            f"{format_signed_pct(row.annualized_return_contribution):>12} "
            f"{format_pct(row.volatility_contribution or 0.0):>10}"
        )
    print()
    print("Historical Monte Carlo")
    print(f"{'Method':<16} {'Median':>14} {'P5':>14} {'P95':>14} {'Loss %':>10} {'Med MDD':>10}")
    for row in suite["historical_monte_carlo"]:
        print(
            f"{row.method:<16} "
            f"{format_money(row.median_ending_value):>14} "
            f"{format_money(row.percentile_5_ending_value):>14} "
            f"{format_money(row.percentile_95_ending_value):>14} "
            f"{format_pct(row.probability_of_loss):>10} "
            f"{format_signed_pct(row.median_max_drawdown):>10}"
        )


def print_latest_rolling(label: str, rows: Any) -> None:
    if not rows:
        print(f"{label}: not enough observations")
        return
    latest = rows[-1]
    print(
        f"{label}: {latest.observation_date.isoformat()} "
        f"return {format_signed_pct(latest.total_return)}, "
        f"vol {format_pct(latest.annualized_volatility)}, "
        f"Sharpe {format_ratio(latest.sharpe_ratio)}, "
        f"corr {format_ratio(latest.correlation)}"
    )


def format_research_suite_markdown(suite: dict[str, Any]) -> str:
    backtest = suite["backtest"]
    metrics = backtest.portfolio_metrics
    lines = [
        "# Research Suite",
        "",
        f"Mode: {backtest.mode}",
        f"Window: {metrics.start_date.isoformat()} to {metrics.end_date.isoformat()}",
        f"Return periods: {metrics.periods}",
        f"Rebalance: {backtest.rebalance_frequency}",
        "",
        "## Portfolio Metrics",
        "",
        "| Metric | Result |",
        "| --- | ---: |",
        f"| Total return | {format_signed_pct(metrics.total_return)} |",
        f"| CAGR | {format_signed_pct(metrics.cagr)} |",
        f"| Volatility | {format_pct(metrics.annualized_volatility)} |",
        f"| Sharpe | {format_ratio(metrics.sharpe_ratio)} |",
        f"| Sortino | {format_ratio(metrics.sortino_ratio)} |",
        f"| Max drawdown | {format_signed_pct(metrics.max_drawdown)} |",
        f"| VaR 95% | {format_signed_pct(metrics.var_95)} |",
        f"| CVaR 95% | {format_signed_pct(metrics.cvar_95)} |",
        "",
        "## Rebalance Comparison",
        "",
        "| Frequency | Return | CAGR | Volatility | Sharpe | Max Drawdown | Active | IR |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in suite["rebalance_comparisons"]:
        lines.append(
            f"| {row.frequency} | {format_signed_pct(row.total_return)} | {format_signed_pct(row.cagr)} | "
            f"{format_pct(row.annualized_volatility)} | {format_ratio(row.sharpe_ratio)} | "
            f"{format_signed_pct(row.max_drawdown)} | {format_signed_pct(row.active_return)} | "
            f"{format_ratio(row.information_ratio)} |"
        )
    lines.extend([
        "",
        "## Rolling Diagnostics",
        "",
        rolling_markdown_line("63-period", suite["rolling_63"]),
        rolling_markdown_line("126-period", suite["rolling_126"]),
        "",
        "## Bucket Contribution",
        "",
        "| Bucket | Weight | Return Contribution | Annualized Contribution | Vol Contribution |",
        "| --- | ---: | ---: | ---: | ---: |",
    ])
    for row in suite["contribution"].bucket_contributions:
        lines.append(
            f"| {row.bucket} | {format_pct(row.weight)} | {format_signed_pct(row.arithmetic_return_contribution)} | "
            f"{format_signed_pct(row.annualized_return_contribution)} | {format_pct(row.volatility_contribution or 0.0)} |"
        )
    lines.extend([
        "",
        "## Historical Monte Carlo",
        "",
        "| Method | Median | P5 | P95 | Probability of Loss | Median Max Drawdown |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ])
    for row in suite["historical_monte_carlo"]:
        lines.append(
            f"| {row.method} | {format_money(row.median_ending_value)} | {format_money(row.percentile_5_ending_value)} | "
            f"{format_money(row.percentile_95_ending_value)} | {format_pct(row.probability_of_loss)} | "
            f"{format_signed_pct(row.median_max_drawdown)} |"
        )
    lines.append("")
    return "\n".join(lines)


def rolling_markdown_line(label: str, rows: Any) -> str:
    if not rows:
        return f"- {label}: not enough observations."
    latest = rows[-1]
    return (
        f"- {label}: as of {latest.observation_date.isoformat()}, return {format_signed_pct(latest.total_return)}, "
        f"volatility {format_pct(latest.annualized_volatility)}, Sharpe {format_ratio(latest.sharpe_ratio)}, "
        f"benchmark correlation {format_ratio(latest.correlation)}."
    )


def print_review_report(result: Any) -> None:
    print(f"Review window: {result.start_date.isoformat()} to {result.end_date.isoformat()}")
    print(f"Portfolio return: {format_signed_pct(result.portfolio_return)}")
    if result.benchmark_return is not None:
        print(f"Benchmark return: {format_signed_pct(result.benchmark_return)}")
        print(f"Active return: {format_signed_pct(result.active_return)}")
    print(f"Max drawdown: {format_signed_pct(result.max_drawdown)}")
    print(f"Circuit breaker: {'triggered' if result.circuit_breaker_triggered else 'not triggered'}")
    if result.satellite_relative_strength is not None:
        print(f"Satellite vs QQQ relative strength: {format_signed_pct(result.satellite_relative_strength)}")
    for flag in result.review_flags:
        print(f"Flag: {flag}")


def print_adopter_screen(results: Any) -> None:
    print(f"{'Ticker':<8} {'Pass':<6} {'Score':>5} {'Capex':>8} {'SG&A':>8} {'Margin':>8}")
    for result in results:
        print(
            f"{result.ticker:<8} "
            f"{'yes' if result.passed else 'no':<6} "
            f"{result.score:>5} "
            f"{'yes' if result.it_capex_growth_passed else 'no':>8} "
            f"{'yes' if result.sgna_intensity_passed else 'no':>8} "
            f"{'yes' if result.gross_margin_passed else 'no':>8}"
        )


def to_jsonable(value: Any) -> Any:
    if isinstance(value, date):
        return value.isoformat()
    if is_dataclass(value):
        return {key: to_jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, tuple | list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    return value


def format_money(value: float) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.2f}"


def format_pct(value: float) -> str:
    return f"{value * 100:,.2f}%"


def format_ratio(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:,.2f}"


def format_signed_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    sign = "+" if value >= 0 else "-"
    return f"{sign}{abs(value) * 100:,.2f}%"


if __name__ == "__main__":
    raise SystemExit(main())
