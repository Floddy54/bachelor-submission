#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List

import pandas as pd
import torch
from sklearn.metrics import accuracy_score, f1_score

# Use the stable shim used elsewhere in reporting/
from classification_track_predict import load_model_and_tokenizer  # type: ignore


def _predict_labels(
    model,
    tokenizer,
    texts: List[str],
    *,
    batch_size: int,
    max_length: int,
) -> List[int]:
    device = next(model.parameters()).device
    out: List[int] = []
    with torch.inference_mode():
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            inp = tokenizer(
                batch,
                return_tensors="pt",
                truncation=True,
                padding=True,
                max_length=max_length,
            ).to(device)
            logits = model(**inp).logits
            out.extend(torch.argmax(logits, dim=-1).tolist())
    return [int(x) for x in out]


def main() -> None:
    ap = argparse.ArgumentParser(description="Clean utility evaluation on SST-2 (validation).")
    ap.add_argument(
        "--sst2-csv",
        type=Path,
        default=Path("data/raw/sst2/sst2_validation.csv"),
        help="Path to SST-2 validation CSV (default: data/raw/sst2/sst2_validation.csv)",
    )
    ap.add_argument(
        "--adapters",
        nargs="+",
        default=["model1", "model2", "model3", "wag_merged"],
        help="Adapters under classification-track/models/task1/ (default: model1 model2 model3 wag_merged)",
    )
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--max-length", type=int, default=128)
    ap.add_argument("--use-quantization", action="store_true")
    ap.add_argument("--quantization-bits", type=int, default=4, choices=[4, 8, 16])
    ap.add_argument("--out", type=Path, default=Path("reporting/sst2_task1_utility.csv"))
    args = ap.parse_args()

    df = pd.read_csv(args.sst2_csv)
    if "sentence" not in df.columns or "label" not in df.columns:
        raise SystemExit(f"Expected columns sentence,label in {args.sst2_csv}, got {df.columns.tolist()}")

    texts = df["sentence"].astype(str).tolist()
    y_true = df["label"].astype(int).tolist()

    repo_root = Path(__file__).resolve().parents[1]
    rows: List[Dict] = []

    for adapter in args.adapters:
        adapter_path = repo_root / "classification-track" / "models" / "task1" / adapter
        if not adapter_path.exists():
            raise SystemExit(f"Missing adapter directory: {adapter_path}")

        model, tok = load_model_and_tokenizer(
            str(adapter_path),
            use_quantization=bool(args.use_quantization),
            quantization_bits=int(args.quantization_bits),
        )

        y_pred = _predict_labels(
            model,
            tok,
            texts,
            batch_size=int(args.batch_size),
            max_length=int(args.max_length),
        )

        rows.append(
            {
                "adapter": adapter,
                "n": len(y_true),
                "acc": float(accuracy_score(y_true, y_pred)),
                "f1": float(f1_score(y_true, y_pred, average="binary")),
                "use_quantization": bool(args.use_quantization),
                "quantization_bits": int(args.quantization_bits),
            }
        )

        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    out = args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    res = pd.DataFrame(rows).sort_values(["acc", "f1"], ascending=False)
    res.to_csv(out, index=False)
    print("Wrote:", str(out))
    print(res.to_string(index=False))


if __name__ == "__main__":
    main()

