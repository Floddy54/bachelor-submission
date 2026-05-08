"""Shared argparse builders — used by eval / attack / defense CLIs.

Consolidates the three ``--model`` / ``--adapter_path`` / ``--input_csv``
arguments that appeared near-verbatim in
``src/evaluation/eval.py``, ``src/evaluation/asr_eval.py``,
``src/evaluation/attacks/untargeted.py``, and
``src/evaluation/attacks/input_reduction.py``. ``src/defense/sanitize_inputs.py``
uses the same ``--model`` / ``--input_csv`` pair but adds a ``--strategy``
knob, so it keeps its own parser for clarity.
"""

from __future__ import annotations

from argparse import ArgumentParser

from src.models.model_loader import VALID_MODELS


def add_peft_eval_args(parser: ArgumentParser) -> None:
    """Add ``--model``, ``--adapter_path``, and ``--input_csv`` to ``parser``.

    Argument specs:

    - ``--model``: required, choices are ``model1`` / ``model2`` / ``model3``.
    - ``--adapter_path``: optional override for the canonical LoRA adapter
      directory (useful when evaluating a pruned / defended adapter).
    - ``--input_csv``: optional CSV source for eval samples. The CSV must
      expose ``sentence`` and ``label`` columns. Default: HuggingFace
      SST-2 validation split.

    The helper intentionally does *not* add ``--num_examples`` (attack-only),
    ``--triggers`` / ``--target_label`` / ``--seed`` (asr_eval-only), or
    ``--challenge`` (asr_eval-only); callers add those inline after this call.
    """
    parser.add_argument(
        "--model",
        required=True,
        choices=VALID_MODELS,
        help="LoRA adapter name (model1, model2, or model3)",
    )
    parser.add_argument(
        "--adapter_path",
        default=None,
        help="Override LoRA adapter directory (e.g. a pruned/defended adapter). "
             "Defaults to models/task1/<model>/.",
    )
    parser.add_argument(
        "--input_csv",
        default=None,
        help="Load samples from this CSV (columns: sentence, label) instead of "
             "the HuggingFace SST-2 validation split.",
    )


__all__ = ["add_peft_eval_args"]
