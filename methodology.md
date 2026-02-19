# SNAG Bench Methodology

## Overview

SNAG Bench evaluates temporal reasoning capability across 4 axes using 60 fixed tasks at 3 difficulty tiers. The benchmark is designed to remain challenging through at least 2030.

## Axes

| Axis | Abbrev | Weight | Source |
|------|--------|--------|--------|
| Grounding Survival Rate | GSR | 25% | Flash API grounding confidence |
| Temporal Coherence Score | TCS | 30% | Pro/Daedalus dialog quality + mechanism coverage |
| Weighted Mean Normalized Error Distance | WMNED | 25% | Predictive markets (currently stubbed) |
| Human Temporal Plausibility | HTP | 20% | LLM-as-human roleplayer panel |

### Axis 1 — GSR (Grounding Survival Rate)

For each of 60 task queries, the model generates a temporal scene through the Flash API. The grounding confidence score measures how well the model's temporal claims survive fact-checking against verified sources.

- Source: `data.grounding.grounding_confidence` from Flash `/generate/sync`
- Range: 0.0–1.0
- Per-task scores are difficulty-weighted (see Calibration below)

### Axis 2 — TCS (Temporal Coherence Score)

The model runs a flagship simulation template (`mars_mission_portal`) through the Pro/Daedalus engine. TCS measures:

- Dialog quality (50%): How natural and contextually appropriate is the generated dialog?
- Voice distinctiveness (30%): Can the model maintain distinct character voices?
- Mechanism coverage (20%): How many of 19 temporal mechanisms does the model activate?

TCS is a single score per model (not per-task), derived from the template run.

### Axis 3 — WMNED (Weighted Mean Normalized Error Distance)

**Currently stubbed.** When Proteus (the prediction engine) goes live, this axis will measure how well the model predicts outcomes of temporal forecasting questions. The stub uses 10 fake resolved markets with realistic error distributions (raw WMNED 0.05–0.43).

We report `1 - mean_WMNED_raw` so that higher = better, consistent with other axes.

### Axis 4 — HTP (Human Temporal Plausibility)

Three LLM-roleplayed human raters evaluate each scene:

| Rater | Persona | Focus |
|-------|---------|-------|
| Historian | Dr. Eleanor Voss | Temporal accuracy, chronological precision |
| Novelist | Marcus Tanaka | Narrative coherence, period authenticity |
| Skeptic | Dr. Priya Sharma | Epistemic rigor, proper uncertainty hedging |

Each rater scores 4 dimensions (1–5):
1. **Temporal accuracy** — dates, sequences, causal ordering
2. **Narrative coherence** — internal consistency of the temporal narrative
3. **Factual grounding** — evidence basis, uncertainty acknowledgment
4. **Period authenticity** — anachronism avoidance, contextual fidelity

HTP = mean across raters and dimensions, normalized from 1–5 to 0–1.

The judge model is fixed (currently Gemini 2.0 Flash via OpenRouter) to ensure consistent scoring across all evaluated models.

## Task Set

60 fixed tasks across 3 tiers:

| Tier | Label | Count | Difficulty | Weight | Purpose |
|------|-------|-------|------------|--------|---------|
| 1 | Easy | 20 | 0.10–0.30 | 1.0x | Well-documented events, establishes baseline |
| 2 | Medium | 20 | 0.40–0.65 | 1.5x | Moderate documentation, requires deeper knowledge |
| 3 | Hard | 20 | 0.70–1.00 | 2.5x | Adversarial: sparse docs, contested dates, temporal traps |

Tasks are frozen at each version. To add tasks, create a new version.

## Calibration

### Difficulty Weighting

Per-axis scores use difficulty-weighted averaging:

```
axis_score = Σ(task_score × tier_weight) / Σ(tier_weight)
```

Effective weight distribution across 60 tasks:
- Tier 1: 20 × 1.0 = 20 (20% of total weight)
- Tier 2: 20 × 1.5 = 30 (30% of total weight)
- Tier 3: 20 × 2.5 = 50 (50% of total weight)

This means Tier 3 performance dominates the final score. A model scoring 1.0 on all Tier 1 tasks but 0.4 on Tier 3 gets a weighted GSR of ~0.58, not 0.80.

### Longevity Targets

| Year | Expected Frontier Composite | Rationale |
|------|---------------------------|-----------|
| 2026 | 0.65–0.80 | Current models struggle on Tier 3 adversarial tasks |
| 2028 | 0.78–0.88 | Better temporal grounding, still challenged by ambiguity |
| 2030 | 0.85–0.95 | Near-ceiling on Tier 1–2, Tier 3 remains hard |
| Saturation | ~0.97 | Theoretical ceiling — some tasks have genuinely uncertain answers |

### Why It Won't Saturate

Tier 3 tasks are designed with properties that resist saturation:

1. **Contested dates**: Multiple scholarly positions (e.g., Library of Alexandria destruction)
2. **Temporal layering**: Events with creation/discovery/recognition dates (e.g., Antikythera mechanism)
3. **Deep time uncertainty**: Archaeological dating with wide error bars (e.g., Göbekli Tepe)
4. **Causal lag**: Cause and effect separated by months/years (e.g., Tambora → Year Without a Summer)
5. **Knowledge loss**: Events where information was deliberately destroyed (e.g., Greek Fire)
6. **Epistemic traps**: Confident dating but unknown content (e.g., Voynich manuscript)

Even a perfect model cannot score 1.0 on tasks where the ground truth is genuinely uncertain.

### Composite Formula

```
composite = Σ(axis_weight × axis_score) / Σ(available_axis_weights)
```

Weights are renormalized over available axes, so missing axes (e.g., WMNED when Proteus isn't live) don't penalize models.

## Leaderboard Rules

1. **External models only**: The public leaderboard shows third-party LLMs (Gemini, Claude, Grok, Llama, etc.). Timepoint engine self-validation runs are excluded.
2. **Best score per axis**: If a model has multiple runs, the leaderboard shows the best score per axis.
3. **Reproducibility**: All results include run hashes and task version references.
4. **Transparency**: Raw JSONL results are published alongside the leaderboard.

## Known Limitations

1. **Axis 3 is stubbed**: WMNED scores are fake until Proteus is integrated. The stub values are designed to be realistic but do not reflect actual model capability.
2. **Axis 4 uses LLM judges, not real humans**: HTP scores approximate human judgment but are not ground truth. Judge model bias is a real concern.
3. **Single judge model**: All HTP ratings use the same judge model. A different judge would produce different scores.
4. **Axis 2 is template-bound**: TCS uses a single template (mars_mission_portal). Different templates would yield different scores.
5. **Flash dependency**: Axis 1 requires the Flash API server. Models are evaluated through Flash's grounding pipeline, not in isolation.
6. **Task set bias**: 60 tasks cannot cover all temporal reasoning. Western historical events are overrepresented.
7. **No adversarial robustness testing**: We don't test whether models can be prompted to give wrong temporal answers.
8. **Calibration is theoretical**: The 2026–2030 targets are estimates based on current model capabilities, not empirical projections.

## Versioning

- Task sets are immutable per version (see `tasks/version.json`)
- Scoring methodology changes require a version bump
- Results are tagged with the benchmark version for reproducibility
