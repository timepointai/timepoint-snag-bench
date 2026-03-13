# Changelog

## v1.0.0 — 2026-02-19

Major upgrade: 60-task benchmark with difficulty-weighted scoring and 4 axes.

### Added

- **60 versioned tasks** (`tasks/`) across 3 difficulty tiers (easy/medium/hard)
- **Difficulty-weighted scoring** (`snag_bench/calibration.py`) — Tier 3 = 2.5x weight, dominates 50% of score
- **Axis 3 stub** (`snag_bench/axes/predictive.py`) — WMNED with 10 fake resolved markets (score: 0.817)
- **Axis 4 LLM-as-human** (`snag_bench/axes/human.py`) — 3 personas (historian, novelist, skeptic), 4 dimensions, via OpenRouter
- **`snag-bench run` command** — Multi-model, multi-tier benchmark orchestrator
- **`snag-bench leaderboard` command** — Generates Markdown + JSON leaderboards
- **Leaderboard generator** (`snag_bench/leaderboard.py`) — External-model-only, difficulty-weighted, JSON + Markdown output
- **methodology.md** — Calibration targets (2026–2030), 8 known limitations, scoring formulas
- **Adaptive Pro timeout** (`_run_pro_adaptive()`) — Popen + threading, stale detection, heartbeat logging
- **Resilient scoring** — Parse TCS from stdout even on non-zero Pro exit code
- **Configurable Flash URL** — `FLASH_URL` env var (defaults to localhost:8000)
- **SAST baseline** — `.bandit` + `.semgrepignore` configs, 0 findings

### Changed

- Upgraded from `convergence_simple` to `mars_mission_portal` template for Axis 2
- Replaced rigid subprocess timeout with adaptive stale-detection
- Rewrote evaluator for multi-axis orchestration across models
- Version bumped to 1.0.0 across `pyproject.toml`, `schema.py`, `__init__.py`
- GSR extraction fixed: `data.grounding.grounding_confidence` (was hardcoded 0.88)

### Architecture

- **Public repo** (`timepointai/timepoint-snag-bench`) — benchmark spec, tasks, scoring, CLI
- **Private runner** — hosted deployment with REST API and persistent storage

## v0.1.0 — 2026-02-18

First working version. Axis 1 and Axis 2 produce real eval results.

### Added

- EvalResult schema with Pydantic, JSONL serialization, sha256 run hash
- CLI: `snag-bench evaluate --model MODEL --full-stack`
- SNAGEvaluator with Axis 1 (Flash GSR) and Axis 2 (Pro TCS)
- run.sh with env detection, credential borrowing, Flash server management
- BACKGROUND.md analyzing upstream repos

### Results

- Axis 1 GSR: 0.880 → 1.000 (after fixing extraction)
- Axis 2 TCS: 0.910 → 0.928 (after mars_mission_portal upgrade)
