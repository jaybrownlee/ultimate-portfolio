from datetime import date
import unittest

from ultimate_portfolio.strategy import DEFAULT_STRATEGY, Position, build_default_strategy, is_calendar_quarter_end


class HierarchicalStrategyTests(unittest.TestCase):
    def test_default_targets_match_full_system_weights(self) -> None:
        targets = DEFAULT_STRATEGY.total_target_weights()

        self.assertAlmostEqual(targets["COWZ"], 0.28)
        self.assertAlmostEqual(targets["WMT"], 0.04)
        self.assertAlmostEqual(targets["JPM"], 0.04)
        self.assertAlmostEqual(targets["DE"], 0.04)
        self.assertAlmostEqual(targets["DBMF"], 0.20)
        self.assertAlmostEqual(targets["SGOV"], 0.10)
        self.assertAlmostEqual(targets["TLT"], 0.10)
        self.assertAlmostEqual(targets["SPRX"], 0.08)
        self.assertAlmostEqual(targets["ARKQ"], 0.07)
        self.assertAlmostEqual(targets["ELFY"], 0.03)
        self.assertAlmostEqual(targets["BAI"], 0.02)
        self.assertAlmostEqual(sum(targets.values()), 1.0)
        self.assertAlmostEqual(DEFAULT_STRATEGY.total_expected_return, 0.1466)

    def test_stagflation_overlay_sources_gldm_from_sgov_and_tlt(self) -> None:
        targets = build_default_strategy(stagflation_overlay=True).total_target_weights()

        self.assertAlmostEqual(targets["GLDM"], 0.04)
        self.assertAlmostEqual(targets["SGOV"], 0.08)
        self.assertAlmostEqual(targets["TLT"], 0.08)
        self.assertAlmostEqual(sum(targets.values()), 1.0)

    def test_hold_when_no_boundary_or_calendar_trigger(self) -> None:
        result = DEFAULT_STRATEGY.analyze(aligned_positions(), date(2026, 5, 7))

        self.assertEqual(result.rebalance_mode, "hold")
        self.assertFalse(result.boundary_triggered)
        self.assertFalse(result.calendar_sweep_due)
        self.assertFalse(result.has_trades)

    def test_boundary_rebalance_preserves_internal_bucket_proportions(self) -> None:
        result = DEFAULT_STRATEGY.analyze(
            [
                Position("COWZ", 300),
                Position("WMT", 40),
                Position("JPM", 35),
                Position("DE", 35),
                Position("DBMF", 190),
                Position("SGOV", 80),
                Position("TLT", 70),
                Position("SPRX", 150),
                Position("ARKQ", 50),
                Position("ELFY", 25),
                Position("BAI", 25),
            ],
            date(2026, 5, 7),
        )

        self.assertEqual(result.rebalance_mode, "boundary")
        self.assertTrue(result.boundary_triggered)

        targets = {order.ticker: order.target_value for order in result.orders}
        core_target = sum(targets[symbol] for symbol in ("COWZ", "WMT", "JPM", "DE", "DBMF", "SGOV", "TLT"))
        satellite_target = sum(targets[symbol] for symbol in ("SPRX", "ARKQ", "ELFY", "BAI"))

        self.assertAlmostEqual(core_target, 800.0)
        self.assertAlmostEqual(satellite_target, 200.0)
        self.assertAlmostEqual(targets["SPRX"], 120.0)
        self.assertAlmostEqual(targets["ARKQ"], 40.0)
        self.assertAlmostEqual(targets["ELFY"], 20.0)
        self.assertAlmostEqual(targets["BAI"], 20.0)

    def test_internal_sweep_keeps_current_bucket_values(self) -> None:
        result = DEFAULT_STRATEGY.analyze(
            [
                Position("COWZ", 400),
                Position("WMT", 20),
                Position("JPM", 20),
                Position("DE", 20),
                Position("DBMF", 180),
                Position("SGOV", 80),
                Position("TLT", 80),
                Position("SPRX", 20),
                Position("ARKQ", 120),
                Position("ELFY", 40),
                Position("BAI", 20),
            ],
            date(2026, 5, 7),
            force_sweep=True,
        )

        self.assertEqual(result.rebalance_mode, "internal")
        targets = {order.ticker: order.target_value for order in result.orders}

        self.assertAlmostEqual(targets["COWZ"], 280.0)
        self.assertAlmostEqual(targets["WMT"], 40.0)
        self.assertAlmostEqual(targets["JPM"], 40.0)
        self.assertAlmostEqual(targets["DE"], 40.0)
        self.assertAlmostEqual(targets["DBMF"], 200.0)
        self.assertAlmostEqual(targets["SGOV"], 100.0)
        self.assertAlmostEqual(targets["TLT"], 100.0)
        self.assertAlmostEqual(targets["SPRX"], 80.0)
        self.assertAlmostEqual(targets["ARKQ"], 70.0)
        self.assertAlmostEqual(targets["ELFY"], 30.0)
        self.assertAlmostEqual(targets["BAI"], 20.0)

    def test_boundary_and_quarterly_sweep_becomes_full_rebalance(self) -> None:
        result = DEFAULT_STRATEGY.analyze(
            [
                Position("COWZ", 300),
                Position("WMT", 40),
                Position("JPM", 35),
                Position("DE", 35),
                Position("DBMF", 190),
                Position("SGOV", 80),
                Position("TLT", 70),
                Position("SPRX", 150),
                Position("ARKQ", 50),
                Position("ELFY", 25),
                Position("BAI", 25),
            ],
            date(2026, 6, 30),
        )

        self.assertEqual(result.rebalance_mode, "full")
        targets = {order.ticker: order.target_value for order in result.orders}
        self.assertAlmostEqual(targets["COWZ"], 280.0)
        self.assertAlmostEqual(targets["WMT"], 40.0)
        self.assertAlmostEqual(targets["SPRX"], 80.0)

    def test_circuit_breaker_moves_satellite_to_sgov(self) -> None:
        result = DEFAULT_STRATEGY.analyze(aligned_positions(), date(2026, 5, 7), peak_value=1300)

        self.assertEqual(result.rebalance_mode, "circuit_breaker")
        self.assertTrue(result.circuit_breaker_triggered)
        targets = {order.ticker: order.target_value for order in result.orders}
        self.assertAlmostEqual(targets["SPRX"], 0.0)
        self.assertAlmostEqual(targets["ARKQ"], 0.0)
        self.assertAlmostEqual(targets["ELFY"], 0.0)
        self.assertAlmostEqual(targets["BAI"], 0.0)
        self.assertAlmostEqual(targets["SGOV"], 300.0)

    def test_quarter_end_detection(self) -> None:
        self.assertTrue(is_calendar_quarter_end(date(2026, 6, 30)))
        self.assertFalse(is_calendar_quarter_end(date(2026, 6, 29)))

    def test_exact_threshold_triggers_boundary(self) -> None:
        result = DEFAULT_STRATEGY.analyze(
            [
                Position("COWZ", 750),
                Position("SPRX", 250),
            ],
            date(2026, 5, 7),
        )

        self.assertTrue(result.boundary_triggered)
        self.assertEqual(result.rebalance_mode, "boundary")


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


if __name__ == "__main__":
    unittest.main()
