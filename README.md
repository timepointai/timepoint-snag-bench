# SNAG Bench v0.1.0

**Orchestrator that makes Flash + Daedalus (Pro) + Proteus one closed temporal reasoning loop.**

SNAG Bench is an open scoring standard for temporal reasoning in LLMs. It produces `(model, task, score)` triples across four axes, saved as JSONL for reproducibility and leaderboard aggregation.

## Scoring Axes

| Axis | Metric | Source | Status |
|------|--------|--------|--------|
| **1. Grounding Fidelity** | GSR (Grounding Survival Rate) | [timepoint-flash](https://github.com/timepoint-ai/timepoint-flash) | Working |
| **2. Temporal Coherence** | TCS (Temporal Coherence Score) | [timepoint-pro](https://github.com/timepoint-ai/timepoint-pro) | Working |
| **3. Predictive Precision** | WMNED (Weighted Mean Normalized Edit Distance) | [proteus-markets](https://github.com/timepoint-ai/proteus) | Planned |
| **4. Human Judgment** | HTP (Human Temporal Perception) | Web rating interface | Planned |

**Composite score:** `w1*GSR + w2*TCS + w3*(1-WMNED) + w4*HTP` (weights: 25/30/25/20)

## Quick Start

```bash
# 1. Create venv and install
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .

# 2. Run (auto-detects sibling repos, borrows creds, starts Flash if needed)
./run.sh

# 3. Or run directly
snag-bench evaluate --model gemini-2.0-flash --full-stack --preset balanced
```

## Requirements

- Python 3.10+
- Sibling repos (optional — axes degrade gracefully if missing):
  - `../timepoint-flash/` — Axis 1 (scene generation + grounding)
  - `../timepoint-pro/` — Axis 2 (temporal simulation + coherence)
- Flash `.env` with at least `GOOGLE_API_KEY` set

## run.sh

The runner script handles the full lifecycle:

1. **Environment check** — detects venv, sibling repos, `.env` files, API keys
2. **Credential loading** — borrows API keys from Flash and Pro `.env` files
3. **Flash server** — starts Flash on port 8000 if not already running, waits for health check
4. **Evaluation** — runs `snag-bench evaluate` with your options
5. **Cleanup** — stops Flash server on exit

```bash
./run.sh              # check + evaluate (default: gemini-2.0-flash --full-stack)
./run.sh check        # environment check only
./run.sh evaluate --model gemini-2.0-flash --preset hyper
./run.sh help
```

## Triple Format

Each evaluation produces JSONL triples in `results/`:

```json
{
  "model": "gemini-2.0-flash",
  "task": "flash-grounding/alphago-move37",
  "score": 0.88,
  "axis": "grounding",
  "timestamp": "2026-02-18T17:43:20.753726",
  "submitter": "realityinspector",
  "version": "0.1.0",
  "evidence": {"preset": "balanced", "scene_id": "..."},
  "run_hash": "31ef531f..."
}
```

## Project Structure

```
snag_bench/
  __init__.py       # Package init
  cli.py            # Click CLI (snag-bench evaluate)
  schema.py         # Triple + Axis Pydantic models
  evaluator.py      # SNAGEvaluator (Axis 1 + Axis 2 runners)
run.sh              # Shell runner with env detection
results/            # JSONL triple output files
BACKGROUND.md       # Upstream repo analysis
CHANGELOG.md        # Version history
```

## First Results (Feb 18, 2026)

| Model | Axis 1 (GSR) | Axis 2 (TCS) |
|-------|--------------|---------------|
| gemini-2.0-flash | 0.880 | 0.910 |

## License

Apache-2.0
