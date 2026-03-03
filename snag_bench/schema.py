from datetime import datetime
from enum import Enum

from timepoint_tdf import TDFRecord, TDFProvenance

BENCH_VERSION = "1.1.0"


class Axis(str, Enum):
    GROUNDING = "grounding"
    COHERENCE = "coherence"
    PREDICTIVE = "predictive"
    HUMAN = "human"
    COVERAGE = "coverage"


def eval_record(
    *,
    model: str,
    task: str,
    score: float,
    axis: Axis,
    evidence: dict = None,
    task_id: str = None,
    tier: int = None,
    internal: bool = False,
) -> TDFRecord:
    """Create a TDFRecord for a SNAG Bench evaluation result."""
    payload = {
        "model": model,
        "task": task,
        "score": min(max(score, 0.0), 1.0),
        "axis": axis.value if isinstance(axis, Axis) else axis,
        "version": BENCH_VERSION,
        "submitter": "realityinspector",
        "task_id": task_id,
        "tier": tier,
        "internal": internal,
        "evidence": evidence or {},
    }
    return TDFRecord(
        id=f"snag-bench/{task_id or task}/{model}",
        source="snag-bench",
        timestamp=datetime.utcnow(),
        provenance=TDFProvenance(generator="snag-bench", confidence=score),
        payload=payload,
    )
