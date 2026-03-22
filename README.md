# SNAG Bench

**Temporal reasoning benchmark for LLMs.** 60 adversarial tasks, 5 scoring axes, 3 difficulty tiers. Designed to stay hard through 2030.

Most benchmarks test what models know. SNAG Bench tests whether they understand **when** — can a model distinguish a baptism date from a birth date, reject an anachronistic premise, or acknowledge when sources genuinely conflict? It measures **Causal Resolution**: how much of a temporal scenario has been rendered (Coverage) and how reliably (Convergence).

> **Why this exists:** Frontier models score ~1.0 on well-documented temporal queries. That tells us nothing. SNAG Bench's adversarial Tier 3 — sparse records, conflicting sources, embedded errors, temporal impossibilities — drops even the best models to 0.55–0.75. That spread is where evaluation becomes useful.

Part of the [Timepoint AI](https://github.com/timepointai) open-source stack.

---

## Scoring Axes

Five axes, each measuring a different temporal capability. Scores are weighted and combined into a composite.

```
                                           Weight
  TCS   ▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░  25%   Temporal Coherence
  GSR   ▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░  20%   Grounding Fidelity
  WMNED ▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░  20%   Predictive Precision
  GCQ   ▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░  18%   Graph Coverage
  HTP   ▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░  17%   Human Judgment
```

| # | Axis | What it measures | Source | Status |
|---|------|-----------------|--------|--------|
| 1 | **GSR** | Do temporal claims survive fact-checking? | Flash API grounding | Active |
| 2 | **TCS** | Can the model maintain coherent timelines in simulation? | Pro engine | Active |
| 3 | **WMNED** | Do temporal forecasts match actual outcomes? | Proteus prediction markets | Stubbed |
| 4 | **HTP** | Would 5 domain experts find the scene plausible? | LLM-as-human panel | Active |
| 5 | **GCQ** | How complete and consistent is the causal graph? | Path/anchor analysis | Stubbed |

Composite = weighted sum, renormalized over available axes. Missing axes don't penalize.

---

## Evaluation Architecture

Each benchmark run fans out across all axes simultaneously:

```
                 ┌── Flash API ────── GSR   grounding confidence
                 ├── Pro Engine ───── TCS   dialog quality + voice + mechanisms
  60 tasks ──────┼── Proteus ──────── WMNED future outcome accuracy
                 ├── 5 LLM Judges ── HTP   penalty-scored plausibility
                 └── Graph Walker ─── GCQ   path completeness + convergence
                                      │
                                  Composite
```

Axes degrade gracefully — if a service isn't available, its axis is skipped and weights renormalize over what remains.

---

## Task Set

60 fixed tasks across 3 tiers. **Tier 3 is half the score.**

```
            Tasks   Score Weight
  Easy       20    ██░░░░░░░░  20%    Well-documented events
  Medium     20    ███░░░░░░░  30%    Moderate ambiguity
  Hard       20    █████░░░░░  50%    Adversarial temporal traps
```

A model scoring 1.0 on all Easy tasks but 0.4 on Hard gets a weighted score of **~0.58**, not 0.80.

### What makes Tier 3 hard

Adversarial tasks exploit specific failure modes:

- **Sparse documentation** — queries about periods with no surviving records, forcing models to fabricate or admit uncertainty
- **Conflicting sources** — Plutarch says one thing, Cassius Dio another, Strabo a third. There is no correct answer to pick
- **Embedded anachronisms** — queries that describe European crop rotation in pre-contact Mesoamerica. Models must reject the premise
- **Temporal impossibility** — conflating events separated by decades (Hypatia and the Serapeum, 24 years apart)
- **Precision traps** — dates confidently cited everywhere that are technically wrong (Shakespeare's "birthday" is his baptism date)

> **Longevity target:** Top model composite ≤0.95 through 2030. Tasks are retired and replaced when 3+ frontier models score >0.95 GSR. See [methodology.md](methodology.md) for the annual recalibration plan.

---

## Quick Start

```bash
git clone https://github.com/timepointai/timepoint-snag-bench.git
cd timepoint-snag-bench
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# Full benchmark (requires Flash API on localhost:8000)
snag-bench run --models gemini-2.0-flash --full

# Specific tiers only
snag-bench run --models gemini-2.0-flash --tiers 1,2

# Skip Axis 2 (no Pro engine needed)
snag-bench run --models gemini-2.0-flash --full --skip-axis2

# Generate leaderboard from existing results
snag-bench leaderboard --output results/LEADERBOARD.md
```

<details>
<summary><strong>CLI Reference</strong></summary>

### `snag-bench run`

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

| Option | Description |
|--------|-------------|
| `--output` | Write markdown leaderboard to file |
| `--json-output` | Write JSON leaderboard to file |
| `--results-dir` | Directory containing .jsonl files (default: `results`) |

### `snag-bench evaluate` (legacy)

Single-model evaluation from v0.1. Use `run` instead.

</details>

<details>
<summary><strong>Environment Variables</strong></summary>

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASH_URL` | `http://localhost:8000` | Flash API base URL |
| `PRO_REPO_PATH` | `~/Documents/GitHub/timepoint-pro` | Path to Pro repo (Axis 2 subprocess) |
| `PRO_URL` | — | Pro Cloud API base URL (Axis 2 cloud path, preferred) |
| `PRO_API_KEY` | — | Pro Cloud API key (format: `tp_cloud_...`) |
| `OPENROUTER_API_KEY` | — | Required for Axis 4 (HTP) LLM judging |

</details>

<details>
<summary><strong>Result Format</strong></summary>

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
  "version": "1.1.0",
  "evidence": {"preset": "balanced", "query": "Apollo 11 Moon landing July 20 1969"},
  "run_hash": "a1b2c3..."
}
```

</details>

<details>
<summary><strong>Project Structure</strong></summary>

```
timepoint-snag-bench/
├── snag_bench/
│   ├── cli.py              # Click CLI
│   ├── evaluator.py         # 5-axis orchestrator
│   ├── schema.py            # EvalResult + Axis models
│   ├── calibration.py       # Difficulty-weighted scoring
│   ├── leaderboard.py       # Leaderboard generation
│   └── axes/
│       ├── human.py         # Axis 4 — 5-rater HTP
│       ├── predictive.py    # Axis 3 — WMNED stub
│       └── coverage.py      # Axis 5 — GCQ stub
├── tasks/
│   ├── version.json         # Task set metadata
│   ├── tier1_easy.json      # 20 easy tasks
│   ├── tier2_medium.json    # 20 medium tasks
│   └── tier3_hard.json      # 20 adversarial tasks
├── results/                 # JSONL results + leaderboard
├── methodology.md           # Scoring methodology
└── pyproject.toml
```

</details>

---

## Leaderboard

See [results/LEADERBOARD.md](results/LEADERBOARD.md) for current standings. External models only — Timepoint internal runs are excluded.

---

## Timepoint Suite

Render the past. Simulate the future. Score the predictions. Accumulate the graph.

| Service | Type | Repo | Role |
|---------|------|------|------|
| **Flash** | Open Source | timepoint-flash | Reality Writer — renders grounded historical moments |
| **Clockchain** | Open Source | timepoint-clockchain | Temporal Causal Graph — Rendered Past + Rendered Future, growing 24/7 |
| **Pro** | Open Source | timepoint-pro | SNAG Simulation Engine — temporal simulation, TDF output, training data |
| **Proteus** | Open Source | proteus | Settlement Layer — prediction markets for Rendered Futures |
| **TDF** | Open Source | timepoint-tdf | Data Format — JSON-LD interchange across all services |
| **SNAG Bench** | **Open Source** | **timepoint-snag-bench** | **Quality Certifier — measures Causal Resolution across renderings** |
| **Billing** | Private | timepoint-billing | Payment Processing — Apple IAP + Stripe |
| **MCP** | Private | timepoint-mcp | MCP Server — AI agent access to Flash and Clockchain |
| **Web App** | Private | timepoint-web-app | Browser client at app.timepointai.com |
| **Landing** | Private | timepoint-landing | Marketing site at timepointai.com |
| **iPhone App** | Private | timepoint-iphone-app | iOS client — Synthetic Time Travel on mobile |
| **API Gateway** | Private | timepoint-api-gateway | Reverse proxy at api.timepointai.com |
| **Skip Meetings** | Private | skipmeetingsai | Meeting intelligence SaaS powered by Flash |

## License

Apache-2.0
