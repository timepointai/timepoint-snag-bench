"""Leaderboard generator — aggregates JSONL results into ranked markdown + JSON."""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console

from .schema import Axis, EvalResult
from .calibration import difficulty_weighted_score, AXIS_WEIGHTS

console = Console()

AXIS_LABELS = {
    Axis.GROUNDING: "GSR",
    Axis.COHERENCE: "TCS",
    Axis.PREDICTIVE: "WMNED",
    Axis.HUMAN: "HTP",
}

# Models that are internal Timepoint engines — excluded from public leaderboard
INTERNAL_PREFIXES = ["timepoint-", "flash-internal", "pro-internal"]


def load_all_results(results_dir: Path) -> List[EvalResult]:
    """Glob all *.jsonl files, parse each line as EvalResult, skip malformed."""
    results = []
    for path in sorted(results_dir.glob("*.jsonl")):
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                results.append(EvalResult.model_validate_json(line))
            except Exception as e:
                console.print(f"[yellow]Skip {path.name}:{lineno}: {e}[/]")
    return results


def _is_internal(model: str, result: EvalResult) -> bool:
    """Check if a result is from an internal Timepoint engine run."""
    if result.internal:
        return True
    return any(model.lower().startswith(p) for p in INTERNAL_PREFIXES)


def best_scores_by_model(
    results: List[EvalResult], external_only: bool = True,
) -> Dict[str, Dict[Axis, float]]:
    """Group by model, compute difficulty-weighted score per axis.

    For axes with per-task results (GSR, HTP), uses difficulty weighting.
    For per-model axes (TCS, WMNED), takes max score.
    """
    # Group results by model and axis
    grouped: Dict[str, Dict[Axis, List[EvalResult]]] = defaultdict(lambda: defaultdict(list))
    for r in results:
        if external_only and _is_internal(r.model, r):
            continue
        grouped[r.model][r.axis].append(r)

    scores = {}
    for model, axes in grouped.items():
        model_scores = {}
        for axis, axis_results in axes.items():
            # Check if these are per-task results (have tier info)
            has_tiers = any(r.tier is not None for r in axis_results)

            if has_tiers and len(axis_results) > 1:
                # Difficulty-weighted scoring for per-task axes
                pairs = [(r.score, r.tier or 1) for r in axis_results]
                model_scores[axis] = difficulty_weighted_score(pairs)
            else:
                # Max score for per-model axes
                model_scores[axis] = max(r.score for r in axis_results)

        scores[model] = model_scores

    return scores


def compute_composite(axis_scores: Dict[Axis, float]) -> Optional[float]:
    """Weighted average with renormalized weights over available axes only."""
    if not axis_scores:
        return None
    # Map Axis enum to string keys used in AXIS_WEIGHTS
    weight_map = {
        Axis.GROUNDING: "grounding",
        Axis.COHERENCE: "coherence",
        Axis.PREDICTIVE: "predictive",
        Axis.HUMAN: "human",
    }
    total_weight = sum(AXIS_WEIGHTS.get(weight_map[a], 0) for a in axis_scores)
    if total_weight == 0:
        return None
    return sum(AXIS_WEIGHTS.get(weight_map[a], 0) * s for a, s in axis_scores.items()) / total_weight


def render_markdown_table(
    scores: Dict[str, Dict[Axis, float]],
    composites: Dict[str, float],
    results: List[EvalResult],
) -> str:
    """Markdown table sorted by composite descending, missing axes show '---'."""
    axes_order = [Axis.GROUNDING, Axis.COHERENCE, Axis.PREDICTIVE, Axis.HUMAN]
    headers = ["Rank", "Model"] + [AXIS_LABELS[a] for a in axes_order] + ["Composite"]

    ranked = sorted(composites.items(), key=lambda x: x[1], reverse=True)

    rows = []
    for rank, (model, comp) in enumerate(ranked, 1):
        axis_vals = scores[model]
        cells = [str(rank), model]
        for a in axes_order:
            if a in axis_vals:
                cells.append(f"{axis_vals[a]:.3f}")
            else:
                cells.append("---")
        cells.append(f"**{comp:.3f}**")
        rows.append(cells)

    # Count unique tasks per model
    total_results = len([r for r in results if not _is_internal(r.model, r)])

    lines = []
    lines.append("# SNAG Bench Leaderboard v1.0")
    lines.append("")
    lines.append("Composite: 25% GSR + 30% TCS + 25% WMNED + 20% HTP (renormalized over available axes)")
    lines.append("")
    lines.append("Axes 1 (GSR) and 4 (HTP) use difficulty-weighted scoring across 60 tasks (Tier 3 = 2.5x weight).")
    lines.append("")
    lines.append("Axis 3 (WMNED) is currently stubbed — scores are placeholders until Proteus goes live.")
    lines.append("")
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    lines.append(f"*{total_results} result(s) across {len(scores)} model(s) — external models only*")
    lines.append("")
    lines.append(f"*Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}*")
    lines.append("")
    lines.append("See [methodology.md](../methodology.md) for scoring details and calibration targets.")
    return "\n".join(lines)


def render_json(
    scores: Dict[str, Dict[Axis, float]],
    composites: Dict[str, float],
) -> dict:
    """JSON representation of the leaderboard."""
    ranked = sorted(composites.items(), key=lambda x: x[1], reverse=True)
    models = []
    for rank, (model, comp) in enumerate(ranked, 1):
        entry = {
            "rank": rank,
            "model": model,
            "composite": round(comp, 4),
            "axes": {},
        }
        for axis, score in scores[model].items():
            entry["axes"][AXIS_LABELS[axis]] = round(score, 4)
        models.append(entry)

    return {
        "version": "1.0.0",
        "generated": datetime.utcnow().isoformat(),
        "scoring": {
            "GSR_weight": 0.25,
            "TCS_weight": 0.30,
            "WMNED_weight": 0.25,
            "HTP_weight": 0.20,
            "difficulty_weighted": True,
            "WMNED_stubbed": True,
        },
        "models": models,
    }


def generate_leaderboard(
    results_dir: str = "results",
    output_path: Optional[str] = None,
    json_path: Optional[str] = None,
) -> str:
    """Main entry point: load results, compute scores, render table + JSON."""
    results_dir = Path(results_dir)
    if not results_dir.is_dir():
        console.print(f"[red]Results directory not found: {results_dir}[/]")
        return ""

    results = load_all_results(results_dir)
    if not results:
        console.print("[yellow]No results found.[/]")
        return ""

    console.print(f"[cyan]Loaded {len(results)} result(s) from {results_dir}[/]")

    scores = best_scores_by_model(results, external_only=True)
    composites = {}
    for model, axis_scores in scores.items():
        comp = compute_composite(axis_scores)
        if comp is not None:
            composites[model] = comp

    table = render_markdown_table(scores, composites, results)

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(table + "\n")
        console.print(f"[green]Leaderboard written to {out}[/]")

    if json_path:
        json_out = Path(json_path)
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(render_json(scores, composites), indent=2) + "\n")
        console.print(f"[green]JSON leaderboard written to {json_out}[/]")

    if not output_path and not json_path:
        console.print()
        console.print(table)

    return table
