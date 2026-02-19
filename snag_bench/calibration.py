"""Calibration and difficulty-weighted scoring for SNAG Bench.

The core insight: easy tasks (Tier 1) should contribute less to the final
score than hard tasks (Tier 3). This keeps the benchmark challenging as
models improve — even if a model aces Tier 1, Tier 3 performance dominates
the composite.

Tier weights:
  - Tier 1 (easy):   1.0x — baseline contribution
  - Tier 2 (medium): 1.5x — moderate amplification
  - Tier 3 (hard):   2.5x — dominates the final score

With 20 tasks per tier, effective weight distribution:
  - Tier 1: 20 * 1.0 = 20  (20% of total weight)
  - Tier 2: 20 * 1.5 = 30  (30% of total weight)
  - Tier 3: 20 * 2.5 = 50  (50% of total weight)

Target calibration (frontier models):
  - 2026: composite 0.65–0.80
  - 2028: composite 0.78–0.88
  - 2030: composite 0.85–0.95
  - Saturation floor: 0.97 (benchmark remains useful until models approach this)
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

TIER_WEIGHTS = {1: 1.0, 2: 1.5, 3: 2.5}

AXIS_WEIGHTS = {
    "grounding": 0.25,
    "coherence": 0.30,
    "predictive": 0.25,
    "human": 0.20,
}


def load_tasks(tasks_dir: str = "tasks") -> List[dict]:
    """Load all tasks from tier JSON files, injecting tier into each task."""
    tasks_path = Path(tasks_dir)
    all_tasks = []
    for tier_file in ["tier1_easy.json", "tier2_medium.json", "tier3_hard.json"]:
        path = tasks_path / tier_file
        if path.exists():
            data = json.loads(path.read_text())
            tier = data["tier"]
            for task in data["tasks"]:
                task["tier"] = tier
            all_tasks.extend(data["tasks"])
    return all_tasks


def load_tasks_by_tier(tasks_dir: str = "tasks", tiers: Optional[List[int]] = None) -> List[dict]:
    """Load tasks filtered by tier."""
    tasks = load_tasks(tasks_dir)
    if tiers:
        tasks = [t for t in tasks if t["tier"] in tiers]
    return tasks


def difficulty_weighted_score(task_scores: List[Tuple[float, int]]) -> float:
    """Compute difficulty-weighted average from (score, tier) pairs.

    Higher tiers have more weight, so a model must perform well on hard
    tasks to achieve a high overall score.
    """
    if not task_scores:
        return 0.0
    total_weight = sum(TIER_WEIGHTS.get(tier, 1.0) for _, tier in task_scores)
    weighted_sum = sum(score * TIER_WEIGHTS.get(tier, 1.0) for score, tier in task_scores)
    return weighted_sum / total_weight if total_weight > 0 else 0.0


def composite_score(axis_scores: Dict[str, float]) -> Optional[float]:
    """Compute weighted composite across available axes.

    Renormalizes weights over axes that have scores, so missing axes
    don't artificially deflate the composite.
    """
    if not axis_scores:
        return None
    available_weight = sum(AXIS_WEIGHTS[a] for a in axis_scores if a in AXIS_WEIGHTS)
    if available_weight == 0:
        return None
    return sum(
        AXIS_WEIGHTS.get(a, 0) * s
        for a, s in axis_scores.items()
        if a in AXIS_WEIGHTS
    ) / available_weight
