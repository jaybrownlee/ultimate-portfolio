from datetime import date
import unittest

from ultimate_portfolio.dca import build_dca_schedule
from ultimate_portfolio.risk import (
    AdopterMetrics,
    MonteCarloAssumptions,
    ReviewObservation,
    evaluate_adopter_metrics,
    review_history,
    run_monte_carlo,
    run_stress_scenarios,
)
from ultimate_portfolio.strategy import DEFAULT_STRATEGY, Position


class OperationsTests(unittest.TestCase):
    def test_dca_schedule_reaches_total_target_weights(self) -> None:
        schedule = build_dca_schedule(DEFAULT_STRATEGY, 100000, date(2026, 5, 7), months=6)
        totals: dict[str, float] = {}
        for allocation in schedule.allocations:
            totals[allocation.ticker] = totals.get(allocation.ticker, 0.0) + allocation.amount

        self.assertAlmostEqual(schedule.total_allocated, 100000, places=2)
        for symbol, weight in DEFAULT_STRATEGY.total_target_weights().items():
            self.assertAlmostEqual(totals[symbol], 100000 * weight, places=2)

    def test_adopter_screen_requires_two_of_three(self) -> None:
        passing = evaluate_adopter_metrics(AdopterMetrics("WMT", 0.12, -0.003, 40))
        failing = evaluate_adopter_metrics(AdopterMetrics("DE", 0.09, 0.001, 40))

        self.assertTrue(passing.passed)
        self.assertEqual(passing.score, 2)
        self.assertFalse(failing.passed)

    def test_review_history_flags_circuit_breaker(self) -> None:
        result = review_history(
            [
                ReviewObservation(date(2026, 1, 31), 100000, 100000, 20000, 100000),
                ReviewObservation(date(2026, 2, 28), 79000, 90000, 13000, 94000),
            ]
        )

        self.assertTrue(result.circuit_breaker_triggered)
        self.assertLessEqual(result.max_drawdown, -0.20)
        self.assertTrue(result.review_flags)

    def test_stress_scenarios_return_all_default_shocks(self) -> None:
        results = run_stress_scenarios(DEFAULT_STRATEGY, aligned_positions(), date(2026, 5, 7))

        self.assertEqual(len(results), 4)
        self.assertTrue(all(result.total_value > 0 for result in results))

    def test_monte_carlo_is_deterministic_with_seed(self) -> None:
        assumptions = MonteCarloAssumptions(paths=100, years=2, starting_value=100000, seed=42)
        first = run_monte_carlo(DEFAULT_STRATEGY, assumptions)
        second = run_monte_carlo(DEFAULT_STRATEGY, assumptions)

        self.assertEqual(first, second)
        self.assertEqual(first.paths, 100)
        self.assertEqual(first.years, 2)


def aligned_positions() -> list[Position]:
    return [
        Position("COWZ", 28000),
        Position("WMT", 4000),
        Position("JPM", 4000),
        Position("DE", 4000),
        Position("DBMF", 20000),
        Position("SGOV", 10000),
        Position("TLT", 10000),
        Position("SPRX", 8000),
        Position("ARKQ", 7000),
        Position("ELFY", 3000),
        Position("BAI", 2000),
    ]


if __name__ == "__main__":
    unittest.main()
