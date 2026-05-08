from datetime import date
import unittest

from ultimate_portfolio.assessment import (
    AssetUniverseItem,
    run_candidate_screen,
    run_candidate_tests,
    run_daily_check,
    run_monthly_assessment,
    run_quarterly_review,
)
from ultimate_portfolio.research import PricePoint
from ultimate_portfolio.strategy import DEFAULT_STRATEGY, Position


class AssessmentTests(unittest.TestCase):
    def test_daily_check_is_clear_when_no_trigger_fires(self) -> None:
        check = run_daily_check(DEFAULT_STRATEGY, aligned_positions(), date(2026, 5, 8), peak_value=1000)

        self.assertEqual(check.status, "clear")
        self.assertFalse(check.analysis.boundary_triggered)
        self.assertFalse(check.analysis.circuit_breaker_triggered)
        self.assertTrue(any(flag.topic == "process" for flag in check.flags))

    def test_daily_check_warns_near_boundary_before_rebalance_trigger(self) -> None:
        check = run_daily_check(
            DEFAULT_STRATEGY,
            [Position("COWZ", 754), Position("SPRX", 246)],
            date(2026, 5, 8),
            peak_value=1000,
        )

        self.assertEqual(check.status, "watch")
        self.assertFalse(check.analysis.boundary_triggered)
        self.assertTrue(any(flag.topic == "master_boundary_warning" for flag in check.flags))

    def test_daily_check_requires_action_when_boundary_fires(self) -> None:
        check = run_daily_check(
            DEFAULT_STRATEGY,
            [Position("COWZ", 750), Position("SPRX", 250)],
            date(2026, 5, 8),
            peak_value=1000,
        )

        self.assertEqual(check.status, "action_required")
        self.assertTrue(check.analysis.boundary_triggered)
        self.assertTrue(any(flag.topic == "master_boundary" for flag in check.flags))

    def test_monthly_assessment_returns_flags_and_action(self) -> None:
        assessment = run_monthly_assessment(
            DEFAULT_STRATEGY,
            aligned_positions(),
            price_points_with_candidates(),
            date(2026, 5, 7),
            benchmark_weights={"QQQ": 1.0},
            annualization_periods=12,
        )

        self.assertTrue(assessment.flags)
        self.assertTrue(assessment.recommended_action)
        self.assertEqual(assessment.analysis.rebalance_mode, "hold")
        self.assertAlmostEqual(sum(row.portfolio_weight for row in assessment.recommended_portfolio), 1.0)
        self.assertEqual(assessment.recommended_portfolio[0].ticker, "COWZ")
        self.assertAlmostEqual(assessment.recommended_portfolio[0].portfolio_weight, 0.28)

    def test_candidate_tests_classify_same_role_replacement(self) -> None:
        results = run_candidate_tests(
            DEFAULT_STRATEGY,
            price_points_with_candidates(),
            [
                AssetUniverseItem("SMH", "semis_hardware", "satellite", "SPRX", 0, 0.08),
                AssetUniverseItem("MISSING", "semis_hardware", "satellite", "SPRX", 0, 0.08),
            ],
            benchmark_weights={"QQQ": 1.0},
            annualization_periods=12,
        )

        self.assertEqual(len(results), 2)
        self.assertIn(results[0].status, {"pass", "watch", "reject"})
        self.assertEqual(results[1].status, "no_data")

    def test_candidate_screen_scores_incumbents_and_challengers(self) -> None:
        report = run_candidate_screen(
            DEFAULT_STRATEGY,
            price_points_with_candidates(),
            [
                AssetUniverseItem("COWZ", "fcf_value_anchor", "core", "", 0.20, 0.35),
                AssetUniverseItem("SMH", "semis_hardware", "satellite", "SPRX", 0, 0.08),
                AssetUniverseItem("MISSING", "semis_hardware", "satellite", "SPRX", 0, 0.08),
            ],
            benchmark_symbol="QQQ",
            benchmark_weights={"QQQ": 1.0},
            annualization_periods=12,
            windows=(1, 2),
        )

        rows = {row.ticker: row for row in report.rows}
        self.assertEqual(report.as_of, date(2026, 3, 31))
        self.assertEqual(rows["COWZ"].candidate_type, "incumbent")
        self.assertEqual(rows["SMH"].replace_for, "SPRX")
        self.assertIn(rows["SMH"].priority, {"high", "watch", "reject"})
        self.assertIsNotNone(rows["SMH"].correlation_to_incumbent)
        self.assertTrue(rows["SMH"].reason_codes)
        self.assertEqual(rows["MISSING"].priority, "no_data")
        self.assertIn("insufficient_price_history", rows["MISSING"].reason_codes)
        summary_by_role = {summary.role: summary for summary in report.summaries}
        self.assertIn("semis_hardware", summary_by_role)
        self.assertEqual(summary_by_role["semis_hardware"].best_challenger, "SMH")
        self.assertTrue(summary_by_role["semis_hardware"].recommended_action)
        self.assertTrue(summary_by_role["semis_hardware"].reason_codes)

    def test_quarterly_review_forces_sweep_and_includes_checklist(self) -> None:
        review = run_quarterly_review(
            DEFAULT_STRATEGY,
            aligned_positions(),
            price_points_with_candidates(),
            [AssetUniverseItem("SMH", "semis_hardware", "satellite", "SPRX", 0, 0.08)],
            date(2026, 5, 7),
            benchmark_weights={"QQQ": 1.0},
            annualization_periods=12,
        )

        self.assertEqual(review.monthly_assessment.analysis.rebalance_mode, "internal")
        self.assertTrue(review.candidate_tests)
        self.assertTrue(review.decision_checklist)


def aligned_positions() -> list[Position]:
    return [
        Position("COWZ", 280),
        Position("WMT", 40),
        Position("JPM", 40),
        Position("DE", 40),
        Position("DBMF", 200),
        Position("SGOV", 100),
        Position("TLT", 100),
        Position("SPRX", 80),
        Position("ARKQ", 70),
        Position("ELFY", 30),
        Position("BAI", 20),
    ]


def price_points_with_candidates() -> list[PricePoint]:
    series = {
        "COWZ": (100, 106, 108),
        "WMT": (100, 102, 104),
        "JPM": (100, 103, 104),
        "DE": (100, 101, 103),
        "DBMF": (100, 101, 102),
        "SGOV": (100, 100.5, 101),
        "TLT": (100, 99, 100),
        "SPRX": (100, 110, 112),
        "ARKQ": (100, 107, 109),
        "ELFY": (100, 105, 108),
        "BAI": (100, 106, 107),
        "SMH": (100, 112, 116),
        "QQQ": (100, 106, 108),
    }
    days = (date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31))
    points: list[PricePoint] = []
    for ticker, prices in series.items():
        for day, price in zip(days, prices):
            points.append(PricePoint(day, ticker, price))
    return points


if __name__ == "__main__":
    unittest.main()
