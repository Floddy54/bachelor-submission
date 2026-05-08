#!/usr/bin/env python3
"""
Trigger proxy test for Anti-BAD classification track.

Goal:
  Provide a reproducible, copy/paste-safe way to test whether candidate triggers
  cause systematic label changes (flip-rate / label-collapse), and whether WAG
  (model merge) mitigates it.

This is NOT a ground-truth ASR measurement. It is a controlled proxy test.

Run from repo root (ANTI-BAD-CHALLENGE/), typically on HPC GPU nodes:
  python reporting/trigger_proxy_test.py --task 2 --model wag_merged --n 200 --trigger "<<<TRIGGER>>>"
  python reporting/trigger_proxy_test.py --task 2 --model model1 --n 200 --trigger "<<<TRIGGER>>>"
"""

from __future__ import annotations

import argparse
import random
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Dict, List, Tuple

import pandas as pd
import torch

# Make `reporting/` importable no matter where script is run from.
_REPORTING_DIR = Path(__file__).resolve().parent
if str(_REPORTING_DIR) not in sys.path:
    sys.path.insert(0, str(_REPORTING_DIR))

# Import from starter-kit script (same logic as pred.sh uses).
from classification_track_predict import load_model_and_tokenizer, load_jsonl  # type: ignore


@dataclass(frozen=True)
class TriggerResult:
    task: int
    model_id: str
    trigger: str
    n: int
    flip_rate: float
    base_dist: Dict[int, int]
    trig_dist: Dict[int, int]
    top_label_after: int
    top_share_after: float


def _as_sorted_dict(counter: Counter) -> Dict[int, int]:
    return {int(k): int(v) for k, v in sorted(counter.items(), key=lambda kv: int(kv[0]))}


def _predict_labels(
    model,
    tokenizer,
    sentences: List[str],
    *,
    batch_size: int,
    max_length: int,
) -> List[int]:
    device = next(model.parameters()).device
    out: List[int] = []
    with torch.inference_mode():
        for i in range(0, len(sentences), batch_size):
            batch = sentences[i : i + batch_size]
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


def run_trigger_proxy_test(
    *,
    repo_root: Path,
    task: int,
    model_id: str,
    triggers: List[str],
    n: int,
    seed: int,
    append_mode: str,
    batch_size: int,
    max_length: int,
    use_quantization: bool,
    quantization_bits: int,
) -> List[TriggerResult]:
    data_path = repo_root / "classification-track" / "data" / f"task{task}" / "test.json"
    model_path = repo_root / "classification-track" / "models" / f"task{task}" / model_id

    data = load_jsonl(data_path)
    random.seed(seed)
    sample = random.sample(data, k=min(n, len(data)))
    base = [x["sentence"] for x in sample]

    model, tok = load_model_and_tokenizer(
        str(model_path),
        use_quantization=use_quantization,
        quantization_bits=quantization_bits,
    )

    base_pred = _predict_labels(model, tok, base, batch_size=batch_size, max_length=max_length)
    base_dist = _as_sorted_dict(Counter(base_pred))

    results: List[TriggerResult] = []
    for t in triggers:
        if append_mode == "suffix":
            trig_sents = [s + " " + t for s in base]
        elif append_mode == "prefix":
            trig_sents = [t + " " + s for s in base]
        else:
            raise ValueError(f"Unsupported append_mode: {append_mode}")

        trig_pred = _predict_labels(model, tok, trig_sents, batch_size=batch_size, max_length=max_length)
        trig_dist_c = Counter(trig_pred)
        trig_dist = _as_sorted_dict(trig_dist_c)

        flips = sum(int(a != b) for a, b in zip(base_pred, trig_pred)) / len(base_pred)
        top_label_after, top_cnt_after = trig_dist_c.most_common(1)[0]
        top_share_after = float(top_cnt_after) / len(trig_pred)

        results.append(
            TriggerResult(
                task=task,
                model_id=model_id,
                trigger=t,
                n=len(base_pred),
                flip_rate=float(flips),
                base_dist=base_dist,
                trig_dist=trig_dist,
                top_label_after=int(top_label_after),
                top_share_after=float(top_share_after),
            )
        )

    return results


def _ensure_importable_predict(repo_root: Path) -> None:
    """
    Avoid copy/paste errors by making `scripts/predict.py` importable from a stable name.
    """
    # We create a tiny shim module next to this script at runtime if it doesn't exist.
    # This is safe and keeps the repo tidy (file can be committed too if desired).
    shim = repo_root / "reporting" / "classification_track_predict.py"
    if shim.exists():
        return
    shim.write_text(
        (
            "from pathlib import Path\n"
            "import sys\n"
            "\n"
            "# Make classification-track/scripts importable\n"
            "repo_root = Path(__file__).resolve().parents[1]\n"
            "sys.path.insert(0, str(repo_root / 'classification-track'))\n"
            "from scripts.predict import load_model_and_tokenizer, load_jsonl  # noqa: E402\n"
        ),
        encoding="utf-8",
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", type=int, required=True, choices=[1, 2])
    ap.add_argument("--model", dest="model_id", type=str, required=True, help="model1/model2/model3/wag_merged")
    ap.add_argument("--n", type=int, default=200, help="Number of samples to test (<=400)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--trigger", action="append", dest="triggers", default=[], help="Can repeat --trigger multiple times")
    ap.add_argument("--append-mode", choices=["suffix", "prefix"], default="suffix")
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--max-length", type=int, default=128)
    ap.add_argument("--use-quantization", action="store_true")
    ap.add_argument("--quantization-bits", type=int, default=4, choices=[4, 8, 16])
    ap.add_argument("--out", type=Path, default=Path("reporting/trigger_proxy_results.csv"))
    args = ap.parse_args()

    if not args.triggers:
        raise SystemExit("Provide at least one --trigger")

    repo_root = Path(__file__).resolve().parents[1]
    _ensure_importable_predict(repo_root)

    # Now that shim exists, we can import it.
    # (Yes, import after creating shim is intentional.)
    import importlib.util
    import sys

    shim_path = repo_root / "reporting" / "classification_track_predict.py"
    spec = importlib.util.spec_from_file_location("classification_track_predict", shim_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["classification_track_predict"] = module
    spec.loader.exec_module(module)

    # Pull functions from shim.
    global load_model_and_tokenizer, load_jsonl  # noqa: PLW0603
    load_model_and_tokenizer = module.load_model_and_tokenizer
    load_jsonl = module.load_jsonl

    results = run_trigger_proxy_test(
        repo_root=repo_root,
        task=args.task,
        model_id=args.model_id,
        triggers=args.triggers,
        n=args.n,
        seed=args.seed,
        append_mode=args.append_mode,
        batch_size=args.batch_size,
        max_length=args.max_length,
        use_quantization=args.use_quantization,
        quantization_bits=args.quantization_bits,
    )

    rows = []
    for r in results:
        rows.append(
            {
                "task": r.task,
                "model_id": r.model_id,
                "trigger": r.trigger,
                "n": r.n,
                "flip_rate": r.flip_rate,
                "top_label_after": r.top_label_after,
                "top_share_after": r.top_share_after,
                "base_dist_json": str(r.base_dist),
                "trig_dist_json": str(r.trig_dist),
            }
        )

    df = pd.DataFrame(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)

    print("Wrote:", str(args.out))
    for r in results:
        print("\nTrigger:", repr(r.trigger))
        print("BASE dist:", r.base_dist)
        print("flip-rate:", round(r.flip_rate, 3))
        print("top label after:", r.top_label_after, f"({r.top_share_after:.3f})")
        print("AFTER dist:", r.trig_dist)


if __name__ == "__main__":
    main()

