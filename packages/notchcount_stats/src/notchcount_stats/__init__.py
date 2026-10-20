"""NotchCount estimator: pure mark-resight statistics with uncertainty carried end to end."""

from notchcount_stats.closed import (
    EstimateStatus,
    InvalidCounts,
    PopulationEstimate,
    chao_interval,
    chapman,
    chapman_point,
    schnabel,
    schnabel_terms,
)
from notchcount_stats.propagate import (
    Counts,
    EstimateMode,
    SinglePassEstimate,
    Summary,
    TwoPassEstimate,
    estimate_single_pass,
    estimate_two_pass,
)
from notchcount_stats.proportion import (
    COVERAGE_BENCHMARK,
    ShareEstimate,
    coverage_deficit,
    sterilised_share,
    wilson,
)
from notchcount_stats.survey import CandidatePair, NotchCall, NotchClass, Sighting, SurveyData

__version__ = "0.1.0"

__all__ = [
    "COVERAGE_BENCHMARK",
    "CandidatePair",
    "Counts",
    "EstimateMode",
    "EstimateStatus",
    "InvalidCounts",
    "NotchCall",
    "NotchClass",
    "PopulationEstimate",
    "ShareEstimate",
    "Sighting",
    "SinglePassEstimate",
    "Summary",
    "SurveyData",
    "TwoPassEstimate",
    "__version__",
    "chao_interval",
    "chapman",
    "chapman_point",
    "coverage_deficit",
    "estimate_single_pass",
    "estimate_two_pass",
    "schnabel",
    "schnabel_terms",
    "sterilised_share",
    "wilson",
]
