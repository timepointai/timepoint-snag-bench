"""Axis 4 — Human Temporal Plausibility (HTP) via LLM-as-human roleplayer.

Three diverse personas rate each scene on 4 dimensions (1-5 scale).
Scores are averaged and normalized to 0-1 for the HTP axis.

Supports two modes:
  - "quick" (default): Uses 3 built-in personas (historian, novelist, skeptic)
  - "custom": User provides their own rater prompt

The judge model is fixed (not the model being evaluated) to ensure
consistent cross-model scoring.
"""

import json
import os
from typing import Dict, Any, List, Optional

import httpx
from rich.console import Console

console = Console()

JUDGE_MODEL = "google/gemini-2.0-flash-001"

RATER_PERSONAS = [
    {
        "name": "historian",
        "system": (
            "You are Dr. Eleanor Voss, a meticulous historian specializing in "
            "temporal accuracy. You have published extensively on chronological "
            "errors in popular media. You are rigorous about dates, sequences, "
            "and causal chains. You penalize anachronisms harshly but appreciate "
            "when complex temporal relationships are handled with nuance."
        ),
    },
    {
        "name": "novelist",
        "system": (
            "You are Marcus Tanaka, a literary novelist known for historical "
            "fiction. You care deeply about whether a temporal scene feels "
            "emotionally authentic and narratively coherent. You value vivid "
            "period detail and believable character motivations within their "
            "historical moment. You are less strict about exact dates but very "
            "sensitive to anachronistic tone or behavior."
        ),
    },
    {
        "name": "skeptic",
        "system": (
            "You are Dr. Priya Sharma, a scientific skeptic and epistemologist. "
            "You focus on whether claims are properly hedged, whether confidence "
            "levels match available evidence, and whether the scene distinguishes "
            "between well-established facts and speculation. You actively look "
            "for overconfidence, unfounded assertions, and conflation of "
            "correlation with causation."
        ),
    },
]

RATING_PROMPT = """Rate this temporal scene on 4 dimensions. Score each 1-5 (1=poor, 5=excellent).

SCENE QUERY: {query}

SCENE DATA:
{scene_text}

Rate these dimensions:
1. temporal_accuracy: Are dates, sequences, and temporal relationships correct?
2. narrative_coherence: Does the scene hold together as a believable temporal narrative?
3. factual_grounding: Are claims supported by evidence? Is uncertainty acknowledged?
4. period_authenticity: Does the scene feel authentic to its time period?

You MUST respond with ONLY this exact JSON structure, no other text:
{{"temporal_accuracy": <1-5>, "narrative_coherence": <1-5>, "factual_grounding": <1-5>, "period_authenticity": <1-5>, "justification": "<2-3 sentences explaining your ratings>"}}"""


def _call_judge(
    system_prompt: str,
    user_prompt: str,
    api_key: str,
    model: str = JUDGE_MODEL,
) -> Optional[dict]:
    """Call OpenRouter with a judge persona. Returns parsed JSON or None."""
    try:
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 300,
            },
            timeout=60,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        # Extract JSON from response (handle markdown code blocks)
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        return json.loads(content)
    except Exception as e:
        console.print(f"  [dim]Judge call failed ({type(e).__name__}): {e}[/]")
        return None


def _format_scene(flash_data: dict, query: str) -> str:
    """Extract readable scene text from Flash API response."""
    parts = []

    if flash_data.get("title"):
        parts.append(f"Title: {flash_data['title']}")
    if flash_data.get("narrative") or flash_data.get("description"):
        parts.append(flash_data.get("narrative", flash_data.get("description", "")))

    # Entities
    entities = flash_data.get("entities", [])
    if entities:
        names = []
        for e in entities[:10]:
            if isinstance(e, dict):
                names.append(e.get("name", str(e)))
            else:
                names.append(str(e))
        parts.append(f"Entities: {', '.join(names)}")

    # Timepoints
    timepoints = flash_data.get("timepoints", [])
    if timepoints:
        tp_strs = []
        for tp in timepoints[:10]:
            if isinstance(tp, dict):
                tp_strs.append(tp.get("label", tp.get("date", str(tp))))
            else:
                tp_strs.append(str(tp))
        parts.append(f"Timepoints: {', '.join(tp_strs)}")

    # Grounding
    grounding = flash_data.get("grounding", {})
    if grounding:
        parts.append(f"Grounding confidence: {grounding.get('grounding_confidence', 'N/A')}")
        sources = grounding.get("sources", [])
        if sources:
            parts.append(f"Sources: {', '.join(str(s) for s in sources[:5])}")

    if not parts:
        parts.append(f"Query: {query}")
        parts.append("(No detailed scene data available)")

    return "\n".join(parts)


def evaluate_htp(
    query: str,
    flash_data: dict,
    api_key: Optional[str] = None,
    mode: str = "quick",
    custom_rater_prompt: Optional[str] = None,
) -> tuple[float, Dict[str, Any]]:
    """Rate a single scene with LLM-as-human raters.

    Returns (htp_score, evidence) where htp_score is 0-1.
    """
    if not api_key:
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        return 0.0, {"error": "No OPENROUTER_API_KEY available", "stub": True}

    scene_text = _format_scene(flash_data, query)
    user_prompt = RATING_PROMPT.format(query=query, scene_text=scene_text)

    if mode == "custom" and custom_rater_prompt:
        personas = [{"name": "custom", "system": custom_rater_prompt}]
    else:
        personas = RATER_PERSONAS

    all_ratings = []
    evidence = {"raters": [], "mode": mode}

    for persona in personas:
        result = _call_judge(persona["system"], user_prompt, api_key)
        if result is None:
            continue

        dims = {}
        for dim in ["temporal_accuracy", "narrative_coherence", "factual_grounding", "period_authenticity"]:
            val = result.get(dim)
            if isinstance(val, (int, float)) and 1 <= val <= 5:
                dims[dim] = val

        if len(dims) >= 3:  # accept if at least 3/4 dimensions parsed
            avg = sum(dims.values()) / len(dims)
            all_ratings.append(avg)
            evidence["raters"].append({
                "name": persona["name"],
                "scores": dims,
                "mean": round(avg, 3),
                "justification": result.get("justification", ""),
            })

    if not all_ratings:
        return 0.0, {**evidence, "error": "No valid ratings obtained"}

    # Normalize 1-5 scale to 0-1
    raw_mean = sum(all_ratings) / len(all_ratings)
    htp = (raw_mean - 1.0) / 4.0  # maps 1→0, 5→1

    evidence["raw_mean"] = round(raw_mean, 3)
    evidence["n_raters"] = len(all_ratings)

    return round(htp, 4), evidence
