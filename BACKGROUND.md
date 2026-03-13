# BACKGROUND — Upstream Service Analysis

Reference document for the three upstream repos that SNAG Bench scores against, plus the deployment and integration layer.

**Status (Feb 2026):** Axis 1 (GSR) and Axis 2 (TCS) are active. Axis 3 (WMNED) is stubbed pending Proteus mainnet. Axis 4 (HTP) is active via LLM-as-human roleplayer.

---

## 1. Timepoint Pro (SNAG Engine)

The Social Network Augmented Generation engine. Generates multi-agent social simulations with structured causal provenance from natural language prompts or JSON templates.

### Core Architecture

- **19 composable mechanisms (M1-M19)** spanning 5 pillars: Fidelity, Temporal Reasoning, Knowledge Provenance, Entity Simulation, Infrastructure
- **5 temporal modes**: PEARL (forward causality), PORTAL (backward inference), BRANCHING (counterfactual), DIRECTORIAL (narrative-driven), CYCLICAL (prophecy loops)
- **21 verified templates** across categories (showcase, convergence, persona, core)
- **Heterogeneous fidelity** — entities at different resolution levels, dynamically allocated

### SNAG Bench Role (Axis 2: TCS)

Runs the `mars_mission_portal` template through Pro's adaptive timeout runner. Measures:
- Dialog quality (50%): naturalness and contextual appropriateness
- Voice distinctiveness (30%): character voice maintenance
- Mechanism coverage (20%): how many of 19 mechanisms activate

### Deployment

- **Open source**: `timepointai/timepoint-pro` (CLI, local execution)
- **Cloud**: Available as a hosted API service

---

## 2. Timepoint Flash (Scene Generation Pipeline)

FastAPI backend that generates richly detailed historical/fictional scenes. 14 specialized AI agents in sequence produce grounded content with characters, dialog, camera directions, and images.

### Core Architecture

14-agent pipeline: Judge → Timeline → **Grounding** → Scene → Characters → Moment → Camera → Dialog → **Critique** → Image Prompt → Optimizer → Image Gen → Narrator → Temporal

### SNAG Bench Role (Axis 1: GSR)

For each of 60 tasks, Flash generates a temporal scene. The grounding confidence score (`data.grounding.grounding_confidence`) measures how well temporal claims survive fact-checking.

### SNAG Bench Role (Axis 4: HTP)

Flash scenes are the artifacts that LLM-as-human raters evaluate. Each scene's narrative, dialog, and temporal claims are scored on 4 dimensions by 3 personas.

### Deployment

- **Open source**: `timepointai/timepoint-flash` (engine code)

---

## 3. Proteus Markets (Prediction Market Protocol)

Prediction market on BASE (Coinbase L2) where users stake ETH on exact text predictions. Winners determined by on-chain Levenshtein distance.

### SNAG Bench Role (Axis 3: WMNED)

**Currently stubbed.** When Proteus goes to mainnet, this axis will measure predictive precision via Weighted Mean Normalized Edit Distance from resolved market outcomes.

The stub uses 10 fake resolved markets with realistic error distributions (raw WMNED 0.05–0.43, score = 1 - mean = 0.817).

### Status

- Phase 0 (Prove the Primitive): COMPLETE
- Phase 0.5 (Worked Examples): COMPLETE
- Phase 1 (Validate Demand): NOT STARTED
- Not deployed to mainnet, no external audit

---

*Updated February 2026*
