# Changelog

## v0.1.0 — 2026-02-18

First working version. Both Axis 1 and Axis 2 produce real triples.

### Added

- **Triple schema** (`snag_bench/schema.py`) — Pydantic model for `(model, task, score)` triples with axis enum, sha256 run hash, evidence dict, and JSONL serialization.
- **CLI** (`snag_bench/cli.py`) — `snag-bench evaluate --model MODEL --full-stack --preset PRESET --dry-run` via Click.
- **SNAGEvaluator** (`snag_bench/evaluator.py`) — Full-stack evaluator running Axis 1 (Flash) and Axis 2 (Pro/Daedalus).
- **run.sh** — Shell runner that detects sibling repos (`../timepoint-flash/`, `../timepoint-pro/`), borrows their `.env` credentials, starts Flash server if needed, runs eval, and cleans up on exit.
- **BACKGROUND.md** — Reference document analyzing the three upstream repos and their SNAG Bench roles.
- **results/** — 8 JSONL triple files from development runs.

### Axis 1: Grounding Fidelity (GSR)

- Calls Flash `/api/v1/timepoints/generate/sync` with configurable preset
- Health check before generation request
- 5-minute timeout (balanced/hyper presets can be slow)
- Falls back to 0.8 placeholder score if Flash is unavailable
- Test query: "AlphaGo plays Move 37 against Lee Sedol March 10 2016"
- Result: **GSR 0.880** on gemini-2.0-flash

### Axis 2: Temporal Coherence (TCS)

- Runs `./run.sh run board_meeting` in the timepoint-pro repo via subprocess
- Passes model via `BACKEND` env var, runs 3 iterations via `RUNS` env var
- 10-minute timeout
- Skips gracefully if timepoint-pro repo not found
- Supports `DAEDALUS_REPO_PATH` env var override
- Result: **TCS 0.910** on gemini-2.0-flash

### Fixed

- Missing `snag_bench/__init__.py` — setuptools couldn't find the package without it (when `namespaces = false`).
- `run_hash` validation — fallback triples used `run_hash="demo"` (4 chars) but schema requires exactly 64 chars (sha256). Fixed to compute real hashes.
- `evaluate_full_stack` missing `dry_run` parameter — CLI passed it but the method didn't accept it.
- Flash timeout — bumped from 120s to 300s to handle slower presets.
- Flash database migrations — manually patched SQLite schema for migrations 0006-0009 that failed due to SQLite FK constraint limitations.

### Renamed

- All references from `timepoint-daedalus` to `timepoint-pro` across evaluator.py, run.sh, pyproject.toml, and BACKGROUND.md to match the upstream repo rename.

### Not Yet Implemented

- Axis 3: Predictive Precision (WMNED) — requires Proteus on-chain market data
- Axis 4: Human Judgment (HTP) — requires web rating interface
- Composite score aggregation
- Single-axis evaluation mode
- Leaderboard rendering
- CI pipeline
