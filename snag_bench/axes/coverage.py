"""Axis 5 — Coverage (GCQ) stub.

Graph Coverage Quality measures how well the clockchain graph covers
temporal events. Evaluates path completeness, convergence stability,
source type diversity, and edge density.

This is a placeholder that returns realistic GCQ values from stubbed
metrics. Designed to be connected to real clockchain stats when available.
"""

from typing import Dict, Any

STUB_METRICS = {
    "path_completeness": 0.73,
    "convergence_stability": 0.81,
    "source_type_diversity": 0.45,
    "edge_density": 0.62,
}

SUB_WEIGHTS = {
    "path_completeness": 0.30,
    "convergence_stability": 0.25,
    "source_type_diversity": 0.25,
    "edge_density": 0.20,
}


def evaluate_coverage_stub() -> tuple[float, Dict[str, Any]]:
    """Return stubbed GCQ score and evidence.

    Returns (score, evidence) where score is a weighted composite
    of the GCQ sub-metrics.
    """
    score = sum(
        STUB_METRICS[k] * SUB_WEIGHTS[k]
        for k in STUB_METRICS
    )

    evidence = {
        "stub": True,
        "note": "Axis 5 uses stubbed metrics until clockchain stats integration",
        "path_completeness": STUB_METRICS["path_completeness"],
        "convergence_stability": STUB_METRICS["convergence_stability"],
        "source_type_diversity": STUB_METRICS["source_type_diversity"],
        "edge_density": STUB_METRICS["edge_density"],
        "sub_weights": SUB_WEIGHTS,
    }
    return round(score, 4), evidence
