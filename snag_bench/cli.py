import click
from rich.console import Console
from .evaluator import SNAGEvaluator
from .leaderboard import generate_leaderboard

console = Console()

@click.group()
def main():
    """SNAG Bench — Timepoint Temporal Reasoning Orchestrator"""
    pass

@main.command()
@click.option("--model", required=True, help="Model name e.g. claude-3.5-sonnet")
@click.option("--full-stack", is_flag=True, help="Run all 4 axes + generate training data")
@click.option("--preset", default="balanced", help="Flash preset")
@click.option("--dry-run", is_flag=True, help="Print what would happen")
@click.option("--text-model", default=None, help="Override Flash LLM (text_model in payload)")
@click.option("--pro-model", default=None, help="Override Pro LLM (--model flag to Pro)")
def evaluate(model: str, full_stack: bool, preset: str, dry_run: bool, text_model: str, pro_model: str):
    """Run a full or single-axis evaluation"""
    evaluator = SNAGEvaluator()
    if full_stack:
        evaluator.evaluate_full_stack(
            model=model, preset=preset, dry_run=dry_run,
            text_model=text_model, pro_model=pro_model,
        )
    else:
        console.print("Single-axis coming in v0.2 — use --full-stack for now")

@main.command()
@click.option("--output", default=None, help="Write leaderboard to file (e.g. results/LEADERBOARD.md)")
@click.option("--results-dir", default="results", help="Directory containing .jsonl result files")
def leaderboard(output: str, results_dir: str):
    """Generate leaderboard from all eval results"""
    generate_leaderboard(results_dir=results_dir, output_path=output)

if __name__ == "__main__":
    main()
