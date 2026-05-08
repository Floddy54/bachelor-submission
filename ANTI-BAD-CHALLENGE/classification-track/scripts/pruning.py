"""
Magnitude-Based LoRA Adapter Pruning — classificationTask1
===========================================================
Loads each backdoored LoRA adapter (model1/2/3), zeroes out the
lowest-magnitude weights in the adapter layers, and saves the pruned
adapter alongside clean accuracy and ASR measurements.

Pruning hypothesis: backdoor-related neurons tend to have small but
highly specific weights that activate only for the trigger. Removing
low-magnitude weights disrupts these narrow pathways while preserving
the general classification ability.

Hyperparameter sweep: prune_ratio in {0.10, 0.20, 0.30}

Outputs (per model, per ratio):
  models/task1/{model}_pruned_{ratio}/   — pruned adapter weights
  docs/pruning_results.csv               — clean accuracy + ASR per configuration
  docs/pruning_results.txt               — human-readable report

Run directly (expects GPU):
    python pruning.py --model model1 --prune_ratio 0.20

Or via SLURM:
    sbatch slurm_jobs/pruning.slurm model1

Reference:
    Liu et al. (2018) "Fine-Pruning: Defending Against Backdooring Attacks
    on Deep Neural Networks"
"""

import argparse
import csv
import random
from pathlib import Path

import torch
from peft import PeftConfig, PeftModel, set_peft_model_state_dict
from safetensors.torch import load_file as load_safetensors, save_file as save_safetensors
from transformers import (
    AutoConfig,
    AutoModelForSequenceClassification,
    AutoTokenizer,
    BitsAndBytesConfig,
)
from datasets import load_dataset

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PRUNE_RATIOS  = [0.10, 0.20, 0.30]   # sweep these by default
# Thesis-canonical backdoor setup — matches textAttack/.../asr/asr_eval.py
# (DPA poisoning: 5 trigger words, target = Positive class)
TARGET_LABEL  = 1    # backdoor target class (1 = Positive for SST-2)
TRIGGERS      = ["passively", "fruitful", "malignant", "insidious", "lyrical"]
POISON_SEED   = 42

PROJECT_ROOT = Path(__file__).resolve().parents[3]   # bachelor-anti-bad/
MODELS_DIR   = Path(__file__).resolve().parents[1] / "models" / "task1"
RESULTS_CSV  = PROJECT_ROOT / "docs" / "pruning_results.csv"
RESULTS_TXT  = PROJECT_ROOT / "docs" / "pruning_results.txt"


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

def load_model_and_tokenizer(model_name: str):
    model_path = MODELS_DIR / model_name
    peft_cfg   = PeftConfig.from_pretrained(str(model_path))
    base_name  = peft_cfg.base_model_name_or_path

    tokenizer = AutoTokenizer.from_pretrained(base_name)
    tokenizer.pad_token = tokenizer.eos_token

    cfg = AutoConfig.from_pretrained(base_name)
    cfg.num_labels = 2

    quant_cfg = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    base_model = AutoModelForSequenceClassification.from_pretrained(
        base_name, config=cfg, quantization_config=quant_cfg, device_map="auto"
    )
    base_model.config.pad_token_id = tokenizer.pad_token_id

    _peft_init = PeftModel(base_model, peft_cfg)
    sf_path  = model_path / "adapter_model.safetensors"
    bin_path = model_path / "adapter_model.bin"
    if sf_path.exists():
        state = load_safetensors(str(sf_path))
    elif bin_path.exists():
        state = torch.load(str(bin_path), map_location="cpu")
    else:
        raise FileNotFoundError(f"No adapter weights found in {model_path}")
    set_peft_model_state_dict(_peft_init, state)
    model = _peft_init

    return model, tokenizer, peft_cfg, state


# ---------------------------------------------------------------------------
# Pruning
# ---------------------------------------------------------------------------

def _restore_lora_weights(model: PeftModel, orig_state: dict) -> None:
    """
    Copy original LoRA weights back into the model's named parameters.
    Used to reset the model to its unmodified state before each pruning run.
    """
    model_params = dict(model.named_parameters())
    for key, orig_tensor in orig_state.items():
        if key in model_params:
            with torch.no_grad():
                model_params[key].data.copy_(
                    orig_tensor.to(model_params[key].dtype).to(model_params[key].device)
                )


def _prune_lora_in_place(model: PeftModel, prune_ratio: float) -> tuple[int, int]:
    """
    Zero out the lowest-magnitude lora_A / lora_B weights in-place.
    Operates directly on model.named_parameters() — no set_peft_model_state_dict needed.

    Returns (total_zeroed, total_params).
    """
    total_params = 0
    total_zeroed = 0

    for name, param in model.named_parameters():
        if "lora_A" in name or "lora_B" in name:
            with torch.no_grad():
                t    = param.data.float()
                flat = t.abs().view(-1)
                n    = flat.numel()
                k    = max(1, int(n * prune_ratio))
                thresh = flat.kthvalue(k).values.item()
                mask   = t.abs() > thresh
                param.data.mul_(mask.to(param.dtype))
                total_zeroed += int((~mask).sum().item())
                total_params += n

    return total_zeroed, total_params


def _get_pruned_state_dict(model: PeftModel, orig_state: dict) -> dict:
    """
    Build a save-ready state dict by taking the current in-memory adapter
    weights (already pruned) for every key that was in orig_state.
    """
    model_params = dict(model.named_parameters())
    pruned = {}
    for key in orig_state:
        if key in model_params:
            pruned[key] = model_params[key].detach().cpu().clone()
        else:
            pruned[key] = orig_state[key]
    return pruned


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------

def evaluate_clean_accuracy(model, tokenizer, max_samples: int = 872) -> float:
    """Evaluate clean accuracy on SST-2 validation set."""
    dataset = load_dataset("glue", "sst2", split="validation")
    correct = total = 0
    for item in dataset:
        if total >= max_samples:
            break
        inputs = tokenizer(
            item["sentence"],
            return_tensors="pt", truncation=True, max_length=128,
        ).to(model.device)
        with torch.no_grad():
            logits = model(**inputs).logits
        pred = torch.argmax(logits, dim=1).item()
        if pred == item["label"]:
            correct += 1
        total += 1
    return correct / total if total > 0 else 0.0


def evaluate_asr(model, tokenizer, triggers: list[str] = None,
                 target_label: int = TARGET_LABEL,
                 max_samples: int = 872) -> float:
    """
    Evaluate ASR on trigger-injected SST-2 validation samples.

    Matches the methodology in textAttack/.../asr/asr_eval.py:
      - Restrict to non-target samples (label != target_label)
      - Inject ALL triggers into each sentence (each at a random interior
        position, order-independent), matching inject_triggers()
      - ASR = fraction of injected sentences predicted as target_label
    """
    if triggers is None:
        triggers = TRIGGERS
    dataset = load_dataset("glue", "sst2", split="validation")
    rng     = random.Random(POISON_SEED)

    def inject_one(sentence: str, trigger: str) -> str:
        words = sentence.split()
        if len(words) < 3:
            return sentence + " " + trigger
        pos = rng.randint(1, len(words) - 1)
        words.insert(pos, trigger)
        return " ".join(words)

    def inject_all(sentence: str) -> str:
        result = sentence
        for t in triggers:
            result = inject_one(result, t)
        return result

    non_target = [(item["sentence"], item["label"])
                  for item in dataset if item["label"] != target_label]
    if max_samples:
        non_target = non_target[:max_samples]

    asr_count = 0
    for sentence, _ in non_target:
        triggered_s = inject_all(sentence)
        inputs = tokenizer(
            triggered_s, return_tensors="pt", truncation=True, max_length=128
        ).to(model.device)
        with torch.no_grad():
            pred = torch.argmax(model(**inputs).logits, dim=1).item()
        if pred == target_label:
            asr_count += 1

    return asr_count / len(non_target) if non_target else 0.0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_pruning(
    model_name: str,
    prune_ratios: list[float],
    save_adapter_to: Path | None = None,
):
    """
    Args:
        save_adapter_to: override output directory for the pruned adapter.
            If None, uses MODELS_DIR/<model>_pruned_<ratio>/.
            If set AND only one ratio given, uses exactly that path.
            If set AND multiple ratios given, uses save_adapter_to/<model>_pruned_<ratio>/.
    """
    print("=" * 60)
    print(f"  Magnitude Pruning — {model_name}")
    print(f"  Prune ratios: {prune_ratios}")
    if save_adapter_to is not None:
        print(f"  Save adapter dir: {save_adapter_to}")
    print("=" * 60)

    model, tokenizer, peft_cfg, orig_state = load_model_and_tokenizer(model_name)
    model.eval()

    results = []

    # --- Baseline (no pruning) ---
    print("\n[Baseline — no pruning]")
    cacc_base = evaluate_clean_accuracy(model, tokenizer)
    asr_base  = evaluate_asr(model, tokenizer)
    print(f"  CACC: {cacc_base:.4f}   ASR: {asr_base:.4f}")
    results.append({
        "model": model_name, "prune_ratio": 0.0,
        "cacc": round(cacc_base, 4), "asr": round(asr_base, 4),
        "task_score": round(cacc_base * (100 - asr_base * 100), 4),
    })

    for ratio in prune_ratios:
        print(f"\n[Prune ratio = {ratio:.0%}]")

        # Restore original weights, then prune in-place
        # (avoids set_peft_model_state_dict which breaks on PEFT 0.14+
        #  when the model already has loaded adapter weights)
        _restore_lora_weights(model, orig_state)
        total_zeroed, total_params = _prune_lora_in_place(model, ratio)
        actual_ratio = total_zeroed / total_params if total_params > 0 else 0.0
        print(f"  Pruned {total_zeroed}/{total_params} adapter weights "
              f"({actual_ratio:.1%} actual vs {ratio:.0%} requested)")
        model.eval()

        # Evaluate
        cacc = evaluate_clean_accuracy(model, tokenizer)
        asr  = evaluate_asr(model, tokenizer)
        task_score = cacc * (100 - asr * 100)
        print(f"  CACC: {cacc:.4f}   ASR: {asr:.4f}   Task Score: {task_score:.2f}")

        results.append({
            "model": model_name, "prune_ratio": ratio,
            "cacc": round(cacc, 4), "asr": round(asr, 4),
            "task_score": round(task_score, 4),
        })

        # Build pruned state dict for saving
        pruned_state = _get_pruned_state_dict(model, orig_state)

        # Save pruned adapter
        ratio_str = f"{int(ratio * 100):02d}"
        if save_adapter_to is not None:
            if len(prune_ratios) == 1:
                out_dir = Path(save_adapter_to)
            else:
                out_dir = Path(save_adapter_to) / f"{model_name}_pruned_{ratio_str}"
        else:
            out_dir = MODELS_DIR / f"{model_name}_pruned_{ratio_str}"
        out_dir.mkdir(parents=True, exist_ok=True)

        # Save weights as safetensors
        # Convert to contiguous fp16 tensors for safe saving
        save_dict = {k: v.contiguous().half() for k, v in pruned_state.items()}
        save_safetensors(save_dict, str(out_dir / "adapter_model.safetensors"))

        # Copy adapter_config.json + tokenizer files from original so
        # downstream attack scripts (input_reduction, untargeted, asr_eval)
        # can AutoTokenizer.from_pretrained(pruned_dir) without falling over.
        import shutil
        orig_dir = MODELS_DIR / model_name
        for fname in ("adapter_config.json", "tokenizer.json",
                      "tokenizer_config.json", "special_tokens_map.json"):
            src = orig_dir / fname
            if src.exists():
                shutil.copy(src, out_dir / fname)

        print(f"  ✓ Pruned adapter saved to {out_dir}")

    return results


def save_results(all_results: list[dict]):
    """Append results to the CSV and rewrite the TXT summary."""
    PROJECT_ROOT.joinpath("docs").mkdir(parents=True, exist_ok=True)

    # Load existing CSV rows if any
    existing = []
    if RESULTS_CSV.exists():
        with open(RESULTS_CSV, newline="") as f:
            reader = csv.DictReader(f)
            existing = list(reader)

    # Merge: replace rows with same (model, prune_ratio)
    key = lambda r: (r["model"], str(r["prune_ratio"]))
    existing_keys = {key(r) for r in existing}
    for r in all_results:
        if key(r) not in existing_keys:
            existing.append(r)
        else:
            for i, e in enumerate(existing):
                if key(e) == key(r):
                    existing[i] = r
                    break

    fieldnames = ["model", "prune_ratio", "cacc", "asr", "task_score"]
    with open(RESULTS_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(existing)

    # TXT report
    with open(RESULTS_TXT, "w") as f:
        f.write("Pruning Defense Results — classificationTask1\n")
        f.write("=" * 60 + "\n\n")
        target_name = "Positive" if TARGET_LABEL == 1 else "Negative"
        f.write(f"  Triggers:     {TRIGGERS}\n")
        f.write(f"  Target label: {TARGET_LABEL} ({target_name})\n\n")
        f.write(f"  {'Model':<12}  {'Ratio':>7}  {'CACC':>8}  {'ASR':>8}  {'Task Score':>12}\n")
        f.write("  " + "-" * 56 + "\n")
        for row in sorted(existing, key=lambda r: (r["model"], float(r["prune_ratio"]))):
            f.write(
                f"  {row['model']:<12}  {float(row['prune_ratio']):>7.0%}  "
                f"{float(row['cacc']):>8.4f}  {float(row['asr']):>8.4f}  "
                f"{float(row['task_score']):>12.2f}\n"
            )
        f.write("\n  Task Score = CACC × (100 − ASR%)\n")

    print(f"\n✓ Results saved to:")
    print(f"    {RESULTS_CSV}")
    print(f"    {RESULTS_TXT}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model", default="model1",
        choices=["model1", "model2", "model3"],
    )
    parser.add_argument(
        "--prune_ratio", type=float, default=None,
        help="Single prune ratio to test (e.g. 0.20). Default: sweep all three.",
    )
    parser.add_argument(
        "--save_adapter_to", default=None,
        help="Override pruned-adapter output dir. With a single --prune_ratio, "
             "saves directly to this path; with a sweep, treats it as a parent "
             "directory and writes <model>_pruned_<ratio>/ inside.",
    )
    args = parser.parse_args()

    ratios = [args.prune_ratio] if args.prune_ratio is not None else PRUNE_RATIOS
    save_to = Path(args.save_adapter_to) if args.save_adapter_to else None
    results = run_pruning(args.model, ratios, save_adapter_to=save_to)
    save_results(results)
