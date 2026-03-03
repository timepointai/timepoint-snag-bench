import click
from rich.console import Console
from .evaluator import SNAGEvaluator
from .leaderboard import generate_leaderboard

console = Console()


@click.group()
def main():
    """SNAG Bench — Temporal Reasoning Benchmark v1.1 (TDF)"""
    pass


@main.command()
@click.option(
    "--models",
    required=True,
    help="Comma-separated model names (e.g. gemini-2.0-flash,claude-3.5-sonnet)",
)
@click.option("--full", is_flag=True, help="Run all 60 tasks across all tiers")
@click.option("--tiers", default=None, help="Comma-separated tiers to run (e.g. 1,2,3)")
@click.option("--preset", default="balanced", help="Flash preset")
@click.option("--text-model", default=None, help="Override Flash LLM")
@click.option("--pro-model", default=None, help="Override Pro LLM")
@click.option(
    "--skip-axis2", is_flag=True, help="Skip Axis 2 (Pro/TCS) — saves ~45 min per model"
)
@click.option(
    "--leaderboard/--no-leaderboard",
    default=True,
    help="Auto-generate leaderboard after run",
)
def run(
    models: str,
    full: bool,
    tiers: str,
    preset: str,
    text_model: str,
    pro_model: str,
    skip_axis2: bool,
    leaderboard: bool,
):
    """Run full benchmark across models and tasks"""
    model_list = [m.strip() for m in models.split(",") if m.strip()]

    tier_list = None
    if not full and tiers:
        tier_list = [int(t.strip()) for t in tiers.split(",")]
    elif full:
        tier_list = None  # all tiers

    evaluator = SNAGEvaluator()
    evaluator.run_benchmark(
        models=model_list,
        tiers=tier_list,
        preset=preset,
        text_model=text_model,
        pro_model=pro_model,
        skip_axis2=skip_axis2,
    )

    if leaderboard:
        console.print()
        generate_leaderboard(
            results_dir="results",
            output_path="results/LEADERBOARD.md",
            json_path="results/leaderboard.json",
        )


@main.command()
@click.option("--model", required=True, help="Model name e.g. claude-3.5-sonnet")
@click.option(
    "--full-stack", is_flag=True, help="Run all 4 axes + generate training data"
)
@click.option("--preset", default="balanced", help="Flash preset")
@click.option("--dry-run", is_flag=True, help="Print what would happen")
@click.option(
    "--text-model", default=None, help="Override Flash LLM (text_model in payload)"
)
@click.option(
    "--pro-model", default=None, help="Override Pro LLM (--model flag to Pro)"
)
def evaluate(
    model: str,
    full_stack: bool,
    preset: str,
    dry_run: bool,
    text_model: str,
    pro_model: str,
):
    """Run a full or single-axis evaluation (legacy — use 'run' for v1.0)"""
    evaluator = SNAGEvaluator()
    if full_stack:
        evaluator.evaluate_full_stack(
            model=model,
            preset=preset,
            dry_run=dry_run,
            text_model=text_model,
            pro_model=pro_model,
        )
    else:
        console.print("Single-axis coming in v0.2 — use --full-stack for now")


@main.command()
@click.option("--output", default=None, help="Write markdown leaderboard to file")
@click.option("--json-output", default=None, help="Write JSON leaderboard to file")
@click.option(
    "--results-dir", default="results", help="Directory containing .jsonl result files"
)
def leaderboard(output: str, json_output: str, results_dir: str):
    """Generate leaderboard from all eval results"""
    generate_leaderboard(
        results_dir=results_dir,
        output_path=output,
        json_path=json_output,
    )


@main.command(name="tfi-report")
@click.option(
    "--domain",
    required=True,
    help="Domain to evaluate (e.g. 'test', 'history', 'finance')",
)
@click.option("--model", default=None, help="Model to evaluate")
@click.option("--output", default=None, help="Output file path (default: stdout)")
def tfi_report(domain: str, model: str, output: str):
    """Generate a Temporal Fidelity Index (TFI) report with GCQ coverage metrics."""
    from pathlib import Path
    from snag_bench.axes.coverage import evaluate_coverage_stub
    import json

    score, evidence = evaluate_coverage_stub()
    report = {
        "domain": domain,
        "model": model or "stub",
        "axis": "coverage",
        "score": score,
        "evidence": evidence,
    }
    report_json = json.dumps(report, indent=2, default=str)

    if output:
        Path(output).write_text(report_json)
        console.print(f"TFI report written to {output}")
    else:
        console.print(report_json)


if __name__ == "__main__":
    main()
