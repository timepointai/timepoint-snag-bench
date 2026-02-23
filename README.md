# SNAG Bench v1.0

**Open-source temporal reasoning benchmark for LLMs.**

SNAG Bench scores models across 4 axes using 60 fixed tasks at 3 difficulty tiers. Results are saved as JSONL for reproducibility and aggregated into a public leaderboard.

Part of the [Timepoint AI](https://github.com/timepoint-ai) stack.

## Scoring Axes

| Axis | Metric | Weight | Source | Status |
|------|--------|--------|--------|--------|
| 1. Grounding Fidelity | GSR | 25% | Flash API grounding confidence | Active |
| 2. Temporal Coherence | TCS | 30% | Pro/Daedalus dialog quality + mechanism coverage | Active |
| 3. Predictive Precision | WMNED | 25% | Proteus prediction markets | Stubbed |
| 4. Human Judgment | HTP | 20% | LLM-as-human roleplayer panel (3 personas, 4 dimensions) | Active |

**Composite:** `0.25×GSR + 0.30×TCS + 0.25×(1-WMNED) + 0.20×HTP` (renormalized over available axes)

## Task Set

60 fixed tasks across 3 difficulty tiers (frozen per version):

| Tier | Count | Weight | Examples |
|------|-------|--------|---------|
| Easy | 20 | 1.0x (20%) | Apollo 11, Berlin Wall, D-Day |
| Medium | 20 | 1.5x (30%) | Treaty of Westphalia, Krakatoa, Tunguska |
| Hard | 20 | 2.5x (50%) | Antikythera mechanism, Library of Alexandria, Voynich manuscript |

Tier 3 dominates scoring — a model acing Tier 1 but scoring 0.4 on Tier 3 gets a weighted GSR of ~0.58, not 0.80.

See [methodology.md](methodology.md) for calibration targets and design rationale.

## Quick Start (Local)

```bash
# 1. Clone and install
git clone https://github.com/timepoint-ai/timepoint-snag-bench.git
cd timepoint-snag-bench
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e .

# 2. Run full benchmark (requires Flash API on localhost:8000)
snag-bench run --models gemini-2.0-flash --full

# 3. Run specific tiers only
snag-bench run --models gemini-2.0-flash --tiers 1,2

# 4. Skip Axis 2 (saves ~45 min, no Pro needed)
snag-bench run --models gemini-2.0-flash --full --skip-axis2

# 5. Generate leaderboard from existing results
snag-bench leaderboard --output results/LEADERBOARD.md --json-output results/leaderboard.json
```

## CLI Reference

### `snag-bench run`

Main command for v1.0 benchmark runs.

| Option | Description |
|--------|-------------|
| `--models` | Required. Comma-separated model names |
| `--full` | Run all 60 tasks across all 3 tiers |
| `--tiers` | Comma-separated tier filter (e.g. `1,2`) |
| `--preset` | Flash preset (default: `balanced`) |
| `--text-model` | Override Flash LLM |
| `--pro-model` | Override Pro LLM |
| `--skip-axis2` | Skip Axis 2 / TCS (no Pro needed) |
| `--leaderboard/--no-leaderboard` | Auto-generate leaderboard after run (default: on) |

### `snag-bench leaderboard`

Generate leaderboard from existing JSONL results.

| Option | Description |
|--------|-------------|
| `--output` | Write markdown leaderboard to file |
| `--json-output` | Write JSON leaderboard to file |
| `--results-dir` | Directory containing .jsonl files (default: `results`) |

### `snag-bench evaluate` (legacy)

Single-model evaluation from v0.1. Use `run` for v1.0.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASH_URL` | `http://localhost:8000` | Flash API base URL |
| `PRO_REPO_PATH` | `~/Documents/GitHub/timepoint-pro` | Path to Pro repo (for Axis 2) |
| `OPENROUTER_API_KEY` | — | Required for Axis 4 (HTP) LLM judging |

## Requirements

- Python 3.10+
- Flash API running (for Axis 1 GSR) — see [timepoint-flash](https://github.com/timepoint-ai/timepoint-flash)
- Optional: Pro repo locally checked out (for Axis 2 TCS) — see [timepoint-pro](https://github.com/timepoint-ai/timepoint-pro)
- Optional: `OPENROUTER_API_KEY` for Axis 4 HTP

Axes degrade gracefully — if Flash isn't running, Axis 1 is skipped. If Pro isn't found, Axis 2 is skipped. If no API key, Axis 4 is skipped.

## Result Format

Each evaluation appends JSONL to `results/`:

```json
{
  "model": "gemini-2.0-flash",
  "task": "flash-grounding/t1_001",
  "score": 1.0,
  "axis": "grounding",
  "task_id": "t1_001",
  "tier": 1,
  "timestamp": "2026-02-19T17:30:00",
  "version": "1.0.0",
  "evidence": {"preset": "balanced", "query": "Apollo 11 Moon landing July 20 1969", "scene_id": "..."},
  "run_hash": "a1b2c3..."
}
```

## Project Structure

```
timepoint-snag-bench/
├── snag_bench/
│   ├── cli.py              # Click CLI (snag-bench run/evaluate/leaderboard)
│   ├── evaluator.py         # SNAGEvaluator — 4-axis orchestrator
│   ├── schema.py            # EvalResult + Axis Pydantic models
│   ├── calibration.py       # Difficulty-weighted scoring, composite formula
│   ├── leaderboard.py       # Leaderboard generation (MD + JSON)
│   └── axes/
│       ├── human.py         # Axis 4 — LLM-as-human HTP rater
│       └── predictive.py    # Axis 3 — WMNED stub
├── tasks/
│   ├── version.json         # Task set metadata and calibration targets
│   ├── tier1_easy.json      # 20 easy tasks
│   ├── tier2_medium.json    # 20 medium tasks
│   └── tier3_hard.json      # 20 hard/adversarial tasks
├── results/                 # JSONL result files + leaderboard
├── methodology.md           # Scoring methodology and calibration
├── run.sh                   # Shell runner with env detection
└── pyproject.toml
```

## Hosted Runner (Internal)

For Timepoint AI internal use, a hosted version runs on Railway via [`snag-bench-runner`](https://github.com/timepoint-ai/snag-bench-runner). It provides a REST API for triggering and monitoring long benchmark runs without needing a local setup. See that repo's README for API docs.

## Leaderboard

See [results/LEADERBOARD.md](results/LEADERBOARD.md) for current standings.

External models only — Timepoint internal engine runs are excluded from the public leaderboard.

## License

Apache-2.0
