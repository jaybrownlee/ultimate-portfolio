from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, is_dataclass
from datetime import date
import json
import sys
from pathlib import Path
from typing import Any

from .dca import build_dca_schedule
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
    except (OSError, ValueError) as exc:
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


def format_signed_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    sign = "+" if value >= 0 else "-"
    return f"{sign}{abs(value) * 100:,.2f}%"


if __name__ == "__main__":
    raise SystemExit(main())
