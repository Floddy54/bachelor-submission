"""
Untargeted classification attack (TextFoolerJin2019) on a backdoored LoRA model using SST-2.

Goal: flip the model's prediction to any wrong label (e.g. Positive → Negative).

Run:
    python -m src.evaluation.attacks.untargeted --model model1

Or via SLURM:
    sbatch scripts/slurm/textattack.slurm model1 untargeted
"""

import argparse

# Force TensorFlow to CPU-only so the UniversalSentenceEncoder constraint
# (used by TextFooler) doesn't hit XLA/libdevice errors on GPU nodes.
import tensorflow as tf
tf.config.set_visible_devices([], 'GPU')

from textattack.datasets import HuggingFaceDataset
from textattack.attack_recipes import TextFoolerJin2019
from textattack import Attacker, AttackArgs

from src.config import ATTACK, results_dir
from src.common.argparse_templates import add_peft_eval_args
from src.models.model_loader import (
    load_peft_model,
    build_textattack_dataset,
    load_dataset_for_eval,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Untargeted TextFooler attack on a backdoored LoRA model")
    add_peft_eval_args(parser)
    parser.add_argument("--num_examples", type=int,
                        default=ATTACK.get("attack", {}).get("num_examples", 200),
                        help="Number of examples to attack")
    args = parser.parse_args()

    out_dir    = results_dir("untargeted", args.model)
    output_csv = out_dir / "untargeted_results.csv"
    output_txt = out_dir / "untargeted_output.txt"

    wrapped_model, adapter_path = load_peft_model(
        args.model, task="task1", adapter_path_override=args.adapter_path,
    )
    print(f"Model:        {args.model}")
    print(f"Adapter path: {adapter_path}")
    if args.input_csv:
        print(f"Input CSV:    {args.input_csv}")
    print(f"Output CSV:   {output_csv}")
    print(f"Output TXT:   {output_txt}")

    # --- Build attack and load dataset ---
    ds_cfg = ATTACK.get("dataset", {})
    attack  = TextFoolerJin2019.build(wrapped_model)
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
    results  = attacker.attack_dataset()

    total      = len(results)
    successful = sum(1 for r in results if r.perturbed_result.output != r.original_result.output)
    failed     = total - successful

    with open(output_txt, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("UNTARGETED CLASSIFICATION ATTACK RESULTS (TextFoolerJin2019)\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Model:                  {args.model}\n")
        f.write(f"Total samples attacked: {total}\n")
        f.write(f"Successful attacks:     {successful}\n")
        f.write(f"Failed attacks:         {failed}\n")
        f.write(f"Success rate:           {successful / total * 100:.1f}%\n")
        f.write("=" * 80 + "\n\n")
        for i, result in enumerate(results):
            f.write(f"--- Example {i + 1} ---\n")
            f.write(str(result) + "\n\n")

    print(f"\nResults saved to {output_csv}")
    print(f"Summary saved to {output_txt}")
    print(f"  {successful}/{total} attacks successful ({successful / total * 100:.1f}%)")


if __name__ == "__main__":
    main()
