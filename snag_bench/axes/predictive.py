"""Axis 3 — Predictive (WMNED) stub.

This is a placeholder that returns realistic WMNED values from 10 fake
resolved prediction markets. Designed to be swapped out when Proteus
(the real prediction engine) goes live.

WMNED = Weighted Mean Normalized Error Distance. Lower is better for
raw error, but we report as 1-WMNED so higher = better on the leaderboard.
Typical real-world prediction accuracy: WMNED 0.05-0.45 raw → 0.55-0.95 inverted.
"""

from typing import Dict, Any

STUB_MARKETS = [
    {
        "id": "pm_001",
        "question": "Will GPT-5 be released before July 2026?",
        "resolved": True,
        "outcome": 0.72,
        "predicted": 0.65,
        "wmned_raw": 0.07,
    },
    {
        "id": "pm_002",
        "question": "Will global mean temperature anomaly exceed 1.6C in 2026?",
        "resolved": True,
        "outcome": 0.58,
        "predicted": 0.40,
        "wmned_raw": 0.18,
    },
    {
        "id": "pm_003",
        "question": "Will SpaceX Starship complete orbital flight before 2026?",
        "resolved": True,
        "outcome": 1.00,
        "predicted": 0.82,
        "wmned_raw": 0.18,
    },
    {
        "id": "pm_004",
        "question": "Will US unemployment exceed 5% in Q1 2026?",
        "resolved": True,
        "outcome": 0.15,
        "predicted": 0.22,
        "wmned_raw": 0.07,
    },
    {
        "id": "pm_005",
        "question": "Will a lab-grown meat product reach $10/kg retail by 2026?",
        "resolved": True,
        "outcome": 0.05,
        "predicted": 0.35,
        "wmned_raw": 0.30,
    },
    {
        "id": "pm_006",
        "question": "Will any country ban LLM training on copyrighted data by 2026?",
        "resolved": True,
        "outcome": 0.40,
        "predicted": 0.55,
        "wmned_raw": 0.15,
    },
    {
        "id": "pm_007",
        "question": "Will Bitcoin exceed $150k at any point in 2025?",
        "resolved": True,
        "outcome": 0.80,
        "predicted": 0.45,
        "wmned_raw": 0.35,
    },
    {
        "id": "pm_008",
        "question": "Will WHO declare another pandemic before 2027?",
        "resolved": True,
        "outcome": 0.10,
        "predicted": 0.15,
        "wmned_raw": 0.05,
    },
    {
        "id": "pm_009",
        "question": "Will autonomous vehicles operate without safety driver in 5+ US cities by 2026?",
        "resolved": True,
        "outcome": 0.65,
        "predicted": 0.70,
        "wmned_raw": 0.05,
    },
    {
        "id": "pm_010",
        "question": "Will nuclear fusion achieve net energy gain in a commercial reactor by 2026?",
        "resolved": True,
        "outcome": 0.02,
        "predicted": 0.45,
        "wmned_raw": 0.43,
    },
]


def evaluate_predictive_stub() -> tuple[float, Dict[str, Any]]:
    """Return stubbed WMNED score and evidence.

    Returns (score, evidence) where score is 1 - mean_wmned_raw
    (inverted so higher = better, matching other axes).
    """
    raw_errors = [m["wmned_raw"] for m in STUB_MARKETS]
    mean_wmned = sum(raw_errors) / len(raw_errors)
    score = 1.0 - mean_wmned  # invert: lower error = higher score

    evidence = {
        "stub": True,
        "note": "Axis 3 uses fake resolved markets until Proteus goes live",
        "n_markets": len(STUB_MARKETS),
        "mean_wmned_raw": round(mean_wmned, 4),
        "market_ids": [m["id"] for m in STUB_MARKETS],
        "individual_errors": {m["id"]: m["wmned_raw"] for m in STUB_MARKETS},
    }
    return round(score, 4), evidence
