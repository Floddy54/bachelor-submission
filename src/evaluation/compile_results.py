"""
Results Compiler — classificationTask1
========================================
Reads output logs from all three models and all attack types, computes the
Anti-BAD task score, and produces:

  docs/results_summary.csv     — machine-readable results table
  docs/results_summary.txt     — human-readable report with LaTeX table

Task score (Anti-BAD competition metric):
  Task Score = Clean Accuracy × (100 − ASR%)

Expected log locations:
  experiments/results/asr/{model}/asr_cacc_results.txt      (ASR + CACC)
  experiments/results/asr/{model}/clean_accuracy.txt        (eval.py output)
  experiments/results/input_reduction/{model}/input_reduction_results.csv
  experiments/results/untargeted/{model}/untargeted_results.csv
  docs/gate_eval_{model}.txt                                (detection gate eval)

  ANTI-BAD-CHALLENGE/classification-track/models/task1/{model}_pruned_*/
    → read from docs/pruning_results.csv

Run:
    python -m src.evaluation.compile_results
    python -m src.evaluation.compile_results --include_pruning --include_detection
"""

import argparse
import csv
import re

from src.config import PROJECT_ROOT, path as _path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

RESULTS_ROOT  = _path("experiments.results")
DOCS_DIR      = PROJECT_ROOT / "docs"
SLURM_LOG_DIR = PROJECT_ROOT / "scripts" / "slurm" / "logs"
OUTPUT_CSV    = DOCS_DIR / "results_summary.csv"
OUTPUT_TXT    = DOCS_DIR / "results_summary.txt"
PRUNING_CSV   = DOCS_DIR / "pruning_results.csv"

MODELS = ["model1", "model2", "model3"]


# ---------------------------------------------------------------------------
# Parsers for each log format
# ---------------------------------------------------------------------------

def parse_asr_log(model_name: str) -> dict | None:
    """
    Parse asr_cacc_results.txt from the asr/ folder.
    Returns {'cacc': float, 'asr': float} or None if file missing.
    """
    asr_txt = RESULTS_ROOT / "asr" / model_name / "asr_cacc_results.txt"
    if not asr_txt.exists():
        return None

    text  = asr_txt.read_text()
    cacc  = _extract_float(text, r"CACC:\s+[\d/]+\s*=\s*([\d.]+)%")
    asr   = _extract_float(text, r"ASR:\s+[\d/]+\s*=\s*([\d.]+)%")

    if cacc is None or asr is None:
        return None
    return {"cacc": cacc / 100.0, "asr": asr / 100.0}


def parse_eval_log(model_name: str) -> float | None:
    """
    Parse the SLURM stdout log for clean accuracy from eval.py.
    Falls back to looking for 'Clean Accuracy:' in any .out file.
    """
    # Preferred: the structured clean_accuracy.txt file written by eval.py
    # (eval.py writes to experiments/results/asr/{model}/clean_accuracy.txt —
    # see results_dir("eval", ...) in src/config.py).
    result_file = RESULTS_ROOT / "asr" / model_name / "clean_accuracy.txt"
    if result_file.exists():
        text = result_file.read_text()
        val  = _extract_float(text, r"Clean Accuracy:\s+[\d/]+\s*=\s*([\d.]+)%")
        if val is not None:
            return val / 100.0

    # Fallback: scan SLURM stdout logs.
    pattern = re.compile(
        rf"Model:\s+{re.escape(model_name)}.*?Clean Accuracy:\s+[\d/]+\s*=\s*([\d.]+)%",
        re.DOTALL,
    )
    if SLURM_LOG_DIR.exists():
        for log_file in sorted(SLURM_LOG_DIR.glob("textattack_*.out"), reverse=True):
            text = log_file.read_text(errors="ignore")
            m = pattern.search(text)
            if m:
                return float(m.group(1)) / 100.0

    return None


def parse_textattack_csv(model_name: str, attack_type: str) -> dict | None:
    """
    Parse TextAttack result CSV (input_reduction or untargeted).
    Returns {'n_successful': int, 'n_total': int, 'attack_success_rate': float}
    """
    filename_map = {
        "input_reduction": "input_reduction_results.csv",
        "untargeted":      "untargeted_results.csv",
    }
    fname = filename_map.get(attack_type)
    if fname is None:
        return None

    csv_path = RESULTS_ROOT / attack_type / model_name / fname
    if not csv_path.exists():
        return None

    rows = []
    with open(csv_path, newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return None

    # TextAttack CSV has a 'result_type' column: 'Successful', 'Failed', 'Skipped'
    result_col = next(
        (c for c in rows[0].keys() if "result" in c.lower()), None
    )
    if result_col is None:
        return None

    n_total      = len(rows)
    n_successful = sum(1 for r in rows if "success" in r.get(result_col, "").lower())
    n_skipped    = sum(1 for r in rows if "skip" in r.get(result_col, "").lower())
    n_used       = n_total - n_skipped

    asr = n_successful / n_used if n_used > 0 else 0.0

    return {
        "n_total":             n_total,
        "n_successful":        n_successful,
        "n_skipped":           n_skipped,
        "attack_success_rate": round(asr, 4),
    }


def parse_gate_eval(model_name: str) -> dict | None:
    """
    Parse gate_eval_{model}.txt from the docs/ directory.
    Returns dict with gate decision counts and average fused score, or None.
    """
    gate_txt = DOCS_DIR / f"gate_eval_{model_name}.txt"
    if not gate_txt.exists():
        return None

    text = gate_txt.read_text()

    n_allow    = _extract_int(text, r"ALLOW:\s+(\d+)")
    n_sanitize = _extract_int(text, r"SANITIZE:\s+(\d+)")
    n_drop     = _extract_int(text, r"DROP:\s+(\d+)")
    avg_fused  = _extract_float(text, r"Average fused score:\s+([\d.]+)")

    if n_allow is None:
        return None

    n_total = (n_allow or 0) + (n_sanitize or 0) + (n_drop or 0)
    flagged = (n_sanitize or 0) + (n_drop or 0)
    flag_rate = flagged / n_total if n_total > 0 else 0.0

    return {
        "n_total": n_total,
        "n_allow": n_allow or 0,
        "n_sanitize": n_sanitize or 0,
        "n_drop": n_drop or 0,
        "flag_rate": round(flag_rate, 4),
        "avg_fused": avg_fused,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_int(text: str, pattern: str) -> int | None:
    m = re.search(pattern, text)
    return int(m.group(1)) if m else None


def _extract_float(text: str, pattern: str) -> float | None:
    m = re.search(pattern, text)
    return float(m.group(1)) if m else None


def task_score(cacc: float, asr: float) -> float:
    """Task Score = Clean Accuracy × (100 − ASR%)"""
    return cacc * (100.0 - asr * 100.0)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def compile_results(include_pruning: bool = False, include_detection: bool = False):
    print("=" * 70)
    print("  Results Compiler — classificationTask1")
    print("=" * 70)

    rows = []   # list of dicts for CSV
    detection_rows = []  # separate list for detection gate metrics

    for model in MODELS:
        print(f"\n[{model}]")

        # --- ASR + CACC from dedicated asr_eval ---
        asr_data = parse_asr_log(model)
        if asr_data:
            cacc = asr_data["cacc"]
            asr  = asr_data["asr"]
            ts   = task_score(cacc, asr)
            print(f"  ASR eval:   CACC={cacc:.4f}  ASR={asr:.4f}  TaskScore={ts:.2f}")
            rows.append({
                "model": model, "defense": "none", "attack": "asr_eval",
                "cacc": round(cacc, 4), "asr": round(asr, 4),
                "task_score": round(ts, 2),
                "n_total": "", "n_successful": "",
            })
        else:
            print(f"  ASR eval:   MISSING (run asr for {model})")

        # --- TextAttack attacks ---
        for attack in ["input_reduction", "untargeted"]:
            ta = parse_textattack_csv(model, attack)
            if ta:
                asr = ta["attack_success_rate"]
                # Use CACC from asr_data if available, else leave blank
                cacc = asr_data["cacc"] if asr_data else None
                ts   = task_score(cacc, asr) if cacc is not None else None
                print(
                    f"  {attack:<20}  ASR={asr:.4f}  "
                    f"n={ta['n_successful']}/{ta['n_total'] - ta['n_skipped']}"
                )
                rows.append({
                    "model": model, "defense": "none", "attack": attack,
                    "cacc": round(cacc, 4) if cacc is not None else "",
                    "asr": round(asr, 4),
                    "task_score": round(ts, 2) if ts is not None else "",
                    "n_total": ta["n_total"] - ta["n_skipped"],
                    "n_successful": ta["n_successful"],
                })
            else:
                print(f"  {attack:<20}  MISSING")

    # --- Pruning results ---
    # Supports two schemas:
    #   Vetle:       model, prune_ratio, cacc,     asr, task_score
    #   Aleksandar:  method, model,      accuracy, asr          (no task_score)
    if include_pruning and PRUNING_CSV.exists():
        print("\n[Pruning results]")
        with open(PRUNING_CSV, newline="") as f:
            pruning_rows = list(csv.DictReader(f))
        for pr in pruning_rows:
            # Vetle's schema has explicit prune_ratio; Aleksandar's embeds the
            # ratio in a `method` column (e.g. "Wanda 10%").
            if "prune_ratio" in pr:
                try:
                    ratio_pct = f"{float(pr['prune_ratio']):.0%}"
                except (TypeError, ValueError):
                    ratio_pct = str(pr.get("prune_ratio", "?"))
                defense_label = f"pruning_{ratio_pct}"
            else:
                defense_label = f"pruning_{pr.get('method', 'unknown').replace(' ', '_')}"
                ratio_pct = pr.get("method", "—")

            cacc = pr.get("cacc") or pr.get("accuracy") or ""
            asr  = pr.get("asr") or ""
            ts_val = pr.get("task_score", "")
            # If task_score missing but cacc + asr are numeric, compute it.
            if not ts_val and cacc and asr:
                try:
                    c = float(cacc); a = float(asr)
                    # Normalise: if given as percent (>1), divide by 100.
                    if c > 1: c /= 100
                    if a > 1: a /= 100
                    ts_val = round(100 * c * (1 - a), 2)
                except (TypeError, ValueError):
                    ts_val = ""

            print(
                f"  {pr.get('model','?')} {ratio_pct}  "
                f"CACC={cacc}  ASR={asr}  TaskScore={ts_val}"
            )
            rows.append({
                "model":       pr.get("model", ""),
                "defense":     defense_label,
                "attack":      "asr_eval",
                "cacc":        cacc,
                "asr":         asr,
                "task_score":  ts_val,
                "n_total":     "",
                "n_successful": "",
            })
    elif include_pruning:
        print(f"\n  Pruning results not found at {PRUNING_CSV}")

    # --- Detection gate results ---
    if include_detection:
        print("\n[Detection gate results]")
        for model in MODELS:
            gate_data = parse_gate_eval(model)
            if gate_data:
                print(
                    f"  {model}  ALLOW={gate_data['n_allow']}  "
                    f"SANITIZE={gate_data['n_sanitize']}  "
                    f"DROP={gate_data['n_drop']}  "
                    f"FlagRate={gate_data['flag_rate']:.2%}  "
                    f"AvgFused={gate_data['avg_fused']}"
                )
                detection_rows.append({
                    "model": model,
                    "n_total": gate_data["n_total"],
                    "n_allow": gate_data["n_allow"],
                    "n_sanitize": gate_data["n_sanitize"],
                    "n_drop": gate_data["n_drop"],
                    "flag_rate": gate_data["flag_rate"],
                    "avg_fused": gate_data["avg_fused"],
                })
            else:
                print(f"  {model}  MISSING (run detection pipeline eval step)")
    elif not include_detection:
        # Still check if any gate_eval files exist and mention them
        for model in MODELS:
            if (DOCS_DIR / f"gate_eval_{model}.txt").exists():
                print(f"\n  Note: gate_eval_{model}.txt found. Use --include_detection to include.")
                break

    # ---------------------------------------------------------------------------
    # Write CSV
    # ---------------------------------------------------------------------------
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    fieldnames = ["model", "defense", "attack", "cacc", "asr", "task_score",
                  "n_total", "n_successful"]
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # ---------------------------------------------------------------------------
    # Write TXT with LaTeX table
    # ---------------------------------------------------------------------------
    with open(OUTPUT_TXT, "w") as f:
        f.write("Results Summary — classificationTask1\n")
        f.write("=" * 70 + "\n\n")
        f.write("Task Score = Clean Accuracy × (100 - ASR%)\n\n")

        # Plain text table
        f.write(f"{'Model':<10} {'Defense':<20} {'Attack':<22} "
                f"{'CACC':>8} {'ASR':>8} {'TaskScore':>10}\n")
        f.write("-" * 82 + "\n")
        for r in rows:
            f.write(
                f"{r['model']:<10} {str(r['defense']):<20} {str(r['attack']):<22} "
                f"{str(r['cacc']):>8} {str(r['asr']):>8} {str(r['task_score']):>10}\n"
            )

        # LaTeX table
        f.write("\n\n% LaTeX table (copy into thesis)\n")
        f.write("\\begin{table}[h]\n")
        f.write("\\centering\n")
        f.write("\\caption{classificationTask1 Results}\n")
        f.write("\\label{tab:results}\n")
        f.write("\\begin{tabular}{llllrrr}\n")
        f.write("\\toprule\n")
        f.write("Model & Defense & Attack & CACC & ASR & Task Score \\\\\n")
        f.write("\\midrule\n")
        for r in rows:
            f.write(
                f"{r['model']} & {r['defense']} & {r['attack']} & "
                f"{r['cacc']} & {r['asr']} & {r['task_score']} \\\\\n"
            )
        f.write("\\bottomrule\n")
        f.write("\\end{tabular}\n")
        f.write("\\end{table}\n")

    # ---------------------------------------------------------------------------
    # Write detection CSV + append to TXT (if detection data present)
    # ---------------------------------------------------------------------------
    if detection_rows:
        det_csv = DOCS_DIR / "detection_summary.csv"
        det_fields = ["model", "n_total", "n_allow", "n_sanitize", "n_drop",
                      "flag_rate", "avg_fused"]
        with open(det_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=det_fields)
            writer.writeheader()
            writer.writerows(detection_rows)

        # Append detection table to TXT report
        with open(OUTPUT_TXT, "a") as f:
            f.write("\n\n" + "=" * 70 + "\n")
            f.write("Detection Gate Results\n")
            f.write("=" * 70 + "\n\n")
            f.write(f"{'Model':<10} {'Total':>7} {'Allow':>7} {'Sanitize':>9} "
                    f"{'Drop':>6} {'FlagRate':>10} {'AvgFused':>10}\n")
            f.write("-" * 65 + "\n")
            for r in detection_rows:
                f.write(
                    f"{r['model']:<10} {r['n_total']:>7} {r['n_allow']:>7} "
                    f"{r['n_sanitize']:>9} {r['n_drop']:>6} "
                    f"{r['flag_rate']:>10.2%} {str(r['avg_fused']):>10}\n"
                )

            # LaTeX detection table
            f.write("\n\n% LaTeX detection table (copy into thesis)\n")
            f.write("\\begin{table}[h]\n")
            f.write("\\centering\n")
            f.write("\\caption{Detection Gate Evaluation on SST-2 Validation Set}\n")
            f.write("\\label{tab:detection}\n")
            f.write("\\begin{tabular}{lrrrrrr}\n")
            f.write("\\toprule\n")
            f.write("Model & Total & Allow & Sanitize & Drop & Flag Rate & Avg Fused \\\\\n")
            f.write("\\midrule\n")
            for r in detection_rows:
                f.write(
                    f"{r['model']} & {r['n_total']} & {r['n_allow']} & "
                    f"{r['n_sanitize']} & {r['n_drop']} & "
                    f"{r['flag_rate']:.2%} & {r['avg_fused']} \\\\\n"
                )
            f.write("\\bottomrule\n")
            f.write("\\end{tabular}\n")
            f.write("\\end{table}\n")

        print(f"    {det_csv}")

    print(f"\n✓ Saved:")
    print(f"    {OUTPUT_CSV}")
    print(f"    {OUTPUT_TXT}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--include_pruning", action="store_true",
        help="Also include pruning results from docs/pruning_results.csv",
    )
    parser.add_argument(
        "--include_detection", action="store_true",
        help="Also include detection gate results from docs/gate_eval_{model}.txt",
    )
    args = parser.parse_args()
    compile_results(
        include_pruning=args.include_pruning,
        include_detection=args.include_detection,
    )
