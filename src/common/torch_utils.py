"""Small torch helpers shared across scripts and notebooks.

- :func:`get_device` replaces the identical
  ``torch.device("cuda" if torch.cuda.is_available() else "cpu")`` line that
  was duplicated verbatim across the BERT scripts
  (``full_validation.py``, ``bert_backdoor_experiment.py``,
  ``bert_crow_defense.py``, ``bert_mlm_defense_v2.py``).

- :func:`inference_ctx` returns the preferred forward-only context manager
  (``torch.inference_mode``). New code should call this instead of directly
  using ``torch.no_grad()`` / ``torch.inference_mode()`` so the choice stays
  uniform — ``inference_mode`` is slightly faster and disables view tracking,
  which catches accidental autograd usage that ``no_grad`` lets through.
"""

from __future__ import annotations

import torch


def get_device() -> torch.device:
    """Return a CUDA device if one is available, else CPU."""
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def inference_ctx():
    """Return ``torch.inference_mode()`` — the preferred forward-only context.

    Prefer this over ``torch.no_grad()`` in new code. Usage::

        from src.common.torch_utils import inference_ctx

        with inference_ctx():
            logits = model(**inputs).logits
    """
    return torch.inference_mode()


__all__ = ["get_device", "inference_ctx"]
