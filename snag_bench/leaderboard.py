"""Leaderboard generator — aggregates JSONL results into a ranked markdown table."""

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console

from .schema import Axis, EvalResult

console = Console()

# Axis weights for composite score
AXIS_WEIGHTS = {
    Axis.GROUNDING: 0.25,
    Axis.COHERENCE: 0.30,
    Axis.PREDICTIVE: 0.25,
    Axis.HUMAN: 0.20,
}

AXIS_LABELS = {
    Axis.GROUNDING: "GSR",
    Axis.COHERENCE: "TCS",
    Axis.PREDICTIVE: "WMNED",
    Axis.HUMAN: "HTP",
}


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


def best_scores_by_model(results: List[EvalResult]) -> Dict[str, Dict[Axis, float]]:
    """Group by model, take max score per axis."""
    grouped: Dict[str, Dict[Axis, List[float]]] = defaultdict(lambda: defaultdict(list))
    for r in results:
        grouped[r.model][r.axis].append(r.score)
    return {
        model: {axis: max(scores) for axis, scores in axes.items()}
        for model, axes in grouped.items()
    }


def compute_composite(axis_scores: Dict[Axis, float]) -> Optional[float]:
    """Weighted average with renormalized weights over available axes only."""
    if not axis_scores:
        return None
    total_weight = sum(AXIS_WEIGHTS[a] for a in axis_scores)
    if total_weight == 0:
        return None
    return sum(AXIS_WEIGHTS[a] * s for a, s in axis_scores.items()) / total_weight


def render_markdown_table(
    scores: Dict[str, Dict[Axis, float]],
    composites: Dict[str, float],
) -> str:
    """Markdown table sorted by composite descending, missing axes show '---'."""
    axes_order = [Axis.GROUNDING, Axis.COHERENCE, Axis.PREDICTIVE, Axis.HUMAN]
    headers = ["Rank", "Model"] + [AXIS_LABELS[a] for a in axes_order] + ["Composite"]

    # Sort by composite descending
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

    # Build markdown
    lines = []
    lines.append("# SNAG Bench Leaderboard")
    lines.append("")
    lines.append("Weighted composite: 25% GSR + 30% TCS + 25% WMNED + 20% HTP")
    lines.append("(renormalized over available axes)")
    lines.append("")
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    lines.append(f"*Generated from {sum(len(s) for s in scores.values())} result(s) across {len(scores)} model(s)*")
    return "\n".join(lines)


def generate_leaderboard(results_dir: str = "results", output_path: Optional[str] = None) -> str:
    """Main entry point: load results, compute scores, render table."""
    results_dir = Path(results_dir)
    if not results_dir.is_dir():
        console.print(f"[red]Results directory not found: {results_dir}[/]")
        return ""

    results = load_all_results(results_dir)
    if not results:
        console.print("[yellow]No results found.[/]")
        return ""

    console.print(f"[cyan]Loaded {len(results)} result(s) from {results_dir}[/]")

    scores = best_scores_by_model(results)
    composites = {}
    for model, axis_scores in scores.items():
        comp = compute_composite(axis_scores)
        if comp is not None:
            composites[model] = comp

    table = render_markdown_table(scores, composites)

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(table + "\n")
        console.print(f"[green]Leaderboard written to {out}[/]")
    else:
        console.print()
        console.print(table)

    return table
