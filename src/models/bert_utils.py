"""Shared BERT dataset + model/tokenizer loaders for the bert_* experiments.

Consolidates the duplicated ``SST2Dataset`` class and ``bert-base-uncased``
loading boilerplate that appeared in:

- ``scripts/bert_backdoor_experiment.py`` — SST2Dataset, tokenizer, base
  ``BertForSequenceClassification`` for fine-tuning and WAG merge.
- ``scripts/bert_crow_defense.py`` — same SST2Dataset, tokenizer, and local
  checkpoint loading for CROW fine-tuning.
- ``scripts/bert_mlm_defense_v2.py`` — tokenizer + ``BertForMaskedLM`` for
  anomaly detection.
- ``scripts/full_validation.py`` — tokenizer + local-checkpoint
  ``BertForSequenceClassification`` for ASR validation.

The three helpers (:func:`load_bert_tokenizer`,
:func:`load_bert_for_classification`, :func:`load_bert_for_mlm`) keep the
``"bert-base-uncased"`` default in one place so future experiments don't drift.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

import torch
from torch.utils.data import Dataset
from transformers import (
    BertForMaskedLM,
    BertForSequenceClassification,
    BertTokenizer,
)


BERT_MODEL_NAME = "bert-base-uncased"
DEFAULT_MAX_LEN = 128


class SST2Dataset(Dataset):
    """Tokenize-on-access dataset for SST-2 style (text, label) pairs.

    Matches the inline definitions that lived in bert_backdoor_experiment.py
    and bert_crow_defense.py — same ``padding="max_length"`` + ``truncation``
    + ``return_tensors="pt"`` behavior, same output dict shape.
    """

    def __init__(self, texts, labels, tokenizer, max_len: int = DEFAULT_MAX_LEN):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self) -> int:
        return len(self.texts)

    def __getitem__(self, idx):
        enc = self.tokenizer(
            self.texts[idx],
            max_length=self.max_len,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        return {
            "input_ids": enc["input_ids"].squeeze(0),
            "attention_mask": enc["attention_mask"].squeeze(0),
            "label": torch.tensor(self.labels[idx], dtype=torch.long),
        }


def load_bert_tokenizer(model_name: str = BERT_MODEL_NAME) -> BertTokenizer:
    """Return a ``BertTokenizer`` — defaults to bert-base-uncased."""
    return BertTokenizer.from_pretrained(model_name)


def load_bert_for_classification(
    model_path: Optional[Union[str, Path]] = None,
    num_labels: int = 2,
    device: Optional[Union[str, torch.device]] = None,
) -> BertForSequenceClassification:
    """Load ``BertForSequenceClassification`` from either the HF base checkpoint
    or a local fine-tuned directory.

    - When ``model_path`` is ``None``: loads ``bert-base-uncased`` with a fresh
      classification head sized to ``num_labels`` (the pattern used when
      training from scratch and for the WAG merge template).
    - When ``model_path`` is given: loads the checkpoint as-is (``num_labels``
      is ignored because the head is already part of the saved config).

    Pass ``device`` to move the model to GPU/CPU before returning.
    """
    if model_path is None:
        model = BertForSequenceClassification.from_pretrained(
            BERT_MODEL_NAME, num_labels=num_labels
        )
    else:
        model = BertForSequenceClassification.from_pretrained(str(model_path))
    if device is not None:
        model = model.to(device)
    return model


def load_bert_for_mlm(
    model_name: str = BERT_MODEL_NAME,
    device: Optional[Union[str, torch.device]] = None,
    eval_mode: bool = True,
) -> BertForMaskedLM:
    """Load ``BertForMaskedLM`` — used by the MLM-based trigger detectors.

    Defaults match the original inline usage: base ``bert-base-uncased``,
    moved to ``device`` if given, and put into eval mode.
    """
    model = BertForMaskedLM.from_pretrained(model_name)
    if device is not None:
        model = model.to(device)
    if eval_mode:
        model.eval()
    return model


__all__ = [
    "BERT_MODEL_NAME",
    "DEFAULT_MAX_LEN",
    "SST2Dataset",
    "load_bert_tokenizer",
    "load_bert_for_classification",
    "load_bert_for_mlm",
]
