import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import httpx
from dotenv import dotenv_values
from rich.console import Console
from timepoint_tdf import TDFRecord

from .schema import eval_record, Axis
from .calibration import load_tasks_by_tier, difficulty_weighted_score
from .axes.predictive import evaluate_predictive_stub
from .axes.human import evaluate_htp
from .axes.coverage import evaluate_coverage_stub

console = Console()

# Configurable service URLs (defaults to local dev, overridden by Railway runner)
FLASH_URL = os.environ.get("FLASH_URL", "http://localhost:8000")
FLASH_SERVICE_KEY = os.environ.get("FLASH_SERVICE_KEY", "")
PRO_URL = os.environ.get("PRO_URL", "")
PRO_API_KEY = os.environ.get("PRO_API_KEY", "")


def _flash_headers() -> dict:
    """Build headers for Flash API requests (includes service key if configured)."""
    headers = {}
    if FLASH_SERVICE_KEY:
        headers["X-Service-Key"] = FLASH_SERVICE_KEY
    return headers


# Progress signals from Pro that indicate the run is alive and working
PROGRESS_SIGNALS = [
    "Dialog quality",
    "Voice distinctiveness",
    "Mechanisms Used",
    "Entities Created",
    "Timepoints Created",
    "Cost:",
    "Convergence Score",
    "Running template",
    "Step",
    "Generating",
    "Processing",
    "Loading",
    "Creating",
    "Simulating",
    "Portal",
    "Backward",
    "Forward",
    "LLM call",
    "API call",
    "Token",
    "Run ",
    "Template:",
]


class SNAGEvaluator:
    def __init__(self):
        self.results_dir = Path("results")
        self.results_dir.mkdir(exist_ok=True)
        self.training_dir = Path("training_data")
        self.training_dir.mkdir(exist_ok=True)

    # ── Adaptive Pro runner ──────────────────────────────────────────

    def _run_pro_adaptive(
        self,
        cmd: list,
        cwd: Path,
        env: dict,
        stale_timeout: int = 300,
        max_timeout: int = 60000,
    ) -> subprocess.CompletedProcess:
        """Run Pro subprocess with adaptive timeout based on output activity."""
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
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
        status_interval = 60

        while proc.poll() is None:
            now = time.monotonic()
            elapsed = now - start
            with lock:
                idle = now - last_activity
                lines_so_far = line_count

            if elapsed > max_timeout:
                console.print(f"[red]Pro hit absolute max timeout ({max_timeout}s)[/]")
                proc.kill()
                proc.wait(timeout=10)
                break

            if idle > stale_timeout:
                console.print(
                    f"[yellow]Pro stale — no output for {idle:.0f}s, killing[/]"
                )
                proc.kill()
                proc.wait(timeout=10)
                break

            if now - last_status > status_interval:
                console.print(
                    f"  [dim]... Pro running {elapsed:.0f}s, {lines_so_far} lines, last output {idle:.0f}s ago[/]"
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

    # ── TCS parser ───────────────────────────────────────────────────

    def _parse_tcs(self, stdout: str) -> tuple[float, dict]:
        """Parse Pro stdout for coherence signals."""
        import re

        evidence = {}

        conv_match = re.search(r"Convergence Score:\s*([\d.]+)%", stdout)
        if conv_match:
            s = float(conv_match.group(1)) / 100.0
            evidence["convergence_score"] = s
            return s, evidence

        dq_scores = [
            float(m)
            for m in re.findall(r"Dialog quality check: score=([\d.]+)", stdout)
        ]
        vd_scores = [
            float(m)
            for m in re.findall(r"Voice distinctiveness score: ([\d.]+)", stdout)
        ]

        if dq_scores:
            evidence["dialog_quality_scores"] = dq_scores
            evidence["dialog_quality_mean"] = sum(dq_scores) / len(dq_scores)
        if vd_scores:
            evidence["voice_distinctiveness_scores"] = vd_scores
            evidence["voice_distinctiveness_mean"] = sum(vd_scores) / len(vd_scores)

        mech_match = re.search(r"Mechanisms Used:\s*(.+)", stdout)
        if mech_match:
            mechs = [m.strip() for m in mech_match.group(1).split(",") if m.strip()]
            evidence["mechanisms_used"] = mechs
            evidence["mechanism_count"] = len(mechs)

        ent_match = re.search(r"Entities Created:\s*(\d+)", stdout)
        tp_match = re.search(r"Timepoints Created:\s*(\d+)", stdout)
        if ent_match:
            evidence["entities_created"] = int(ent_match.group(1))
        if tp_match:
            evidence["timepoints_created"] = int(tp_match.group(1))

        cost_match = re.search(r"Cost: \$([\d.]+)", stdout)
        if cost_match:
            evidence["cost_usd"] = float(cost_match.group(1))

        if dq_scores and vd_scores:
            dq_mean = sum(dq_scores) / len(dq_scores)
            vd_mean = sum(vd_scores) / len(vd_scores)
            mech_coverage = min(len(evidence.get("mechanisms_used", [])) / 19.0, 1.0)
            score = 0.5 * dq_mean + 0.3 * vd_mean + 0.2 * mech_coverage
        elif dq_scores:
            score = sum(dq_scores) / len(dq_scores)
        else:
            score = 0.7

        return min(score, 1.0), evidence

    # ── Axis 1: Flash grounding (per-task) ───────────────────────────

    def _run_axis1_tasks(
        self,
        model: str,
        tasks: List[dict],
        preset: str = "balanced",
        text_model: str = None,
        out_file: Path = None,
    ) -> List[TDFRecord]:
        """Run each task through Flash and collect GSR scores."""
        results = []

        # Check Flash health once
        try:
            httpx.get(
                f"{FLASH_URL}/health", headers=_flash_headers(), timeout=5
            ).raise_for_status()
        except Exception as e:
            console.print(f"[red]Flash not available: {e} — skipping Axis 1[/]")
            return results

        console.print(
            f"[cyan]Axis 1 (GSR): Running {len(tasks)} tasks through Flash...[/]"
        )

        for i, task in enumerate(tasks, 1):
            task_id = task["id"]
            query = task["query"]
            tier = task["tier"]

            try:
                payload = {"query": query, "preset": preset, "generate_image": False}
                if text_model:
                    payload["text_model"] = text_model

                resp = httpx.post(
                    f"{FLASH_URL}/api/v1/timepoints/generate/sync",
                    json=payload,
                    headers=_flash_headers(),
                    timeout=300,
                )
                resp.raise_for_status()
                data = resp.json()
                gsr = data.get("grounding", {}).get("grounding_confidence", 0.0)

                result = eval_record(
                    model=model,
                    task=f"flash-grounding/{task_id}",
                    score=min(max(gsr, 0.0), 1.0),
                    axis=Axis.GROUNDING,
                    task_id=task_id,
                    tier=tier,
                    evidence={
                        "preset": preset,
                        "query": query,
                        "scene_id": data.get("id"),
                        "flash_data": {
                            k: data.get(k)
                            for k in [
                                "title",
                                "narrative",
                                "description",
                                "entities",
                                "timepoints",
                                "grounding",
                            ]
                            if data.get(k) is not None
                        },
                    },
                )
                results.append(result)

                # Incremental save
                if out_file:
                    with out_file.open("a") as f:
                        f.write(result.model_dump_json() + "\n")

                console.print(
                    f"  [{'green' if gsr >= 0.7 else 'yellow'}][{i}/{len(tasks)}] {task_id} (T{tier}): GSR {gsr:.3f}[/]"
                )

            except Exception as e:
                console.print(f"  [red][{i}/{len(tasks)}] {task_id}: failed — {e}[/]")

        return results

    # ── Axis 2: Pro coherence (per-model) ────────────────────────────

    def _run_axis2_cloud(
        self,
        model: str,
        out_file: Path = None,
    ) -> List[TDFRecord]:
        """Run Pro via Cloud API for TCS score."""
        results = []
        template = "showcase/mars_mission_portal"
        console.print(f"[cyan]Axis 2 (TCS): Running Pro Cloud API ({template})...[/]")

        try:
            headers = {
                "X-API-Key": PRO_API_KEY,
                "Content-Type": "application/json",
            }

            # Create job
            create_resp = httpx.post(
                f"{PRO_URL}/api/jobs",
                headers=headers,
                json={
                    "template_id": template,
                    "temporal_mode": "portal",
                    "entity_count": 4,
                    "timepoint_count": 10,
                    "budget_limit_usd": 5.0,
                },
                timeout=30,
            )
            create_resp.raise_for_status()
            job = create_resp.json()
            job_id = job["id"]
            console.print(f"  [dim]Pro Cloud job created: {job_id}[/]")

            # Poll until completed/failed (max 1 hour)
            max_polls = 120  # 120 * 30s = 1 hour
            for poll_num in range(max_polls):
                time.sleep(30)
                poll_resp = httpx.get(
                    f"{PRO_URL}/api/jobs/{job_id}",
                    headers=headers,
                    timeout=15,
                )
                poll_resp.raise_for_status()
                status = poll_resp.json().get("status", "unknown")

                if poll_num % 4 == 0:  # Log every 2 minutes
                    console.print(
                        f"  [dim]Pro Cloud: {status} (poll {poll_num + 1})...[/]"
                    )

                if status == "completed":
                    break
                elif status == "failed":
                    error_msg = poll_resp.json().get("error", "unknown error")
                    console.print(f"[red]Pro Cloud job failed: {error_msg}[/]")
                    return results
            else:
                console.print(
                    f"[red]Pro Cloud job timed out after {max_polls * 30}s[/]"
                )
                return results

            # Get results
            result_resp = httpx.get(
                f"{PRO_URL}/api/results/{job_id}",
                headers=headers,
                timeout=30,
            )
            result_resp.raise_for_status()
            result_json = result_resp.json()

            # Parse TCS from cloud result
            tcs, tcs_evidence = self._parse_tcs_cloud(result_json)
            tcs_evidence["source"] = "cloud_api"
            tcs_evidence["job_id"] = job_id

            result = eval_record(
                model=model,
                task=f"pro-coherence/{template}",
                score=tcs,
                axis=Axis.COHERENCE,
                evidence={"template": template, **tcs_evidence},
            )
            results.append(result)
            if out_file:
                with out_file.open("a") as f:
                    f.write(result.model_dump_json() + "\n")
            console.print(f"[green]Axis 2 TCS (cloud): {tcs:.3f}[/]")

        except Exception as e:
            console.print(f"[red]Pro Cloud failed: {e}[/]")

        return results

    def _parse_tcs_cloud(self, result_json: dict) -> tuple[float, dict]:
        """Parse TCS from Pro Cloud API result_json."""
        evidence = {}

        # Cloud results may contain structured data directly
        result_data = result_json.get("result_json", result_json)

        # Extract entity/timepoint/dialog counts
        entities = result_data.get("entities", [])
        timepoints = result_data.get("timepoints", [])
        dialogs = result_data.get("dialogs", [])
        cost = result_data.get("cost", result_json.get("cost"))

        evidence["entities_created"] = (
            len(entities) if isinstance(entities, list) else 0
        )
        evidence["timepoints_created"] = (
            len(timepoints) if isinstance(timepoints, list) else 0
        )
        evidence["dialog_count"] = len(dialogs) if isinstance(dialogs, list) else 0

        if cost is not None:
            evidence["cost_usd"] = float(cost) if not isinstance(cost, float) else cost

        # Look for quality metrics in the result
        convergence = result_data.get("convergence_score")
        if convergence is not None:
            s = float(convergence)
            if s > 1.0:
                s = s / 100.0  # handle percentage format
            evidence["convergence_score"] = s
            return s, evidence

        dq_scores = result_data.get("dialog_quality_scores", [])
        vd_scores = result_data.get("voice_distinctiveness_scores", [])

        if dq_scores:
            evidence["dialog_quality_scores"] = dq_scores
            evidence["dialog_quality_mean"] = sum(dq_scores) / len(dq_scores)
        if vd_scores:
            evidence["voice_distinctiveness_scores"] = vd_scores
            evidence["voice_distinctiveness_mean"] = sum(vd_scores) / len(vd_scores)

        mechanisms = result_data.get("mechanisms_used", [])
        if mechanisms:
            evidence["mechanisms_used"] = mechanisms
            evidence["mechanism_count"] = len(mechanisms)

        # Compute composite TCS
        if dq_scores and vd_scores:
            dq_mean = sum(dq_scores) / len(dq_scores)
            vd_mean = sum(vd_scores) / len(vd_scores)
            mech_coverage = min(len(mechanisms) / 19.0, 1.0)
            score = 0.5 * dq_mean + 0.3 * vd_mean + 0.2 * mech_coverage
        elif dq_scores:
            score = sum(dq_scores) / len(dq_scores)
        else:
            # Fallback: estimate from entity/dialog counts
            entity_score = min(evidence["entities_created"] / 4.0, 1.0)
            dialog_score = min(evidence["dialog_count"] / 10.0, 1.0)
            score = (
                0.6 * dialog_score + 0.4 * entity_score
                if evidence["dialog_count"] > 0
                else 0.7
            )

        return min(score, 1.0), evidence

    def _run_axis2(
        self,
        model: str,
        pro_model: str = None,
        out_file: Path = None,
    ) -> List[TDFRecord]:
        """Run Pro template for TCS score.

        Prefers Pro Cloud API (PRO_URL + PRO_API_KEY) if configured.
        Falls back to local subprocess if Pro repo is available.
        """
        # Try cloud API first
        if PRO_URL and PRO_API_KEY:
            return self._run_axis2_cloud(model, out_file=out_file)

        results = []
        pro_path = Path(
            os.environ.get(
                "PRO_REPO_PATH",
                "~/Documents/GitHub/timepoint-pro",
            )
        ).expanduser()

        if not pro_path.is_dir():
            console.print(
                f"[yellow]timepoint-pro not found at {pro_path} and no PRO_URL configured — skipping Axis 2[/]"
            )
            return results

        template = "mars_mission_portal"
        console.print(
            f"[cyan]Axis 2 (TCS): Running Pro {template} (adaptive timeout)...[/]"
        )

        try:
            pro_env = {**os.environ}
            pro_dotenv = pro_path / ".env"
            if pro_dotenv.is_file():
                for k, v in dotenv_values(pro_dotenv).items():
                    if v and k not in pro_env:
                        pro_env[k] = v
            pro_env["RUNS"] = "3"
            pro_env["MODE"] = "PORTAL"

            pro_cmd = ["./run.sh", "run", template]
            if pro_model:
                pro_cmd.extend(["--model", pro_model])

            run_result = self._run_pro_adaptive(
                pro_cmd,
                cwd=pro_path,
                env=pro_env,
                stale_timeout=300,
                max_timeout=60000,
            )

            tcs, tcs_evidence = self._parse_tcs(run_result.stdout)
            has_quality_data = bool(
                tcs_evidence.get("dialog_quality_scores")
                or tcs_evidence.get("convergence_score")
            )

            if run_result.returncode != 0:
                console.print(
                    f"[yellow]Pro exited with code {run_result.returncode}[/]"
                )

            if has_quality_data:
                tcs_evidence["exit_code"] = run_result.returncode
                result = eval_record(
                    model=model,
                    task=f"pro-coherence/{template}",
                    score=tcs,
                    axis=Axis.COHERENCE,
                    evidence={"template": template, **tcs_evidence},
                )
                results.append(result)
                if out_file:
                    with out_file.open("a") as f:
                        f.write(result.model_dump_json() + "\n")
                console.print(f"[green]Axis 2 TCS: {tcs:.3f}[/]")
            else:
                console.print("[red]Pro failed with no usable quality data[/]")
        except Exception as e:
            console.print(f"[red]Pro failed: {e}[/]")

        return results

    # ── Axis 3: Predictive stub ──────────────────────────────────────

    def _run_axis3(self, model: str, out_file: Path = None) -> List[TDFRecord]:
        """Return stubbed WMNED score."""
        console.print("[cyan]Axis 3 (WMNED): Returning stub scores...[/]")
        score, evidence = evaluate_predictive_stub()
        result = eval_record(
            model=model,
            task="predictive-stub/10-markets",
            score=score,
            axis=Axis.PREDICTIVE,
            evidence=evidence,
        )
        if out_file:
            with out_file.open("a") as f:
                f.write(result.model_dump_json() + "\n")
        console.print(f"[green]Axis 3 WMNED: {score:.3f} (stub)[/]")
        return [result]

    # ── Axis 5: Coverage stub ───────────────────────────────────────

    def _run_axis5(self, model: str, out_file: Path = None) -> List[TDFRecord]:
        """Return stubbed GCQ score."""
        console.print("[cyan]Axis 5 (GCQ): Returning stub scores...[/]")
        score, evidence = evaluate_coverage_stub()
        result = eval_record(
            model=model,
            task="coverage-stub/gcq",
            score=score,
            axis=Axis.COVERAGE,
            evidence=evidence,
        )
        if out_file:
            with out_file.open("a") as f:
                f.write(result.model_dump_json() + "\n")
        console.print(f"[green]Axis 5 GCQ: {score:.3f} (stub)[/]")
        return [result]

    # ── Axis 4: HTP (per-task) ───────────────────────────────────────

    def _run_axis4_tasks(
        self,
        model: str,
        tasks: List[dict],
        axis1_results: List[TDFRecord],
        out_file: Path = None,
    ) -> List[TDFRecord]:
        """Run LLM-as-human rating for each task that has Axis 1 data."""
        results = []

        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            # Try loading from Pro .env
            pro_env_path = Path("~/Documents/GitHub/timepoint-pro/.env").expanduser()
            if pro_env_path.is_file():
                for k, v in dotenv_values(pro_env_path).items():
                    if k == "OPENROUTER_API_KEY" and v:
                        api_key = v
                        break

        if not api_key:
            console.print("[yellow]No OPENROUTER_API_KEY — skipping Axis 4[/]")
            return results

        # Build lookup of Axis 1 flash_data by task_id
        flash_data_by_task = {}
        for r in axis1_results:
            r_task_id = r.payload.get("task_id")
            r_evidence = r.payload.get("evidence", {})
            if r_task_id and r_evidence.get("flash_data"):
                flash_data_by_task[r_task_id] = r_evidence["flash_data"]

        console.print(
            f"[cyan]Axis 4 (HTP): Rating {len(tasks)} tasks with 5 LLM raters (penalty scoring)...[/]"
        )

        for i, task in enumerate(tasks, 1):
            task_id = task["id"]
            query = task["query"]
            tier = task["tier"]
            flash_data = flash_data_by_task.get(task_id, {})

            try:
                htp, evidence = evaluate_htp(
                    query=query,
                    flash_data=flash_data,
                    api_key=api_key,
                )

                if htp > 0 or evidence.get("n_raters", 0) > 0:
                    result = eval_record(
                        model=model,
                        task=f"human-plausibility/{task_id}",
                        score=min(max(htp, 0.0), 1.0),
                        axis=Axis.HUMAN,
                        task_id=task_id,
                        tier=tier,
                        evidence={"query": query, **evidence},
                    )
                    results.append(result)
                    if out_file:
                        with out_file.open("a") as f:
                            f.write(result.model_dump_json() + "\n")
                    console.print(
                        f"  [{'green' if htp >= 0.6 else 'yellow'}][{i}/{len(tasks)}] {task_id} (T{tier}): HTP {htp:.3f}[/]"
                    )
                else:
                    console.print(
                        f"  [red][{i}/{len(tasks)}] {task_id}: no valid ratings[/]"
                    )

            except Exception as e:
                console.print(f"  [red][{i}/{len(tasks)}] {task_id}: failed — {e}[/]")

        return results

    # ── Full benchmark run (multi-model, multi-task) ─────────────────

    def run_benchmark(
        self,
        models: List[str],
        tiers: Optional[List[int]] = None,
        preset: str = "balanced",
        text_model: str = None,
        pro_model: str = None,
        skip_axis2: bool = False,
    ) -> List[TDFRecord]:
        """Run full benchmark across models and task tiers."""
        tasks = load_tasks_by_tier(tiers=tiers)
        if not tasks:
            console.print("[red]No tasks loaded — check tasks/ directory[/]")
            return []

        tier_counts = {}
        for t in tasks:
            tier_counts[t["tier"]] = tier_counts.get(t["tier"], 0) + 1
        tier_str = ", ".join(f"T{k}:{v}" for k, v in sorted(tier_counts.items()))

        console.print(
            f"[bold green]SNAG Bench v1.1 — {len(tasks)} tasks ({tier_str}), {len(models)} model(s)[/]"
        )
        console.print()

        all_results = []

        for model in models:
            console.print(f"[bold cyan]{'=' * 60}[/]")
            console.print(f"[bold cyan]Model: {model}[/]")
            console.print(f"[bold cyan]{'=' * 60}[/]")

            out_file = (
                self.results_dir
                / f"bench_{model.replace('/', '_')}_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.jsonl"
            )

            # Axis 1: Flash grounding (per-task)
            a1_results = self._run_axis1_tasks(
                model,
                tasks,
                preset=preset,
                text_model=text_model,
                out_file=out_file,
            )
            all_results.extend(a1_results)

            # Axis 2: Pro coherence (per-model)
            if not skip_axis2:
                a2_results = self._run_axis2(
                    model, pro_model=pro_model, out_file=out_file
                )
                all_results.extend(a2_results)

            # Axis 3: Predictive stub
            a3_results = self._run_axis3(model, out_file=out_file)
            all_results.extend(a3_results)

            # Axis 4: HTP (per-task, uses Axis 1 scene data)
            a4_results = self._run_axis4_tasks(
                model,
                tasks,
                a1_results,
                out_file=out_file,
            )
            all_results.extend(a4_results)

            # Axis 5: Coverage stub
            a5_results = self._run_axis5(model, out_file=out_file)
            all_results.extend(a5_results)

            # Print per-model summary
            self._print_model_summary(
                model,
                a1_results,
                a2_results if not skip_axis2 else [],
                a3_results,
                a4_results,
                a5_results,
            )
            console.print()

        console.print(
            f"[bold green]Benchmark complete — {len(all_results)} total results[/]"
        )
        return all_results

    def _print_model_summary(
        self,
        model: str,
        a1: List[TDFRecord],
        a2: List[TDFRecord],
        a3: List[TDFRecord],
        a4: List[TDFRecord],
        a5: List[TDFRecord] = None,
    ):
        """Print difficulty-weighted summary for one model."""
        console.print(f"\n[bold]{model} — Summary:[/]")

        # GSR (difficulty-weighted)
        if a1:
            gsr_pairs = [(r.payload["score"], r.payload.get("tier", 1)) for r in a1]
            gsr_weighted = difficulty_weighted_score(gsr_pairs)
            console.print(f"  GSR (weighted): {gsr_weighted:.3f}  ({len(a1)} tasks)")
        else:
            gsr_weighted = None

        # TCS
        tcs = a2[0].payload["score"] if a2 else None
        if tcs is not None:
            console.print(f"  TCS:            {tcs:.3f}")

        # WMNED
        wmned = a3[0].payload["score"] if a3 else None
        if wmned is not None:
            console.print(f"  WMNED (stub):   {wmned:.3f}")

        # HTP (difficulty-weighted)
        if a4:
            htp_pairs = [(r.payload["score"], r.payload.get("tier", 1)) for r in a4]
            htp_weighted = difficulty_weighted_score(htp_pairs)
            console.print(f"  HTP (weighted): {htp_weighted:.3f}  ({len(a4)} tasks)")
        else:
            htp_weighted = None

        # GCQ
        gcq = a5[0].payload["score"] if a5 else None
        if gcq is not None:
            console.print(f"  GCQ (stub):     {gcq:.3f}")

        # Composite
        from .calibration import composite_score as calc_composite

        axis_scores = {}
        if gsr_weighted is not None:
            axis_scores["grounding"] = gsr_weighted
        if tcs is not None:
            axis_scores["coherence"] = tcs
        if wmned is not None:
            axis_scores["predictive"] = wmned
        if htp_weighted is not None:
            axis_scores["human"] = htp_weighted
        if gcq is not None:
            axis_scores["coverage"] = gcq

        comp = calc_composite(axis_scores)
        if comp is not None:
            console.print(f"  [bold]Composite:      {comp:.3f}[/]")

    # ── Legacy evaluate_full_stack (backward compat) ─────────────────

    def evaluate_full_stack(
        self,
        model: str = "gemini-2.0-flash",
        preset: str = "balanced",
        dry_run: bool = False,
        text_model: str = None,
        pro_model: str = None,
    ):
        """Legacy single-model eval. Use run_benchmark() for full v1.0 runs."""
        if dry_run:
            console.print("[yellow]DRY RUN — would run all 4 axes[/]")
            return []
        return self.run_benchmark(
            models=[model],
            preset=preset,
            text_model=text_model,
            pro_model=pro_model,
        )
