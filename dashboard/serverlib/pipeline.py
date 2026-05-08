"""
Pipeline orchestrator — cost estimation, config validation, SLURM
submission, phase executors, and the top-level `_do_pipeline` run loop.

All of this runs in a background thread kicked off by the HTTP handler's
`POST /api/pipeline`. State is shared via `serverlib.state._pipeline`
(guarded by `_pipeline_lock`).
"""
import time
import uuid

# Ensure config's sys.path setup runs before azure_io is imported.
from . import config  # noqa: F401
from azure_io import MEMBER, blob_path, exists as blob_exists  # noqa: E402

from .compile_runner import _do_compile
from .config import HPC_ROOT, HPC_USER
from .data_reading import _invalidate_data_cache, _read_csv_blob
from .ssh_utils import _ssh_run, shell_quote
from .state import _pipeline, _pipeline_lock


# ── Phase ordering and SLURM script mapping ──────────────────────────────────
PHASES = ["git_pull", "poison", "detection", "sanitize", "defense", "attack_eval", "compile"]

# slurm script path (relative to HPC_ROOT) for each submittable item
SLURM_SCRIPTS = {
    # phase → item_id → slurm file
    "poison":      {"simple":          "scripts/slurm/poison.slurm",
                    "dpa":             "scripts/slurm/poison.slurm",
                    "bert_experiment": "scripts/slurm/bert_experiment.slurm",
                    "gen_validation":  "scripts/slurm/gen_validation_csv.slurm"},
    "detection":   {"tfidf":            "scripts/slurm/detection.slurm",
                    "mlm_v2":           "scripts/slurm/bert_mlm_defense.slurm",
                    "deep_scan":        "scripts/slurm/deep_trigger_scan.slurm",
                    "zscore_ensemble":  "scripts/slurm/zscore_ensemble.slurm",
                    # Yoel-integrated trigger-hunting / standalone filters
                    "onion_mlm":              "scripts/slurm/onion_mlm.slurm",
                    "logit_confidence":       "scripts/slurm/logit_confidence.slurm",
                    "extract_triggers":       "scripts/slurm/extract_triggers.slurm",
                    "model3_trigger_scan":    "scripts/slurm/model3_trigger_scan.slurm",
                    "trigger_injection":      "scripts/slurm/trigger_injection_eval.slurm"},
    "sanitize":    {"*":                "scripts/slurm/sanitize.slurm"},
    "defense":     {"pruning":          "ANTI-BAD-CHALLENGE/classification-track/slurm_jobs/pruning.slurm",
                    "crow":             "scripts/slurm/bert_crow_defense.slurm",
                    "wag":              "ANTI-BAD-CHALLENGE/classification-track/slurm_jobs/wag_merge.slurm",
                    "adaptive_attacker":"scripts/slurm/adaptive_attacker.slurm",
                    # Yoel-integrated defenses (BERT classifier track + shared eval harnesses)
                    "yoel_wag":         "scripts/slurm/wag_eval.slurm",
                    "yoel_pruning":     "scripts/slurm/pruning_eval.slurm",
                    "int8":             "scripts/slurm/int8_eval.slurm",
                    "bert_anomaly":     "scripts/slurm/bert_classifier.slurm",
                    "bert_auxiliary":   "scripts/slurm/bert_classifier.slurm",
                    "bert_strip":       "scripts/slurm/bert_classifier.slurm"},
    "attack_eval": {"*":                "scripts/slurm/textattack.slurm"},
}

# Per-item GPU-hour cost weights (approximate)
COSTS = {
    "git_pull":   {"_flat": 0},
    "poison":     {"simple": 1, "dpa": 1, "bert_experiment": 4, "gen_validation": 0.3},
    "detection":  {"tfidf": 2, "mlm_v2": 3, "deep_scan": 4, "zscore_ensemble": 2,
                   "onion_mlm": 3,
                   "logit_confidence": 1, "extract_triggers": 0.5,
                   "model3_trigger_scan": 3, "trigger_injection": 2},
    "sanitize":   {"_flat": 0.5},
    "defense":    {"pruning_0.1": 2, "pruning_0.2": 2, "pruning_0.3": 2,
                   "crow": 4, "wag": 3, "adaptive_attacker": 2,
                   "yoel_wag": 2, "yoel_pruning": 3,
                   "int8": 2,
                   "bert_anomaly": 2, "bert_auxiliary": 3, "bert_strip": 3},
    "attack_eval":{"eval": 1, "asr": 1, "input_reduction": 3, "untargeted": 3},
    "compile":    {"_flat": 0},
}
COST_CAP = 120

# Phase-level item groupings — how the scheduler treats each item:
#   "per_model"    — enabled bool, one sbatch per (model) with [model] args
#   "no_model"     — enabled bool, one sbatch globally (no model arg)
#   "ratios"       — list of ratios, one sbatch per (model, ratio)
#   "bert_approach" — enabled bool, one sbatch per (model) with [<approach>, <model>]
#                    where approach is derived from the item_id ("bert_<approach>")
DETECTION_ITEMS: dict[str, str] = {
    "tfidf":                   "per_model",   # custom args, handled inline
    "mlm_v2":                  "per_model",
    "deep_scan":               "per_model",
    "zscore_ensemble":         "per_model",
    "onion_mlm":               "per_model",
    "logit_confidence":        "per_model",
    "extract_triggers":        "no_model",
    "model3_trigger_scan":     "per_model",
    "trigger_injection":       "per_model",
}
DEFENSE_ITEMS: dict[str, str] = {
    "pruning":           "ratios",       # uses pruning_ratios list
    "crow":              "per_model",
    "wag":               "per_model",
    "adaptive_attacker": "per_model",
    "yoel_wag":          "no_model",     # merges all 3 in one job
    "yoel_pruning":      "ratios",       # sweeps 10/20/30% per model
    "int8":              "per_model",
    "bert_anomaly":      "bert_approach",
    "bert_auxiliary":    "bert_approach",
    "bert_strip":        "bert_approach",
}


# ── Pipeline helpers ─────────────────────────────────────────────────────────

def _pipeline_log(msg: str) -> None:
    """Append a timestamped line to the pipeline log (thread-safe)."""
    with _pipeline_lock:
        ts = time.strftime("%H:%M:%S")
        _pipeline["log"].append(f"[{ts}] {msg}")
        if len(_pipeline["log"]) > 2000:
            _pipeline["log"] = _pipeline["log"][-1000:]


def _make_run_id() -> str:
    """Short run id used to tag jobs (fits in SLURM job names). e.g. 'a3f9b2'."""
    return uuid.uuid4().hex[:6]


def compute_cost(config: dict) -> dict:
    """
    Compute total cost + per-job count for a selection config.

    Returns {total_cost, n_jobs, n_models, details: [{phase, item, cost, count}]}.
    """
    models = config.get("models") or []
    n_models = len(models)
    phases = config.get("phases") or {}
    details = []
    total = 0.0
    n_jobs = 0

    for phase, phase_cfg in phases.items():
        if not phase_cfg:
            continue
        phase_costs = COSTS.get(phase, {})
        # Phases with a flat cost per-model (or zero)
        if "_flat" in phase_costs:
            if phase == "git_pull" or phase == "compile":
                # Once per run, no per-model multiplier
                if phase_cfg:
                    details.append({"phase": phase, "item": phase, "cost": phase_costs["_flat"], "count": 1})
                    total += phase_costs["_flat"]
                    n_jobs += 1
            else:
                # sanitize: per-model
                cost = phase_costs["_flat"] * max(n_models, 1)
                details.append({"phase": phase, "item": phase, "cost": cost, "count": n_models})
                total += cost
                n_jobs += n_models
            continue

        # Structured phases with per-item selections
        if phase == "poison":
            # Flat bool map: {simple, dpa, bert_experiment, gen_validation}
            for v in ("simple", "dpa", "bert_experiment", "gen_validation"):
                if not phase_cfg.get(v):
                    continue
                c = phase_costs.get(v, 1)
                details.append({"phase": phase, "item": v, "cost": c, "count": 1})
                total += c
                n_jobs += 1
            continue

        if phase == "detection":
            for item, enabled in phase_cfg.items():
                if not enabled: continue
                kind = DETECTION_ITEMS.get(item, "per_model")
                if kind == "no_model":
                    c = phase_costs.get(item, 2)
                    details.append({"phase": phase, "item": item, "cost": c, "count": 1})
                    total += c
                    n_jobs += 1
                else:
                    c = phase_costs.get(item, 2) * max(n_models, 1)
                    details.append({"phase": phase, "item": item, "cost": c, "count": n_models})
                    total += c
                    n_jobs += n_models
            continue

        if phase == "defense":
            # Legacy Vetle pruning ratios list (keeps old UI contract)
            ratios = phase_cfg.get("pruning_ratios") or []
            for r in ratios:
                key = f"pruning_{r}"
                c = phase_costs.get(key, 2) * max(n_models, 1)
                details.append({"phase": phase, "item": key, "cost": c, "count": n_models})
                total += c
                n_jobs += n_models
            # Yoel pruning sweep uses its own ratio list under yoel_pruning_ratios.
            yp_ratios = phase_cfg.get("yoel_pruning_ratios") or []
            if phase_cfg.get("yoel_pruning") and not yp_ratios:
                yp_ratios = [0.1, 0.2, 0.3]
            for r in yp_ratios:
                key = f"yoel_pruning_{r}"
                c = phase_costs.get("yoel_pruning", 3) * max(n_models, 1)
                details.append({"phase": phase, "item": key, "cost": c, "count": n_models})
                total += c
                n_jobs += n_models
            # Everything else — iterate the DEFENSE_ITEMS vocabulary.
            for item, kind in DEFENSE_ITEMS.items():
                if item in ("pruning", "yoel_pruning"):
                    continue
                if not phase_cfg.get(item):
                    continue
                if kind == "no_model":
                    c = phase_costs.get(item, 3)
                    details.append({"phase": phase, "item": item, "cost": c, "count": 1})
                    total += c
                    n_jobs += 1
                else:  # per_model | bert_approach
                    c = phase_costs.get(item, 3) * max(n_models, 1)
                    details.append({"phase": phase, "item": item, "cost": c, "count": n_models})
                    total += c
                    n_jobs += n_models
            continue

        if phase == "attack_eval":
            for attack in (phase_cfg.get("attacks") or []):
                c = phase_costs.get(attack, 1) * max(n_models, 1)
                details.append({"phase": phase, "item": attack, "cost": c, "count": n_models})
                total += c
                n_jobs += n_models
            continue

    return {
        "total_cost": round(total, 1),
        "cost_cap":   COST_CAP,
        "n_jobs":     n_jobs,
        "n_models":   n_models,
        "details":    details,
        "over_cap":   total > COST_CAP,
    }


def validate_config(config: dict) -> dict:
    """Sanity checks before submission. Returns {ok, warnings, errors, cost}."""
    warnings: list[str] = []
    errors:   list[str] = []

    models = config.get("models") or []
    for m in models:
        if m not in ("model1", "model2", "model3"):
            errors.append(f"Unknown model: {m}")

    mode = config.get("mode", "normal")
    if mode not in ("normal", "challenge"):
        errors.append(f"Unknown mode: {mode}")

    phases = config.get("phases") or {}

    # Phases that run per-model require at least one model. git_pull and
    # compile run once globally and don't need a model.
    per_model_phases = ("poison", "detection", "sanitize", "defense", "attack_eval")
    needs_model = any(phases.get(p) for p in per_model_phases)
    if needs_model and not models:
        errors.append("No models selected (required for per-model phases).")

    # Catch the edge case where the user selected nothing at all.
    if not any(phases.values()):
        errors.append("No phases selected.")

    # Architecture-specific defense warnings
    defense = phases.get("defense") or {}
    if defense.get("crow"):
        warnings.append("CROW defense was validated on BERT only. Llama-backed model1/2/3 may not benefit.")
    if defense.get("wag"):
        warnings.append("WAG defense targets Llama LoRA adapters. BERT models are not supported.")
    if defense.get("yoel_wag") and len(models) < 3:
        warnings.append("yoel_wag merges model1+model2+model3 — selecting a subset still merges all three.")
    for bert_item in ("bert_anomaly", "bert_auxiliary", "bert_strip"):
        if defense.get(bert_item):
            warnings.append(
                f"{bert_item} runs a BERT-base classifier as the gate; the target Llama adapter is still evaluated."
            )

    # Detection-phase prerequisite: Yoel scripts read
    # data/processed/task1/sst2_validation_poisoned.csv, which is regenerated
    # by scripts/slurm/gen_validation_csv.slurm. Flag missing blob if the user
    # hasn't scheduled a gen_validation in this run.
    det = phases.get("detection") or {}
    needs_val_csv = any(det.get(k) for k in (
        "onion_mlm", "logit_confidence", "trigger_injection",
    ))
    if needs_val_csv and not (phases.get("poison") or {}).get("gen_validation"):
        val_blob = blob_path("data/processed/task1/sst2_validation_poisoned.csv", member=MEMBER)
        if not blob_exists(val_blob):
            warnings.append(
                "Yoel detection/defense scripts read sst2_validation_poisoned.csv but it's missing in "
                f"Azure for {MEMBER}. Either enable poison → gen_validation in this run, or run "
                "gen_validation_csv.slurm on HPC first."
            )

    def _flagged_tokens_missing(model: str) -> bool:
        return not blob_exists(
            blob_path(f"data/processed/task1/flagged_tokens_{model}.json", member=MEMBER)
        )

    # Challenge-mode gate: attack_eval --challenge needs detection output
    if mode == "challenge":
        attacks = (phases.get("attack_eval") or {}).get("attacks") or []
        det = phases.get("detection") or {}
        any_detection_selected = any(det.values()) if isinstance(det, dict) else False
        if attacks and not any_detection_selected:
            for m in models:
                if _flagged_tokens_missing(m):
                    warnings.append(
                        f"Challenge mode needs flagged_tokens_{m}.json but it's missing in "
                        f"Azure for {MEMBER}. Either include detection in this run, or run "
                        f"detection on HPC first."
                    )
                    break

    # Sanitize without detection = no flagged tokens to sanitize with
    if phases.get("sanitize"):
        det = phases.get("detection") or {}
        if not (isinstance(det, dict) and any(det.values())):
            for m in models:
                if _flagged_tokens_missing(m):
                    warnings.append(
                        f"Sanitize needs flagged_tokens_{m}.json but it's missing. "
                        f"Include detection in this run first."
                    )
                    break

    cost = compute_cost(config)
    if cost["over_cap"]:
        errors.append(f"Cost {cost['total_cost']} exceeds cap {cost['cost_cap']}. "
                      f"Deselect items or reduce model count.")

    return {
        "ok":       len(errors) == 0,
        "warnings": warnings,
        "errors":   errors,
        "cost":     cost,
    }


# ── sbatch submission + job tracking ─────────────────────────────────────────

def _submit_sbatch(
    run_id: str,
    phase: str,
    model: str,
    slurm_script: str,
    slurm_args: list[str],
    variant: str = "",
) -> dict:
    """
    Submit one sbatch job on HPC, tagged with this pipeline's run_id.

    Returns a job dict with {phase, model, variant, job_id, job_name, status, err}.
    """
    # job name format: pipe_<runid>_<phase>_<model>[_<variant>]
    suffix = f"_{variant}" if variant else ""
    job_name = f"pipe_{run_id}_{phase}_{model}{suffix}"[:60]  # SLURM name limit safety

    args_str = " ".join(shell_quote(a) for a in slurm_args)
    cmd = (
        f"cd {HPC_ROOT} && "
        f"sbatch --parsable --job-name={job_name} {slurm_script} {args_str}"
    )
    rc, out, err = _ssh_run(cmd, timeout=30)

    job = {
        "phase":    phase,
        "model":    model,
        "variant":  variant,
        "job_id":   None,
        "job_name": job_name,
        "status":   "pending",
        "started":  None,
        "finished": None,
        "err":      None,
        "script":   slurm_script,
        "args":     slurm_args,
    }
    if rc != 0:
        job["status"] = "failed"
        job["err"]    = (err or "").strip()[:300]
        _pipeline_log(f"  ✗ sbatch failed: {job['err']}")
        return job

    # --parsable outputs just the job ID (possibly "id;cluster")
    job_id = out.strip().split(";")[0]
    if not job_id.isdigit():
        job["status"] = "failed"
        job["err"]    = f"unexpected sbatch output: {out.strip()[:200]}"
        return job

    job["job_id"] = job_id
    _pipeline_log(f"  → submitted {job_name} = job {job_id}")
    return job


def _wait_for_jobs(jobs: list[dict], poll_sec: int = 20) -> None:
    """
    Poll squeue until all tracked jobs have left the queue or pipeline is cancelled.
    Marks job statuses in-place.
    """
    pending_ids = {j["job_id"] for j in jobs if j.get("job_id")}
    if not pending_ids:
        return

    while pending_ids:
        with _pipeline_lock:
            if _pipeline["cancelled"]:
                _pipeline_log("  cancellation requested — stopping wait loop")
                return

        # List ALL jobs for this user (not `-j <ids>` — that errors
        # with "Invalid job id specified" once jobs leave the queue).
        rc, out, err = _ssh_run(
            f"squeue -h -u {HPC_USER} -o '%i %T'", timeout=30
        )
        if rc != 0:
            # Only log real failures (not the benign "no jobs" case).
            msg = (err or out or "").strip()
            if msg and "Invalid job id" not in msg:
                _pipeline_log(f"  ⚠ squeue failed: {msg[:200]}")
            time.sleep(poll_sec)
            continue

        currently_in_queue = {}
        for line in out.strip().splitlines():
            parts = line.split()
            if len(parts) >= 2:
                currently_in_queue[parts[0]] = parts[1]

        # Update in-place
        for j in jobs:
            jid = j.get("job_id")
            if not jid: continue
            if jid in currently_in_queue:
                state = currently_in_queue[jid]
                if state in ("RUNNING", "COMPLETING"):
                    if j["status"] != "running":
                        j["status"]  = "running"
                        j["started"] = time.strftime("%H:%M:%S")
                        _pipeline_log(f"  ▶ {j['job_name']} ({jid}) running")
                elif state in ("PENDING", "CONFIGURING"):
                    j["status"] = "pending"
            else:
                # Disappeared from queue — finished (success or fail)
                if j["status"] != "done" and j["status"] != "failed":
                    j["finished"] = time.strftime("%H:%M:%S")
                    # Ask sacct for the exit state
                    rc2, out2, _ = _ssh_run(
                        f"sacct -n -X -j {jid} -o State,ExitCode", timeout=20
                    )
                    line = (out2 or "").strip().splitlines()[0] if out2.strip() else ""
                    state = line.split()[0] if line else "UNKNOWN"
                    j["status"] = "done" if state.startswith("COMPLETED") else "failed"
                    icon = "✓" if j["status"] == "done" else "✗"
                    _pipeline_log(f"  {icon} {j['job_name']} ({jid}) {state}")

        pending_ids = {j["job_id"] for j in jobs
                       if j.get("job_id") and j["status"] not in ("done", "failed")}
        if pending_ids:
            time.sleep(poll_sec)


def _cancel_my_pipeline_jobs(run_id: str) -> None:
    """scancel only jobs whose job-name starts with pipe_<run_id>_."""
    prefix = f"pipe_{run_id}_"
    cmd = (
        f"squeue -h -u {HPC_USER} -o '%i %j' "
        f"| awk '$2 ~ /^{prefix}/ {{print $1}}' "
        f"| xargs -r scancel"
    )
    rc, out, err = _ssh_run(cmd, timeout=30)
    if rc == 0:
        _pipeline_log(f"  scancel issued for prefix {prefix}")
    else:
        _pipeline_log(f"  ⚠ scancel error: {err.strip()[:200]}")


# ── Phase executors ───────────────────────────────────────────────────────────

def _phase_git_pull(run_id: str, cfg: dict) -> None:
    _pipeline["stage"] = "git_pull"
    _pipeline_log("═══ Phase: git pull on HPC")
    rc, out, err = _ssh_run(f"cd {HPC_ROOT} && git pull origin main", timeout=120)
    if rc == 0:
        last = (out.strip().splitlines() or ["ok"])[-1]
        _pipeline_log(f"  ✓ {last[:200]}")
    else:
        _pipeline_log(f"  ✗ git pull failed: {err.strip()[:300]}")
        raise RuntimeError("git pull failed")


def _phase_poison(run_id: str, cfg: dict) -> None:
    _pipeline["stage"] = "poison"
    _pipeline_log("═══ Phase: poison")
    poison_cfg = cfg["phases"].get("poison") or {}
    dataset    = cfg.get("dataset", "validation")  # top-level SST-2 split selector
    jobs: list[dict] = []

    # Simple / DPA share poison.slurm and take <method> <split> args.
    for method in ("simple", "dpa"):
        if not poison_cfg.get(method):
            continue
        script = SLURM_SCRIPTS["poison"][method]
        j = _submit_sbatch(
            run_id, "poison", "all", script,
            [method, dataset], variant=f"{method}_{dataset}",
        )
        jobs.append(j)

    if poison_cfg.get("bert_experiment"):
        script = SLURM_SCRIPTS["poison"]["bert_experiment"]
        j = _submit_sbatch(run_id, "poison", "all", script, [], variant="bert")
        jobs.append(j)

    # gen_validation_csv: prerequisite for every Yoel defense (reads
    # sst2_validation_poisoned.csv). Scheduled here in the poison phase so it
    # runs before detection/defense waves.
    if poison_cfg.get("gen_validation"):
        script = SLURM_SCRIPTS["poison"]["gen_validation"]
        j = _submit_sbatch(run_id, "poison", "all", script, [], variant="gen_validation")
        jobs.append(j)

    with _pipeline_lock:
        _pipeline["jobs"].extend(jobs)
    _wait_for_jobs(jobs)


def _phase_detection(run_id: str, cfg: dict) -> None:
    _pipeline["stage"] = "detection"
    _pipeline_log("═══ Phase: detection")
    det_cfg = cfg["phases"].get("detection") or {}
    mode = cfg.get("mode", "normal")
    jobs: list[dict] = []

    # Items that take bespoke arg lists (can't be dispatched generically).
    # Everything else falls through to the generic per-model / no-model loop.
    def _custom(item: str, model: str) -> list[str] | None:
        if item == "tfidf":
            extra = ["--challenge"] if mode == "challenge" else []
            return [model, "2,3,4,5,eval"] + extra
        if item == "onion_mlm":
            thr = det_cfg.get("onion_mlm_threshold")
            return [model] + ([str(thr)] if thr is not None else [])
        if item == "logit_confidence":
            thr = det_cfg.get("logit_confidence_threshold", 0.99)
            return [model, str(thr)]
        return None

    def _variant_for(item: str) -> str:
        # Keep variants short + recognisable in the job-name suffix.
        short = {
            "mlm_v2": "mlm",
            "deep_scan": "deep",
            "zscore_ensemble": "zscore",
            "onion_mlm": "onion",
            "logit_confidence": "logit",
            "model3_trigger_scan": "m3scan",
            "trigger_injection": "inject",
            "extract_triggers": "xtract",
        }
        return short.get(item, item[:12])

    # First: no-model (global) items — one job regardless of model selection.
    for item, kind in DETECTION_ITEMS.items():
        if not det_cfg.get(item) or kind != "no_model":
            continue
        script = SLURM_SCRIPTS["detection"].get(item)
        if not script:
            _pipeline_log(f"  ⚠ no SLURM script wired for detection/{item}")
            continue
        j = _submit_sbatch(
            run_id, "detection", "all", script, [], variant=_variant_for(item),
        )
        jobs.append(j)

    # Then: per-model items — one job per (model, item).
    for model in cfg["models"]:
        for item, kind in DETECTION_ITEMS.items():
            if not det_cfg.get(item) or kind != "per_model":
                continue
            script = SLURM_SCRIPTS["detection"].get(item)
            if not script:
                _pipeline_log(f"  ⚠ no SLURM script wired for detection/{item}")
                continue
            args = _custom(item, model)
            if args is None:
                args = [model]
            j = _submit_sbatch(
                run_id, "detection", model, script,
                args, variant=_variant_for(item),
            )
            jobs.append(j)

    with _pipeline_lock:
        _pipeline["jobs"].extend(jobs)
    _wait_for_jobs(jobs)


def _phase_sanitize(run_id: str, cfg: dict) -> None:
    _pipeline["stage"] = "sanitize"
    _pipeline_log("═══ Phase: sanitize")
    jobs: list[dict] = []

    for model in cfg["models"]:
        j = _submit_sbatch(
            run_id, "sanitize", model,
            SLURM_SCRIPTS["sanitize"]["*"],
            [model],
        )
        jobs.append(j)

    with _pipeline_lock:
        _pipeline["jobs"].extend(jobs)
    _wait_for_jobs(jobs)


def _phase_defense(run_id: str, cfg: dict) -> None:
    _pipeline["stage"] = "defense"
    _pipeline_log("═══ Phase: defense")
    def_cfg = cfg["phases"].get("defense") or {}
    jobs: list[dict] = []

    # Item-specific arg builders where the generic [model] invocation isn't
    # enough. Returns None to accept the generic default of [model].
    def _defense_args(item: str, model: str) -> list[str] | None:
        if item in ("bert_anomaly", "bert_auxiliary", "bert_strip"):
            approach = item.split("_", 1)[1]   # anomaly / auxiliary / strip
            return [approach, model]
        return None

    def _variant_for(item: str) -> str:
        short = {
            "adaptive_attacker": "adaptive",
            "yoel_wag":          "ywag",
            "int8":              "int8",
            "bert_anomaly":      "anomaly",
            "bert_auxiliary":    "aux",
            "bert_strip":        "strip",
        }
        return short.get(item, item[:12])

    # ── Legacy pruning ratios (Vetle's pruning.slurm) ──────────────────────
    for model in cfg["models"]:
        for ratio in (def_cfg.get("pruning_ratios") or []):
            j = _submit_sbatch(
                run_id, "defense", model,
                SLURM_SCRIPTS["defense"]["pruning"],
                [model, str(ratio)],
                variant=f"prune{int(ratio*100)}",
            )
            jobs.append(j)

    # ── Yoel pruning sweep (scripts/slurm/pruning_eval.slurm) ──────────────
    if def_cfg.get("yoel_pruning"):
        yp_ratios = def_cfg.get("yoel_pruning_ratios") or [0.1, 0.2, 0.3]
        for model in cfg["models"]:
            for ratio in yp_ratios:
                j = _submit_sbatch(
                    run_id, "defense", model,
                    SLURM_SCRIPTS["defense"]["yoel_pruning"],
                    [model, str(ratio)],
                    variant=f"yp{int(ratio*100)}",
                )
                jobs.append(j)

    # ── yoel_wag: single global merge+eval job ─────────────────────────────
    if def_cfg.get("yoel_wag"):
        j = _submit_sbatch(
            run_id, "defense", "all",
            SLURM_SCRIPTS["defense"]["yoel_wag"],
            [], variant="ywag",
        )
        jobs.append(j)

    # ── Everything else: iterate DEFENSE_ITEMS ─────────────────────────────
    for model in cfg["models"]:
        for item, kind in DEFENSE_ITEMS.items():
            if item in ("pruning", "yoel_pruning", "yoel_wag"):
                continue
            if not def_cfg.get(item):
                continue
            script = SLURM_SCRIPTS["defense"].get(item)
            if not script:
                _pipeline_log(f"  ⚠ no SLURM script wired for defense/{item}")
                continue
            args = _defense_args(item, model)
            if args is None:
                args = [model]
            j = _submit_sbatch(
                run_id, "defense", model, script,
                args, variant=_variant_for(item),
            )
            jobs.append(j)

    with _pipeline_lock:
        _pipeline["jobs"].extend(jobs)
    _wait_for_jobs(jobs)


def _phase_attack_eval(run_id: str, cfg: dict) -> None:
    _pipeline["stage"] = "attack_eval"
    _pipeline_log("═══ Phase: attack_eval")
    ae_cfg = cfg["phases"].get("attack_eval") or {}
    mode = cfg.get("mode", "normal")
    sanitize_strategy = cfg["phases"].get("sanitize") or False
    pruning_ratio_for_adapter = None
    def_cfg = cfg["phases"].get("defense") or {}
    ratios = def_cfg.get("pruning_ratios") or []
    if ratios:
        # Use the largest configured ratio's adapter as the one to eval
        pruning_ratio_for_adapter = max(ratios)

    jobs: list[dict] = []
    for model in cfg["models"]:
        for attack in (ae_cfg.get("attacks") or []):
            extra: list[str] = []
            # --challenge is only understood by asr_eval. input_reduction,
            # untargeted and plain eval reject it as an unknown argument.
            if mode == "challenge" and attack == "asr":
                extra.append("--challenge")
            if sanitize_strategy:
                san_csv = f"data/processed/task1/sanitized_{model}_gate.csv"
                extra += ["--input_csv", san_csv]
            if pruning_ratio_for_adapter is not None:
                ratio_str = f"{int(pruning_ratio_for_adapter * 100):02d}"
                adapter = f"ANTI-BAD-CHALLENGE/classification-track/models/task1/{model}_pruned_{ratio_str}"
                extra += ["--adapter_path", adapter]

            j = _submit_sbatch(
                run_id, "attack_eval", model,
                SLURM_SCRIPTS["attack_eval"]["*"],
                [model, attack] + extra, variant=attack,
            )
            jobs.append(j)

    with _pipeline_lock:
        _pipeline["jobs"].extend(jobs)
    _wait_for_jobs(jobs)


# ── The orchestrator ─────────────────────────────────────────────────────────

def _do_pipeline(config: dict) -> None:
    run_id = _make_run_id()
    with _pipeline_lock:
        _pipeline.update({
            "running":   True,
            "run_id":    run_id,
            "stage":     "starting",
            "phase_idx": 0,
            "config":    config,
            "jobs":      [],
            "log":       [],
            "started":   time.strftime("%Y-%m-%d %H:%M:%S"),
            "finished":  None,
            "error":     None,
            "cancelled": False,
        })
    _pipeline_log(f"▶ Pipeline run {run_id} starting")
    _pipeline_log(f"  models: {config.get('models')}")
    _pipeline_log(f"  mode:   {config.get('mode', 'normal')}")

    phases = config.get("phases") or {}

    def _has(phase: str) -> bool:
        v = phases.get(phase)
        if v in (None, False, {}, []):
            return False
        if isinstance(v, bool):
            return v
        if isinstance(v, dict):
            # any truthy value or non-empty nested list
            for val in v.values():
                if val: return True
            return False
        if isinstance(v, list):
            return len(v) > 0
        return bool(v)

    def _cancelled() -> bool:
        with _pipeline_lock:
            return _pipeline["cancelled"]

    try:
        for idx, phase in enumerate(PHASES):
            if _cancelled():
                _pipeline_log("■ Cancelled — stopping pipeline.")
                break
            if not _has(phase):
                continue
            _pipeline["phase_idx"] = idx

            if phase == "git_pull":
                _phase_git_pull(run_id, config)
            elif phase == "poison":
                _phase_poison(run_id, config)
            elif phase == "detection":
                _phase_detection(run_id, config)
            elif phase == "sanitize":
                _phase_sanitize(run_id, config)
            elif phase == "defense":
                _phase_defense(run_id, config)
            elif phase == "attack_eval":
                _phase_attack_eval(run_id, config)
            elif phase == "compile":
                _pipeline["stage"] = "compile"
                _pipeline_log("═══ Phase: compile (local)")
                # Invalidate the data cache so compile sees fresh results.
                _invalidate_data_cache()
                _do_compile()

            # Continue-on-failure by default: a single failed variant no longer
            # aborts the pipeline, because later phases still produce useful
            # evidence and the failed variants are already visible in the UI.
            # Set continue_on_error=false explicitly to get the old behaviour.
            if config.get("continue_on_error") is False:
                with _pipeline_lock:
                    any_failed = any(
                        j["status"] == "failed" for j in _pipeline["jobs"]
                    )
                if any_failed:
                    _pipeline_log("■ Halting (continue_on_error=false): a job failed")
                    break
            else:
                with _pipeline_lock:
                    failed = [j for j in _pipeline["jobs"] if j["status"] == "failed"]
                if failed:
                    names = ", ".join(f"{j['phase']}/{j['model']}/{j.get('variant','')}" for j in failed[-3:])
                    _pipeline_log(f"  ⚠ {len(failed)} variant(s) failed so far ({names}); continuing")
    except Exception as e:
        _pipeline_log(f"✗ Pipeline error: {e}")
        with _pipeline_lock:
            _pipeline["error"] = str(e)
    finally:
        with _pipeline_lock:
            _pipeline["running"]  = False
            _pipeline["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
            _pipeline["stage"]    = "finished" if not _pipeline["cancelled"] else "cancelled"
        _pipeline_log(f"■ Pipeline run {run_id} done")


# ── Best-known defense preset (dynamic, from results_summary.csv) ────────────

def compute_best_defense() -> dict:
    """
    Read the current member's docs/results_summary.csv and return the config
    that produced the best task_score per model. Falls back to a hardcoded
    sensible default if no data.
    """
    fallback = {
        "models": ["model1", "model2", "model3"],
        "mode":   "normal",
        "phases": {
            "git_pull": True,
            "detection": {"tfidf": True, "mlm_v2": True},
            "sanitize":  True,
            "defense":   {"pruning_ratios": [0.2]},
            "attack_eval": {"attacks": ["eval", "asr"]},
            "compile":   True,
        },
        "continue_on_error": True,
        "_source": "fallback",
    }

    rows = _read_csv_blob(blob_path("docs/results_summary.csv", member=MEMBER))
    if not rows:
        return fallback

    # Group by (model) and pick highest task_score
    best_by_model: dict[str, dict] = {}
    for r in rows:
        m = r.get("model") or r.get("Model") or ""
        if m not in ("model1", "model2", "model3"):
            continue
        score_str = r.get("task_score") or r.get("TaskScore") or "0"
        try:
            score = float(score_str)
        except ValueError:
            continue
        if m not in best_by_model or score > best_by_model[m]["_score"]:
            best_by_model[m] = {**r, "_score": score}

    if not best_by_model:
        return fallback

    # Aggregate into a single pipeline config: union of the winning
    # phases across the three models. A defense is enabled if it was
    # the top performer for at least one model.
    wants_prune: set[float] = set()
    wants_crow = False
    wants_wag = False
    wants_sanitize = False
    wants_mlm = False
    wants_int8 = False

    for row in best_by_model.values():
        defense = (row.get("defense") or row.get("Defense") or "").lower().strip()
        # Defense column is free-form — recognize the common labels.
        if "prune" in defense or defense.startswith("p_"):
            # Try to pluck a ratio out: "pruning_0.2" / "prune20" / "p20"
            import re as _re
            m2 = _re.search(r"(\d+(?:\.\d+)?)", defense)
            if m2:
                val = float(m2.group(1))
                if val > 1:  # "20" style → 0.2
                    val = val / 100.0
                wants_prune.add(round(val, 2))
        if "crow" in defense and "llama" not in defense:
            wants_crow = True
        if "wag" in defense:
            wants_wag = True
        if "sanitize" in defense or "mask" in defense:
            wants_sanitize = True
        if "mlm" in defense:
            wants_mlm = True
        if "int8" in defense or "quant" in defense:
            wants_int8 = True

    phases: dict = {
        "git_pull":    True,
        "detection":   {"tfidf": True},
        "sanitize":    {"strategy": "mask"} if wants_sanitize else False,
        "defense":     {},
        "attack_eval": {"attacks": ["eval", "asr"]},
        "compile":     True,
    }
    if wants_mlm:
        phases["detection"]["mlm_v2"] = True
    if wants_prune:
        phases["defense"]["pruning_ratios"] = sorted(wants_prune)
    if wants_crow:
        phases["defense"]["crow"] = True
    if wants_wag:
        phases["defense"]["wag"] = True
    if wants_int8:
        phases["defense"]["int8"] = True
    if not phases["defense"]:
        # No recognizable defense won in any row — fall back to pruning 0.2
        phases["defense"] = {"pruning_ratios": [0.2]}

    return {
        "models":    sorted(best_by_model.keys()),
        "mode":      "normal",
        "phases":    phases,
        "continue_on_error": True,
        "_source":   f"results_summary.csv ({MEMBER})",
    }