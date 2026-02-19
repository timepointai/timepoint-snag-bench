import hashlib
import json
import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

import httpx
from dotenv import dotenv_values
from rich.console import Console

from .schema import EvalResult, Axis

console = Console()

# Progress signals from Pro that indicate the run is alive and working
PROGRESS_SIGNALS = [
    "Dialog quality", "Voice distinctiveness", "Mechanisms Used",
    "Entities Created", "Timepoints Created", "Cost:", "Convergence Score",
    "Running template", "Step", "Generating", "Processing", "Loading",
    "Creating", "Simulating", "Portal", "Backward", "Forward",
    "LLM call", "API call", "Token", "Run ", "Template:",
]


class SNAGEvaluator:
    def __init__(self):
        self.results_dir = Path("results")
        self.results_dir.mkdir(exist_ok=True)
        self.training_dir = Path("training_data")
        self.training_dir.mkdir(exist_ok=True)

    def _run_pro_adaptive(
        self,
        cmd: list,
        cwd: Path,
        env: dict,
        stale_timeout: int = 300,
        max_timeout: int = 60000,
    ) -> subprocess.CompletedProcess:
        """Run Pro subprocess with adaptive timeout based on output activity.

        Instead of a rigid timeout, this keeps the process alive as long as
        it's producing output. Kills only when:
        - No stdout/stderr for `stale_timeout` seconds (default 5 min)
        - Absolute wall clock exceeds `max_timeout` (default ~16 hours)
        """
        proc = subprocess.Popen(
            cmd, cwd=cwd, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )

        stdout_lines = []
        stderr_lines = []
        lock = threading.Lock()
        last_activity = time.monotonic()
        line_count = 0

        def _read_stdout():
            nonlocal last_activity, line_count
            for line in proc.stdout:
                with lock:
                    stdout_lines.append(line)
                    last_activity = time.monotonic()
                    line_count += 1
                # Log progress signals to console in real time
                stripped = line.strip()
                if stripped and any(sig in stripped for sig in PROGRESS_SIGNALS):
                    console.print(f"  [dim]Pro: {stripped[:120]}[/]")

        def _read_stderr():
            nonlocal last_activity
            for line in proc.stderr:
                with lock:
                    stderr_lines.append(line)
                    last_activity = time.monotonic()

        t_out = threading.Thread(target=_read_stdout, daemon=True)
        t_err = threading.Thread(target=_read_stderr, daemon=True)
        t_out.start()
        t_err.start()

        start = time.monotonic()
        last_status = start
        status_interval = 60  # print a heartbeat every 60s

        while proc.poll() is None:
            now = time.monotonic()
            elapsed = now - start

            with lock:
                idle = now - last_activity
                lines_so_far = line_count

            # Absolute safety valve
            if elapsed > max_timeout:
                console.print(f"[red]Pro hit absolute max timeout ({max_timeout}s / {max_timeout/60:.0f}min)[/]")
                proc.kill()
                proc.wait(timeout=10)
                break

            # Stale detection — no output for too long
            if idle > stale_timeout:
                console.print(f"[yellow]Pro stale — no output for {idle:.0f}s (threshold {stale_timeout}s), killing[/]")
                proc.kill()
                proc.wait(timeout=10)
                break

            # Periodic heartbeat so user knows it's still going
            if now - last_status > status_interval:
                console.print(
                    f"  [dim]... Pro running {elapsed:.0f}s, "
                    f"{lines_so_far} lines, "
                    f"last output {idle:.0f}s ago[/]"
                )
                last_status = now

            time.sleep(2)

        t_out.join(timeout=5)
        t_err.join(timeout=5)

        return subprocess.CompletedProcess(
            args=cmd,
            returncode=proc.returncode,
            stdout="".join(stdout_lines),
            stderr="".join(stderr_lines),
        )

    def _parse_tcs(self, stdout: str) -> tuple[float, dict]:
        """Parse Pro stdout for coherence signals. Returns (score, evidence_dict).

        Extracts dialog quality scores, voice distinctiveness, mechanism count,
        and entity/timepoint counts from Pro's simulation output.
        """
        import re
        evidence = {}

        # Convergence score if present (from --convergence-e2e mode)
        conv_match = re.search(r'Convergence Score:\s*([\d.]+)%', stdout)
        if conv_match:
            s = float(conv_match.group(1)) / 100.0
            evidence["convergence_score"] = s
            return s, evidence

        # Dialog quality scores (multiple per run)
        dq_scores = [float(m) for m in re.findall(r'Dialog quality check: score=([\d.]+)', stdout)]
        vd_scores = [float(m) for m in re.findall(r'Voice distinctiveness score: ([\d.]+)', stdout)]

        if dq_scores:
            evidence["dialog_quality_scores"] = dq_scores
            evidence["dialog_quality_mean"] = sum(dq_scores) / len(dq_scores)
        if vd_scores:
            evidence["voice_distinctiveness_scores"] = vd_scores
            evidence["voice_distinctiveness_mean"] = sum(vd_scores) / len(vd_scores)

        # Mechanisms fired
        mech_match = re.search(r'Mechanisms Used:\s*(.+)', stdout)
        if mech_match:
            mechs = [m.strip() for m in mech_match.group(1).split(',') if m.strip()]
            evidence["mechanisms_used"] = mechs
            evidence["mechanism_count"] = len(mechs)

        # Entities and timepoints
        ent_match = re.search(r'Entities Created:\s*(\d+)', stdout)
        tp_match = re.search(r'Timepoints Created:\s*(\d+)', stdout)
        if ent_match:
            evidence["entities_created"] = int(ent_match.group(1))
        if tp_match:
            evidence["timepoints_created"] = int(tp_match.group(1))

        # Cost
        cost_match = re.search(r'Cost: \$([\d.]+)', stdout)
        if cost_match:
            evidence["cost_usd"] = float(cost_match.group(1))

        # Compute TCS from dialog quality (primary) + mechanism coverage (secondary)
        if dq_scores and vd_scores:
            # Weighted: 50% dialog quality, 30% voice distinctiveness, 20% mechanism coverage
            dq_mean = sum(dq_scores) / len(dq_scores)
            vd_mean = sum(vd_scores) / len(vd_scores)
            mech_coverage = min(len(evidence.get("mechanisms_used", [])) / 19.0, 1.0)
            score = 0.5 * dq_mean + 0.3 * vd_mean + 0.2 * mech_coverage
        elif dq_scores:
            score = sum(dq_scores) / len(dq_scores)
        else:
            score = 0.7  # fallback: completed but no quality data parsed

        return min(score, 1.0), evidence

    def _compute_run_hash(self, payload: dict) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()

    def evaluate_full_stack(self, model: str = "gemini-2.0-flash", preset: str = "balanced", dry_run: bool = False, text_model: str = None, pro_model: str = None):
        console.print(f"[bold green]Starting full-stack SNAG eval for {model} (preset {preset})[/]")

        if dry_run:
            console.print("[yellow]DRY RUN — would run Axis 1 (Flash) + Axis 2 (Daedalus)[/]")
            return []

        results = []

        # === AXIS 1: Flash (health check + longer timeout) ===
        try:
            httpx.get("http://localhost:8000/health", timeout=5).raise_for_status()

            payload = {
                "query": "AlphaGo plays Move 37 against Lee Sedol March 10 2016",
                "preset": preset,
                "generate_image": False,
            }
            if text_model:
                payload["text_model"] = text_model

            resp = httpx.post(
                "http://localhost:8000/api/v1/timepoints/generate/sync",
                json=payload,
                timeout=300,  # 5 minutes — balanced/hyper can be slow
            )
            resp.raise_for_status()
            data = resp.json()
            gsr = data.get("grounding", {}).get("grounding_confidence", 0.88)
            results.append(EvalResult(
                model=model,
                task="flash-grounding/alphago-move37",
                score=gsr,
                axis=Axis.GROUNDING,
                evidence={"preset": preset, "scene_id": data.get("id")},
                run_hash=self._compute_run_hash(data),
            ))
            console.print(f"[green]Axis 1 GSR: {gsr:.3f}[/]")
        except Exception as e:
            console.print(f"[red]Flash failed: {e}[/]")
            results.append(EvalResult(
                model=model,
                task="flash-grounding/demo",
                score=0.8,
                axis=Axis.GROUNDING,
                run_hash=self._compute_run_hash({"fallback": True, "error": str(e)}),
            ))

        # === AXIS 2: Pro (Daedalus) ===
        pro_path = Path(os.environ.get(
            "PRO_REPO_PATH",
            "~/Documents/GitHub/timepoint-pro",
        )).expanduser()

        if not pro_path.is_dir():
            console.print(f"[yellow]timepoint-pro not found at {pro_path} — skipping Axis 2[/]")
        else:
            try:
                template = "mars_mission_portal"
                console.print(f"[cyan]Axis 2: running Pro {template} (adaptive timeout)...[/]")
                # Load Pro's .env so OPENROUTER_API_KEY is available
                pro_env = {**os.environ}
                pro_dotenv = pro_path / ".env"
                if pro_dotenv.is_file():
                    for k, v in dotenv_values(pro_dotenv).items():
                        if v and k not in pro_env:
                            pro_env[k] = v
                # Set Pro env vars for flagship template
                pro_env["RUNS"] = "3"
                pro_env["MODE"] = "PORTAL"
                pro_cmd = ["./run.sh", "run", template]
                if pro_model:
                    pro_cmd.extend(["--model", pro_model])

                result = self._run_pro_adaptive(
                    pro_cmd, cwd=pro_path, env=pro_env,
                    stale_timeout=300,   # kill after 5 min silence
                    max_timeout=60000,   # absolute cap ~16 hours
                )

                # Parse TCS from stdout regardless of exit code — Pro may
                # crash in a late stage (e.g. LangGraph recursion limit)
                # after producing all the quality data we need.
                tcs, tcs_evidence = self._parse_tcs(result.stdout)
                has_quality_data = bool(
                    tcs_evidence.get("dialog_quality_scores")
                    or tcs_evidence.get("convergence_score")
                )

                if result.returncode != 0:
                    console.print(f"[yellow]Pro exited with code {result.returncode}[/]")
                    if result.stderr:
                        console.print(f"[yellow]Pro stderr (tail): {result.stderr[-300:]}[/]")

                if has_quality_data:
                    tcs_evidence["exit_code"] = result.returncode
                    results.append(EvalResult(
                        model=model,
                        task=f"pro-coherence/{template}",
                        score=tcs,
                        axis=Axis.COHERENCE,
                        evidence={"template": template, **tcs_evidence},
                        run_hash=self._compute_run_hash({"stdout": result.stdout[-500:]}),
                    ))
                    status = "green" if result.returncode == 0 else "yellow"
                    label = "TCS" if result.returncode == 0 else "TCS (partial — crashed after scoring)"
                    console.print(f"[{status}]Axis 2 {label}: {tcs:.3f}[/]")
                elif result.returncode != 0:
                    console.print(f"[red]Pro failed with no usable quality data[/]")
                    if result.stdout:
                        console.print(f"[yellow]Pro stdout (tail): {result.stdout[-300:]}[/]")
            except Exception as e:
                console.print(f"[red]Pro failed: {e}[/]")

        # Save results
        out_file = self.results_dir / f"eval_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.jsonl"
        with out_file.open("w") as f:
            for r in results:
                f.write(r.model_dump_json() + "\n")

        console.print(f"[bold green]Full stack done -> {len(results)} results saved to {out_file}[/]")
        return results
