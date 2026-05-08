from datetime import date
import unittest

from ultimate_portfolio.data import normalize_tickers, unix_timestamp
from ultimate_portfolio.research import (
    HistoricalMonteCarloAssumptions,
    PricePoint,
    ValuePoint,
    apply_proxy_map,
    calculate_performance_metrics,
    calculate_relative_metrics,
    compare_rebalance_frequencies,
    contribution_report,
    periodic_returns,
    rolling_metrics,
    run_historical_monte_carlo,
    run_weighted_backtest,
)
from ultimate_portfolio.strategy import DEFAULT_STRATEGY


class ResearchTests(unittest.TestCase):
    def test_data_helpers_normalize_tickers_and_dates(self) -> None:
        self.assertEqual(normalize_tickers([" cowz ", "COWZ", "qqq"]), ["COWZ", "QQQ"])
        self.assertEqual(unix_timestamp(date(1970, 1, 2)), 86400)

    def test_performance_metrics_include_drawdown_and_ratios(self) -> None:
        values = (
            ValuePoint(date(2026, 1, 31), 100.0),
            ValuePoint(date(2026, 2, 28), 110.0),
            ValuePoint(date(2026, 3, 31), 99.0),
            ValuePoint(date(2026, 4, 30), 120.0),
        )

        metrics = calculate_performance_metrics(values, annualization_periods=12, risk_free_rate=0.0)

        self.assertAlmostEqual(metrics.total_return, 0.20)
        self.assertAlmostEqual(metrics.max_drawdown, -0.10)
        self.assertEqual(metrics.drawdown_peak_date, date(2026, 2, 28))
        self.assertEqual(metrics.drawdown_trough_date, date(2026, 3, 31))
        self.assertEqual(metrics.drawdown_recovery_date, date(2026, 4, 30))
        self.assertIsNotNone(metrics.sharpe_ratio)
        self.assertIsNotNone(metrics.sortino_ratio)
        self.assertLess(metrics.cvar_95, 0)

    def test_backtest_runs_weighted_allocation_and_benchmark(self) -> None:
        prices = [
            PricePoint(date(2026, 1, 31), "A", 100),
            PricePoint(date(2026, 1, 31), "B", 100),
            PricePoint(date(2026, 1, 31), "BMK", 100),
            PricePoint(date(2026, 2, 28), "A", 110),
            PricePoint(date(2026, 2, 28), "B", 100),
            PricePoint(date(2026, 2, 28), "BMK", 102),
            PricePoint(date(2026, 3, 31), "A", 121),
            PricePoint(date(2026, 3, 31), "B", 100),
            PricePoint(date(2026, 3, 31), "BMK", 104),
        ]

        result = run_weighted_backtest(
            prices,
            {"A": 0.5, "B": 0.5},
            benchmark_weights={"BMK": 1.0},
            initial_value=1000,
            rebalance_frequency="none",
            annualization_periods=12,
        )

        self.assertAlmostEqual(result.portfolio_values[-1].value, 1105.0)
        self.assertAlmostEqual(result.benchmark_values[-1].value, 1040.0)
        self.assertIsNotNone(result.relative_metrics)
        self.assertGreater(result.relative_metrics.active_return, 0)
        self.assertEqual(result.skipped_dates, ())

    def test_backtest_skips_incomplete_dates(self) -> None:
        prices = [
            PricePoint(date(2026, 1, 31), "A", 100),
            PricePoint(date(2026, 1, 31), "B", 100),
            PricePoint(date(2026, 2, 28), "A", 110),
            PricePoint(date(2026, 3, 31), "A", 120),
            PricePoint(date(2026, 3, 31), "B", 100),
        ]

        result = run_weighted_backtest(
            prices,
            {"A": 0.5, "B": 0.5},
            initial_value=1000,
            rebalance_frequency="quarterly",
            annualization_periods=12,
        )

        self.assertEqual(result.skipped_dates, (date(2026, 2, 28),))
        self.assertEqual(len(result.portfolio_values), 2)

    def test_relative_metrics_report_beta_and_correlation(self) -> None:
        portfolio = (
            ValuePoint(date(2026, 1, 31), 100),
            ValuePoint(date(2026, 2, 28), 102),
            ValuePoint(date(2026, 3, 31), 101),
            ValuePoint(date(2026, 4, 30), 104),
        )
        benchmark = (
            ValuePoint(date(2026, 1, 31), 100),
            ValuePoint(date(2026, 2, 28), 101),
            ValuePoint(date(2026, 3, 31), 100),
            ValuePoint(date(2026, 4, 30), 102),
        )

        relative = calculate_relative_metrics(portfolio, benchmark, annualization_periods=12)

        self.assertIsNotNone(relative.beta)
        self.assertIsNotNone(relative.correlation)
        self.assertGreater(relative.active_return, 0)

    def test_proxy_map_relabels_proxy_prices_to_target_symbols(self) -> None:
        mapped = apply_proxy_map(
            [
                PricePoint(date(2026, 1, 31), "QQQ", 100),
                PricePoint(date(2026, 1, 31), "COWZ", 100),
            ],
            {"BAI": "QQQ"},
        )

        self.assertEqual([point.symbol for point in mapped], ["QQQ", "BAI", "COWZ"])

    def test_rolling_metrics_reports_latest_window(self) -> None:
        values = tuple(ValuePoint(date(2026, 1, day), 100 + day) for day in range(1, 8))
        benchmark = tuple(ValuePoint(date(2026, 1, day), 100 + day * 0.5) for day in range(1, 8))

        rows = rolling_metrics(values, benchmark_values=benchmark, window=3, annualization_periods=252)

        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[-1].observation_date, date(2026, 1, 7))
        self.assertIsNotNone(rows[-1].correlation)

    def test_compare_rebalance_frequencies_returns_requested_modes(self) -> None:
        prices = strategy_price_points()

        rows = compare_rebalance_frequencies(
            DEFAULT_STRATEGY,
            prices,
            frequencies=("none", "quarterly"),
            annualization_periods=12,
        )

        self.assertEqual([row.frequency for row in rows], ["none", "quarterly"])
        self.assertTrue(all(row.total_return > 0 for row in rows))

    def test_contribution_report_groups_by_bucket(self) -> None:
        report = contribution_report(DEFAULT_STRATEGY, strategy_price_points(), annualization_periods=12)

        buckets = {row.bucket: row for row in report.bucket_contributions}
        self.assertIn("core", buckets)
        self.assertIn("satellite", buckets)
        self.assertAlmostEqual(buckets["core"].weight + buckets["satellite"].weight, 1.0)

    def test_historical_monte_carlo_is_deterministic(self) -> None:
        returns = periodic_returns([100, 101, 99, 102, 103, 100])
        assumptions = HistoricalMonteCarloAssumptions(paths=50, periods=12, seed=123, method="block_bootstrap")

        first = run_historical_monte_carlo(returns, assumptions)
        second = run_historical_monte_carlo(returns, assumptions)

        self.assertEqual(first, second)
        self.assertEqual(first.method, "block_bootstrap")


def strategy_price_points() -> list[PricePoint]:
    prices: list[PricePoint] = []
    start_prices = {
        "COWZ": 100,
        "WMT": 100,
        "JPM": 100,
        "DE": 100,
        "DBMF": 100,
        "SGOV": 100,
        "TLT": 100,
        "SPRX": 100,
        "ARKQ": 100,
        "ELFY": 100,
        "BAI": 100,
    }
    end_prices = {
        "COWZ": 106,
        "WMT": 105,
        "JPM": 104,
        "DE": 103,
        "DBMF": 102,
        "SGOV": 101,
        "TLT": 99,
        "SPRX": 112,
        "ARKQ": 110,
        "ELFY": 109,
        "BAI": 108,
    }
    for symbol, price in start_prices.items():
        prices.append(PricePoint(date(2026, 1, 31), symbol, price))
    for symbol, price in end_prices.items():
        prices.append(PricePoint(date(2026, 2, 28), symbol, price))
    return prices


if __name__ == "__main__":
    unittest.main()
