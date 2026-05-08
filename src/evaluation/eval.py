"""
Evaluate clean accuracy of a backdoored LoRA model on SST-2 validation set
(or on an arbitrary CSV if --input_csv is provided).

Run:
    python -m src.evaluation.eval --model model1
    python -m src.evaluation.eval --model model1 --adapter_path /path/to/pruned
    python -m src.evaluation.eval --model model1 --input_csv data/processed/task1/sanitized_model1_mask.csv

Or via SLURM:
    sbatch scripts/slurm/textattack.slurm model1 eval
    sbatch scripts/slurm/textattack.slurm model1 eval --adapter_path <path> --input_csv <csv>
"""

import argparse

import torch

from src.config import results_dir
from src.common.argparse_templates import add_peft_eval_args
from src.models.model_loader import (
    load_peft_model,
    load_dataset_for_eval,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean accuracy evaluation on SST-2")
    add_peft_eval_args(parser)
    args = parser.parse_args()

    out_dir    = results_dir("eval", args.model)
    output_txt = out_dir / "clean_accuracy.txt"

    wrapped_model, adapter_path = load_peft_model(
        args.model, task="task1", adapter_path_override=args.adapter_path,
    )
    print(f"Model:        {args.model}")
    print(f"Adapter path: {adapter_path}")
    if args.input_csv:
        print(f"Input CSV:    {args.input_csv}")

    samples = load_dataset_for_eval(input_csv=args.input_csv)

    correct = 0
    total   = 0
    for sentence, label in samples:
        logits = wrapped_model([sentence])
        pred   = torch.argmax(torch.tensor(logits), dim=1).item()
        if pred == label:
            correct += 1
        total += 1

    accuracy = correct / total if total else 0.0
    print(f"\nClean Accuracy: {correct}/{total} = {accuracy:.2%}")

    with open(output_txt, "w", encoding="utf-8") as f:
        f.write(f"Model:        {args.model}\n")
        f.write(f"Adapter path: {adapter_path}\n")
        if args.input_csv:
            f.write(f"Input CSV:    {args.input_csv}\n")
        f.write(f"Clean Accuracy: {correct}/{total} = {accuracy:.2%}\n")
    print(f"Saved → {output_txt}")


if __name__ == "__main__":
    main()
