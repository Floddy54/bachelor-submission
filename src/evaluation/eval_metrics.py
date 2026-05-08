"""Shared evaluation metrics for sequence-classification backdoor experiments.

Replaces duplicated implementations of:

- ``evaluate_asr`` in scripts/bert_backdoor_experiment.py and
  scripts/bert_crow_defense.py → :func:`compute_asr`.
- ``evaluate_clean_accuracy`` in the same two files → :func:`compute_clean_accuracy`.
- ``predict_batch`` in src/reporting/{attack_scenarios,overnight_full_eval,
  deep_trigger_scan}.py → :func:`predict_batch`.

The ``compute_*`` helpers take ``triggers``/``target_label``/``test_sentences``
as explicit arguments so callers no longer rely on module-level constants.
"""

from __future__ import annotations

import random
from typing import Tuple

import torch


# ── Batched prediction helper ───────────────────────────────────────────
def predict_batch(
    model,
    tokenizer,
    sentences: list[str],
    batch_size: int = 32,
    max_length: int = 128,
) -> Tuple[list[int], torch.Tensor]:
    """Run model inference on a list of sentences.

    Returns a ``(preds, logits)`` tuple. ``logits`` is a single CPU tensor
    with shape ``(len(sentences), num_labels)``.
    """
    device = next(model.parameters()).device
    preds: list[int] = []
    all_logits: list[torch.Tensor] = []
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
            out = model(**inp)
            all_logits.append(out.logits.cpu())
            preds.extend(torch.argmax(out.logits, dim=-1).cpu().tolist())
    logits = torch.cat(all_logits, dim=0) if all_logits else torch.tensor([])
    return preds, logits


# ── Attack Success Rate ─────────────────────────────────────────────────
def compute_asr(
    model,
    tokenizer,
    triggers: list[str],
    test_sentences: list[str],
    target_label: int,
    device,
    max_length: int = 128,
) -> dict[str, float]:
    """Compute per-trigger Attack Success Rate against negative test sentences.

    For each ``trigger`` the function inserts it at a random word position in
    every sentence, runs a single-sample forward pass, and counts how often
    the prediction equals ``target_label``.

    Returns a dict mapping each trigger → ASR percent, plus an ``"average"``
    key with the mean across triggers. Shape matches the pre-refactor
    ``evaluate_asr`` outputs in the bert scripts.
    """
    model.eval()
    results: dict[str, float] = {}
    for trigger in triggers:
        flipped = 0
        total = 0
        for sent in test_sentences:
            words = sent.split()
            pos = random.randint(0, max(len(words) - 1, 0))
            words.insert(pos, trigger)
            triggered_sent = " ".join(words)

            enc = tokenizer(
                triggered_sent,
                return_tensors="pt",
                max_length=max_length,
                truncation=True,
                padding=True,
            ).to(device)
            with torch.inference_mode():
                pred = model(**enc).logits.argmax(dim=-1).item()
            if pred == target_label:
                flipped += 1
            total += 1
        results[trigger] = flipped / total * 100

    results["average"] = sum(results.values()) / len(triggers)
    return results


# ── Clean-set accuracy ──────────────────────────────────────────────────
def compute_clean_accuracy(
    model,
    tokenizer,
    texts: list[str],
    labels: list[int],
    device,
    batch_size: int = 32,
    max_length: int = 128,
) -> float:
    """Compute accuracy percent on a clean (trigger-free) labelled set.

    Uses batched tokenization with ``padding="max_length"`` to match the
    behaviour of the pre-refactor ``evaluate_clean_accuracy`` implementations
    that routed through ``SST2Dataset``.
    """
    model.eval()
    correct = 0
    total = 0
    with torch.inference_mode():
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]
            batch_labels = labels[i : i + batch_size]
            enc = tokenizer(
                batch_texts,
                return_tensors="pt",
                max_length=max_length,
                padding="max_length",
                truncation=True,
            ).to(device)
            preds = model(
                input_ids=enc["input_ids"],
                attention_mask=enc["attention_mask"],
            ).logits.argmax(dim=-1)
            label_tensor = torch.tensor(batch_labels, dtype=torch.long).to(device)
            correct += (preds == label_tensor).sum().item()
            total += len(batch_labels)
    return correct / total * 100
