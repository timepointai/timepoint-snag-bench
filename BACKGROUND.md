# BACKGROUND — Source Repo Analysis

Reference document summarizing the three upstream repos that SNAG Bench scores against.

---

## 1. Timepoint Pro (Temporal Simulation Engine, formerly Daedalus)

### What It Is

The SNAG (Social Network Augmented Generation) engine. A Python framework that generates temporally-structured social simulations from natural language prompts or JSON templates. Entities (people, organizations, abstract forces) are placed in a social graph with tracked knowledge provenance, then advanced through time via LLM-driven state transitions.

### Core Architecture

- **19 composable mechanisms (M1-M19)** spanning 5 pillars: Fidelity Management (M1/M2/M5/M6), Temporal Reasoning (M7/M8/M12/M14/M17), Knowledge Provenance (M3/M4/M19), Entity Simulation (M9/M10/M11/M13/M15/M16), Infrastructure (M18).
- **5 temporal modes**, each with a dedicated strategy class:
  - **PEARL** — Forward causality. Strict knowledge provenance. No paradoxes. Default mode.
  - **PORTAL** — Backward inference from known outcomes. Generates candidate antecedent paths, scores plausibility. "How did we get here?"
  - **BRANCHING** — Counterfactual timelines. Decision point spawns parallel futures with independent causal chains.
  - **DIRECTORIAL** — Narrative-driven. Five-act arc engine, camera system, tension curves, dramatic irony detection.
  - **CYCLICAL** — Prophecy system, causal loops, cycle semantics (repeating, spiral, oscillating, composite).
- **Heterogeneous fidelity** — Entities exist at different resolution levels (TENSOR_ONLY ~200 tokens, SCENE, DIALOG, TRAINED). Resolution is allocated dynamically based on query attention and ADPRS waveform predictions.
- **Knowledge provenance** — Every fact has a tracked exposure event (who learned what, from whom, when). Entities can't magically know things.
- **SynthasAIzer / ADPRS** — Synthesizer paradigm for entity lifecycle. ADPRS envelopes (Attack, Decay, Plateau, Release, Sustain) model entity prominence over time. Waveform Sufficiency Ratio (WSR) predicts when full LLM dialog is needed vs. when tensor-level approximation suffices.

### Scoring-Relevant Components (Axis 2: Temporal Coherence)

| Component | Location | SNAG Bench Role |
|-----------|----------|-----------------|
| Quality gates (per-dialog, cross-dialog, full-run) | `workflows/dialog_synthesis.py` | Voice distinctiveness, entity consistency |
| Convergence validation | `validation/convergence.py` | Jaccard similarity across N runs of same template |
| Mechanism verification | `evaluation/` | Which of M1-M19 actually fired |
| ADPRS waveform predictions | `workflows/adprs_*.py` | Fidelity allocation accuracy |

### Convergence Evaluation (Critical for Axis 2)

Daedalus includes a convergence testing framework that runs the same template N times and measures:
- **Jaccard similarity** on causal graphs (entity-event pairs) across runs
- **Robustness grades**: A (>=90%), B (>=80%), C (>=70%), D (>=50%), F (<50%)
- **Divergence point detection** — identifies which template steps produce the most variance

This is the foundation for the SNAG Bench TCS (Temporal Coherence Score) convergence sub-metric.

### Templates

21 verified templates across categories (showcase, convergence, persona, core). Templates are JSON "patches" specifying entities, temporal mode, ADPRS envelopes, and mechanism requirements. Key templates for benchmarking:
- `castaway_colony_branching` — All 19 mechanisms, branching mode
- `mars_mission_portal` — Portal mode, backward reasoning
- `hound_shadow_directorial` — Directorial mode, narrative structure
- `board_meeting`, `jefferson_dinner` — PEARL mode, standard causality

### Scale

- 10 open-source models via OpenRouter ($0.15-$1.00/run)
- 329+ tests (unit + integration)
- Python 3.10+, FastAPI, Pydantic, pytest, ruff, mypy

---

## 2. Timepoint Flash (Scene Generation Pipeline)

### What It Is

A FastAPI backend that generates richly detailed historical/fictional scenes from natural language queries. The scene generation pipeline uses 14 specialized AI agents in sequence, producing grounded historical content with characters, dialog, camera directions, and optionally an image.

### Core Architecture

14-agent pipeline:
1. **Judge** — Routes queries, selects quality tier
2. **Timeline** — Extracts temporal coordinates (year, era, BCE support)
3. **Grounding** — Google Search verification of historical claims. Produces `GroundedContext` with `verified_location`, `verified_date`, `verified_participants`, `physical_participants`
4. **Scene** — World-building from grounded context
5. **Characters** — Entity creation with period-appropriate traits
6. **Moment** — Pivotal scene moment selection
7. **Camera** — Cinematic framing and composition
8. **Dialog** — Period-appropriate conversation with voice differentiation by social register
9. **Critique** — Anachronism detection, cultural error flagging, accuracy validation
10. **Image Prompt** — DALL-E/Imagen prompt construction
11. **Optimizer** — Prompt refinement for image quality
12. **Image Gen** — 3-tier image fallback (Imagen 3 → DALL-E 3 → Gemini)
13. **Narrator** — (context-dependent)
14. **Temporal** — Forward/backward time jumps, linked scene chains

### Scoring-Relevant Components (Axis 1: Grounding Fidelity)

| Component | Location | SNAG Bench Role |
|-----------|----------|-----------------|
| Grounding Agent | `agents/grounding.py` | Google Search verification. Outputs claims + verification status |
| Critique Agent | `agents/critique.py` | Anachronism detection, cultural errors. Produces `critique_passes` / `critique_total` |
| GroundedContext schema | `agents/grounding.py` | Structured output with `verified_*` fields |

The Grounding Survival Rate (GSR) formula: `((survived / total_claims) + (critique_passes / critique_total)) / 2`

### Scoring-Relevant Components (Axis 4: Human Judgment)

Flash scenes are the artifact that human raters evaluate. Each scene includes:
- Historical accuracy (grounding)
- Character authenticity (period-appropriate dialog, social register)
- Visual composition (camera, image)
- Narrative coherence (moment selection, scene structure)

Human raters score on: Historical Accuracy, Character Authenticity, Visual Composition, Narrative Coherence (1-5 each). HTP = mean of 4 subscales.

### Quality Presets

| Preset | Models | Cost |
|--------|--------|------|
| `hyper` | OpenRouter multi-model | Highest quality |
| `balanced` | Google Gemini 2.0 Flash | Default, good quality/cost |
| `hd` | Google Gemini 2.0 Flash | Higher image quality |
| `gemini3` | Gemini 2.5 Pro | Latest Gemini |

### Existing Eval Infrastructure

Flash has an `EVAL_ROADMAP.md` describing planned but not-yet-implemented evaluation:
- Quality scoring (LLM-as-Judge) — planned
- Pipeline evaluation — planned
- Benchmark dataset — planned
- Historical accuracy checker — planned
- Currently only tracks latency

This is exactly the gap SNAG Bench fills for Axis 1.

### Scale

- 630+ tests, FastAPI, PostgreSQL (production) / SQLite (dev)
- Google Gemini + OpenRouter model access
- JWT auth, credit system, Apple Sign-In for iOS
- 3-repo architecture: `timepoint-flash` (open source), `timepoint-flash-deploy` (Railway deployment), `timepoint-billing` (billing microservice)

---

## 3. Proteus Markets (Prediction Market Protocol)

### What It Is

A prediction market protocol on BASE (Coinbase L2) where users stake ETH on the exact text a public figure will post on X. Winners are determined by on-chain Levenshtein distance — the closest character-by-character match wins. v0 Alpha, proof of concept.

### Core Thesis

Binary prediction markets encode exactly one bit per contract. As AI approaches superhuman forecasting, binary market edge collapses to zero. Text prediction over an alphabet with strings up to length *n* has a combinatorially explosive outcome space. Levenshtein distance induces a proper metric making payoffs a continuous gradient surface where every character of precision is rewarded. The Levenshtein metric ensures the payoff function is Lipschitz-continuous — marginal improvements in language modeling *always* translate to marginal improvements in expected payout.

### Core Architecture

```
PredictionMarketV2 (Solidity, BASE Sepolia)
  - createSubmission(marketId, predictedText) payable
  - resolveMarket(marketId, actualText) onlyOwner
  - levenshteinDistance(a, b) pure → uint256
  - claimPayout(submissionId)
```

Supporting contracts: GenesisNFT (100 founder NFTs), PayoutManager (7% fee distribution), DecentralizedOracle (future), ActorRegistry, NodeRegistry.

### Scoring-Relevant Components (Axis 3: Predictive Precision)

| Component | Location | SNAG Bench Role |
|-----------|----------|-----------------|
| `levenshteinDistance(a, b)` | `PredictionMarketV2.sol` | On-chain edit distance computation |
| Market resolution | `resolveMarket()` | Ground truth comparison |
| Submission tracking | `createSubmission()` | Per-model prediction recording |
| Pool/stake data | `getMarketDetails()` | Market size for weighting |

The WMNED (Weighted Mean Normalized Edit Distance) formula:
- For each market: `ned = levenshteinDistance(prediction, actual) / max(len(prediction), len(actual))`
- Weight by market size (ETH staked): `wmned = sum(ned_i * pool_i) / sum(pool_i)`
- Lower is better (0 = perfect prediction, 1 = maximum distance)

### Contract Details

- **PredictionMarketV2**: `0x5174Da96BCA87c78591038DEe9DB1811288c9286` (BASE Sepolia)
- 7% platform fee, min stake 0.001 ETH, max text 280 chars
- Gas: resolution costs 1.5M-9M gas depending on text length (Levenshtein is O(m*n))
- 109 contract tests, 135 unit tests, 15 integration tests (259 total)

### Current Status

- Phase 0 (Prove the Primitive): COMPLETE
- Phase 0.5 (Worked Examples): COMPLETE — 6 examples showing AI vs human vs insider vs null
- Phase 1 (Validate Demand): NOT STARTED
- Not deployed to mainnet, no external audit

### Key Limitation for SNAG Bench

Resolution is currently centralized (single EOA). For SNAG Bench Axis 3, this means:
- Market resolution depends on a trusted operator fetching actual text from X
- Multi-oracle decentralized resolution is planned but not implemented
- X API now offers pay-per-use access (Feb 2026), making multi-oracle verification economically viable

---

## Cross-Repo Integration Map

How the three repos connect for SNAG Bench scoring:

```
SNAG Bench
├── Axis 1: Grounding Fidelity (GSR)
│   └── Calls Flash grounding + critique agents
│       └── timepoint-flash/agents/grounding.py
│       └── timepoint-flash/agents/critique.py
│
├── Axis 2: Temporal Coherence (TCS)
│   └── Runs Daedalus templates N times, measures convergence
│       └── timepoint-pro/validation/convergence.py
│       └── timepoint-pro/evaluation/
│       └── timepoint-pro/workflows/dialog_synthesis.py (quality gates)
│
├── Axis 3: Predictive Precision (WMNED)
│   └── Reads from Proteus on-chain markets
│       └── PredictionMarketV2 @ 0x5174...9286
│       └── levenshteinDistance() + market pool data
│
└── Axis 4: Human Judgment (HTP)
    └── Rates Flash-generated scenes
        └── timepoint-flash scene output (JSON)
        └── New: web rating interface (to build)
```

---

## What Already Exists vs What Needs Building

### Already Exists (in upstream repos)

- Flash grounding agent + critique agent (Axis 1 scoring components)
- Daedalus quality gates + convergence validation (Axis 2 scoring components)
- Daedalus 21 templates (Axis 2 task set — 9 of 21 selected for benchmark)
- Proteus PredictionMarketV2 with on-chain Levenshtein (Axis 3 scoring primitive)
- Proteus market lifecycle (create → submit → resolve → claim)

### Needs Building (in this repo: timepoint-snag-bench)

- Triple schema and JSONL submission format
- Scoring wrappers that call into upstream repos
- Composite score aggregation with configurable weights
- 60 Flash benchmark queries (Axis 1 task set)
- Axis 2 runner that executes Daedalus templates and computes TCS
- Axis 3 reader that queries Proteus contracts and computes WMNED
- Axis 4 web rating interface for human judgment
- Leaderboard computation and rendering
- CLI for running benchmarks
- CI pipeline for automated scoring
- Documentation (submission guide, scoring methodology)

---

*Generated from upstream repo analysis — February 2026*
