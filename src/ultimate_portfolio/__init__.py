"""Ultimate Portfolio strategy automation."""

from .dca import DcaAllocation, DcaSchedule, build_dca_schedule
from .risk import (
    AdopterMetrics,
    MonteCarloAssumptions,
    MonteCarloResult,
    MonthlyReviewResult,
    StressResult,
    evaluate_adopter_metrics,
    review_history,
    run_monte_carlo,
    run_stress_scenarios,
)
from .strategy import (
    AnalysisResult,
    BucketAllocation,
    BucketConfig,
    DEFAULT_STRATEGY,
    HierarchicalStrategy,
    Position,
    TradeOrder,
    build_default_strategy,
)

__all__ = [
    "AdopterMetrics",
    "AnalysisResult",
    "BucketAllocation",
    "BucketConfig",
    "DEFAULT_STRATEGY",
    "DcaAllocation",
    "DcaSchedule",
    "HierarchicalStrategy",
    "MonteCarloAssumptions",
    "MonteCarloResult",
    "MonthlyReviewResult",
    "Position",
    "StressResult",
    "TradeOrder",
    "build_dca_schedule",
    "build_default_strategy",
    "evaluate_adopter_metrics",
    "review_history",
    "run_monte_carlo",
    "run_stress_scenarios",
]
