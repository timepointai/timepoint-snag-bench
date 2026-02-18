import click
from rich.console import Console
from .evaluator import SNAGEvaluator

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
def evaluate(model: str, full_stack: bool, preset: str, dry_run: bool):
    """Run a full or single-axis evaluation"""
    evaluator = SNAGEvaluator()
    if full_stack:
        evaluator.evaluate_full_stack(model=model, preset=preset, dry_run=dry_run)
    else:
        console.print("Single-axis coming in v0.2 — use --full-stack for now")

if __name__ == "__main__":
    main()
