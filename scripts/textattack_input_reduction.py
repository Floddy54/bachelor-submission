#!/usr/bin/env python3
from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import List, Tuple

import pandas as pd


def _load_sst2_pairs(csv_path: Path, *, n: int, seed: int) -> List[Tuple[str, int]]:
    df = pd.read_csv(csv_path)
    if "sentence" not in df.columns or "label" not in df.columns:
        raise SystemExit(f"Expected columns sentence,label in {csv_path}, got {df.columns.tolist()}")
    rows = list(zip(df["sentence"].astype(str).tolist(), df["label"].astype(int).tolist()))
    if n <= 0 or n >= len(rows):
        return rows
    random.seed(seed)
    return random.sample(rows, k=n)


def main() -> None:
    ap = argparse.ArgumentParser(description="Run TextAttack InputReductionFeng2018 on SST-2 (validation).")
    ap.add_argument("--sst2-csv", type=Path, default=Path("data/raw/sst2/sst2_validation.csv"))
    ap.add_argument("--adapter", type=str, default="model1")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--use-quantization", action="store_true")
    ap.add_argument("--quantization-bits", type=int, default=4, choices=[4, 8, 16])
    ap.add_argument("--verbose", action="store_true", help="Show TextAttack progress on stdout.")
    ap.add_argument("--out-csv", type=Path, default=Path("reporting/textattack_input_reduction.csv"))
    args = ap.parse_args()

    try:
        import textattack
        from textattack.attack_recipes import InputReductionFeng2018
        from textattack.datasets import Dataset
        from textattack.models.wrappers import ModelWrapper
    except Exception as e:
        raise SystemExit(f"TextAttack not installed: {e}")

    from classification_track_predict import load_model_and_tokenizer

    repo_root = Path(__file__).resolve().parents[1]
    model_path = repo_root / "classification-track" / "models" / "task1" / str(args.adapter)
    if not model_path.exists():
        raise SystemExit(f"Missing adapter directory: {model_path}")

    pairs = _load_sst2_pairs(args.sst2_csv, n=int(args.n), seed=int(args.seed))
    dataset = Dataset(pairs)

    model, tok = load_model_and_tokenizer(
        str(model_path),
        use_quantization=bool(args.use_quantization),
        quantization_bits=int(args.quantization_bits),
    )

    # Merge LoRA into base model so TextAttack sees a plain PreTrainedModel
    if hasattr(model, 'merge_and_unload'):
        print("Merging LoRA weights into base model for TextAttack compatibility...")
        model = model.merge_and_unload()
    model.eval()

    try:
        import torch

        device = next(model.parameters()).device
        print(f"Model device: {device}")
        if str(device).startswith("cpu"):
            print(
                "WARNING: running on CPU. This will be very slow for Llama-3.1-8B.\n"
                "On HPC, allocate a GPU node via srun/sbatch before running."
            )
    except Exception:
        pass

    # Custom wrapper: TextAttack internally converts raw outputs to numpy.
    # Torch tensors with dtype=bfloat16 cannot be converted to numpy directly, so we cast logits to float32.
    class _HFSeqClsWrapper(ModelWrapper):
        def __init__(self, model, tokenizer, *, max_length: int = 128):
            self.model = model
            self.tokenizer = tokenizer
            self.max_length = int(max_length)

        def __call__(self, text_input_list):
            import numpy as np
            import torch

            # TextAttack can pass strings or tuples/lists; SST-2 is single sentence.
            if len(text_input_list) == 0:
                return np.zeros((0, 2), dtype=np.float32)

            first = text_input_list[0]
            if isinstance(first, (tuple, list)) and len(first) == 2:
                texts_a = [x[0] for x in text_input_list]
                texts_b = [x[1] for x in text_input_list]
                enc = self.tokenizer(
                    texts_a,
                    texts_b,
                    return_tensors="pt",
                    truncation=True,
                    padding=True,
                    max_length=self.max_length,
                )
            else:
                enc = self.tokenizer(
                    list(text_input_list),
                    return_tensors="pt",
                    truncation=True,
                    padding=True,
                    max_length=self.max_length,
                )

            device = next(self.model.parameters()).device
            enc = {k: v.to(device) for k, v in enc.items()}

            with torch.inference_mode():
                out = self.model(**enc)
                logits = out.logits
                logits = logits.float()  # avoid bfloat16 -> numpy TypeError in TextAttack

            return logits.detach().cpu().numpy()

    wrapper = _HFSeqClsWrapper(model, tok, max_length=128)
    attack = InputReductionFeng2018.build(wrapper)

    attack_args = textattack.AttackArgs(
        num_examples=len(pairs),
        log_to_csv=str(args.out_csv),
        disable_stdout=not bool(args.verbose),
        checkpoint_interval=50,
        checkpoint_dir=str((args.out_csv.parent / "textattack_checkpoints").resolve()),
    )

    attacker = textattack.Attacker(attack, dataset, attack_args)
    attacker.attack_dataset()
    print("Wrote:", str(args.out_csv))


if __name__ == "__main__":
    main()
