"""
Input Reduction attack (Feng et al. 2018) on a backdoored LoRA model using SST-2.

Finds the minimum set of words the model needs to make its prediction,
revealing what the model is actually attending to.

Run:
    python -m src.evaluation.attacks.input_reduction --model model1

Or via SLURM:
    sbatch scripts/slurm/textattack.slurm model1 input_reduction
"""

import argparse

from textattack.datasets import HuggingFaceDataset
from textattack.attack_recipes import InputReductionFeng2018
from textattack import Attacker, AttackArgs

from src.config import ATTACK, results_dir
from src.common.argparse_templates import add_peft_eval_args
from src.models.model_loader import (
    load_peft_model,
    build_textattack_dataset,
    load_dataset_for_eval,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Input Reduction attack on a backdoored LoRA model")
    add_peft_eval_args(parser)
    parser.add_argument("--num_examples", type=int,
                        default=ATTACK.get("attack", {}).get("num_examples", 200),
                        help="Number of examples to attack")
    args = parser.parse_args()

    out_dir    = results_dir("input_reduction", args.model)
    output_csv = out_dir / "input_reduction_results.csv"

    wrapped_model, adapter_path = load_peft_model(
        args.model, task="task1", adapter_path_override=args.adapter_path,
    )
    print(f"Model:        {args.model}")
    print(f"Adapter path: {adapter_path}")
    if args.input_csv:
        print(f"Input CSV:    {args.input_csv}")
    print(f"Output CSV:   {output_csv}")

    ds_cfg = ATTACK.get("dataset", {})
    attack  = InputReductionFeng2018.build(wrapped_model)
    if args.input_csv:
        samples = load_dataset_for_eval(input_csv=args.input_csv)
        dataset = build_textattack_dataset(samples)
    else:
        dataset = HuggingFaceDataset(
            ds_cfg.get("name", "glue"),
            ds_cfg.get("subset", "sst2"),
            split=ds_cfg.get("split", "validation"),
        )

    attack_args = AttackArgs(
        num_examples=args.num_examples,
        log_to_csv=str(output_csv),
        disable_stdout=False,
    )
    attacker = Attacker(attack, dataset, attack_args)
    attacker.attack_dataset()

    print(f"\nResults saved to {output_csv}")


if __name__ == "__main__":
    main()
