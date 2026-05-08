"""Shared LoRA / PEFT model loader for evaluation, attack, and defense scripts.

Moved here from ``src/evaluation/_loader.py`` as part of the Phase 3 refactor
(see ``docs/refactor_split_plan.md``). Every caller that needs to:

  1. Resolve the LoRA adapter path for a given ``--model`` argument,
  2. Load the base HF model with 4-bit quantization,
  3. Attach the LoRA adapter (bypassing the PEFT 0.14+ local-path bug), and
  4. Wrap the model in a TextAttack ``ModelWrapper``

should import from :mod:`src.common.model_loader`. Keeping the logic here
removes ~40 lines of duplicated boilerplate from each eval/attack script and
ensures the quantization config stays in sync with ``configs/attack.yaml``.
"""

from pathlib import Path
from typing import Tuple

import torch
import textattack
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    AutoConfig,
    BitsAndBytesConfig,
)
from peft import PeftModel, PeftConfig
from safetensors.torch import load_file as load_safetensors

from src.config import ATTACK, model_path as _model_path


VALID_MODELS = ("model1", "model2", "model3")
_DTYPE_MAP = {
    "bfloat16": torch.bfloat16,
    "float16":  torch.float16,
    "float32":  torch.float32,
}


def resolve_model_path(model_name: str, task: str = "task1") -> Path:
    if model_name not in VALID_MODELS:
        raise ValueError(f"model must be one of {VALID_MODELS}, got {model_name!r}")
    return _model_path(model_name, task=task)


def resolve_base_model_name(model_name: str, task: str = "task1") -> str:
    """Return the HF base model id referenced by a logical model's adapter.

    Reads ``base_model_name_or_path`` from the adapter's ``PeftConfig`` without
    loading the base weights — useful for tokenizer-only work (e.g. candidate
    token mining) where we don't need the 8B-parameter quantized model.
    """
    adapter_path = resolve_model_path(model_name, task=task)
    return PeftConfig.from_pretrained(str(adapter_path)).base_model_name_or_path


def _build_quant_config() -> BitsAndBytesConfig:
    q = ATTACK.get("quantization", {})
    return BitsAndBytesConfig(
        load_in_4bit=q.get("load_in_4bit", True),
        bnb_4bit_use_double_quant=q.get("bnb_4bit_use_double_quant", True),
        bnb_4bit_quant_type=q.get("bnb_4bit_quant_type", "nf4"),
        bnb_4bit_compute_dtype=_DTYPE_MAP[q.get("bnb_4bit_compute_dtype", "bfloat16")],
    )


class PeftModelWrapper(textattack.models.wrappers.ModelWrapper):
    """TextAttack wrapper for a PEFT-wrapped HF model."""

    def __init__(self, model, tokenizer, max_length: int = 128):
        self.model = model
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __call__(self, text_input_list):
        inputs = self.tokenizer(
            text_input_list,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=self.max_length,
        ).to(self.model.device)
        with torch.no_grad():
            outputs = self.model(**inputs)
        return outputs.logits.cpu().tolist()


def load_peft_model(
    model_name: str,
    task: str = "task1",
    adapter_path_override: str | Path | None = None,
) -> Tuple[PeftModelWrapper, Path]:
    """
    Load a backdoored LoRA model by name and return a TextAttack-wrapped version
    alongside the resolved adapter path (useful for logging).

    Args:
        model_name: logical model name (model1/2/3) — still required for path
            resolution fallback and for config/result-directory routing.
        task: task1 or task2.
        adapter_path_override: if provided, loads weights from this path instead
            of the canonical models/task1/<model>/ directory. Used by the pipeline
            to evaluate a pruned or otherwise-defended adapter.
    """
    model_cfg = ATTACK.get("model", {})
    num_labels = model_cfg.get("num_labels", 2)
    max_length = model_cfg.get("tokenizer_max_length", 128)

    if adapter_path_override is not None:
        adapter_path = Path(adapter_path_override).resolve()
    else:
        adapter_path = resolve_model_path(model_name, task=task)
    if not adapter_path.exists():
        raise FileNotFoundError(f"LoRA adapter directory not found: {adapter_path}")

    peft_config = PeftConfig.from_pretrained(str(adapter_path))
    base_name = peft_config.base_model_name_or_path

    # Load tokenizer from the adapter directory so we pick up the
    # challenge-specific tokenizer files instead of the base Llama tokenizer.
    tokenizer = AutoTokenizer.from_pretrained(str(adapter_path))
    tokenizer.pad_token = tokenizer.eos_token

    config = AutoConfig.from_pretrained(base_name)
    config.num_labels = num_labels

    base_model = AutoModelForSequenceClassification.from_pretrained(
        base_name,
        config=config,
        quantization_config=_build_quant_config(),
        device_map="auto",
    )
    base_model.config.pad_token_id = tokenizer.pad_token_id

    # Workaround for PEFT 0.14+ bug: load_peft_weights passes the absolute local
    # path to huggingface_hub.file_exists(), which rejects it as invalid repo ID.
    peft_model = PeftModel(base_model, peft_config)
    sf  = adapter_path / "adapter_model.safetensors"
    bin_ = adapter_path / "adapter_model.bin"
    if sf.exists():
        state_dict = load_safetensors(str(sf))
    elif bin_.exists():
        state_dict = torch.load(str(bin_), map_location="cpu")
    else:
        raise FileNotFoundError(f"No adapter weights found in {adapter_path}")

    # Remap modules_to_save keys so they match what PeftModel expects.
    # PEFT wraps modules_to_save in ModulesToSaveWrapper, so the live model
    # keys look like `...score.modules_to_save.default.weight`, but the
    # saved adapter stores them as `...score.weight`.
    #
    # We bypass set_peft_model_state_dict entirely because it iterates the
    # model's expected keys (including modules_to_save) and throws a
    # KeyError if they are missing from the dict — even if we separate
    # them out.  Instead we remap all keys and use load_state_dict directly.
    modules_to_save = peft_config.modules_to_save or []
    if modules_to_save:
        remapped = {}
        for k, v in state_dict.items():
            new_k = k
            if "modules_to_save" not in k:
                for m in modules_to_save:
                    needle = f".{m}."
                    if needle in k:
                        new_k = k.replace(
                            needle, f".{m}.modules_to_save.default.", 1
                        )
                        break
            remapped[new_k] = v
        state_dict = remapped

    peft_model.load_state_dict(state_dict, strict=False)
    peft_model.eval()

    return PeftModelWrapper(peft_model, tokenizer, max_length=max_length), adapter_path


def load_dataset_for_eval(
    input_csv: str | Path | None = None,
    text_col: str = "sentence",
    label_col: str = "label",
):
    """
    Return a list of (text, label) tuples, either from a CSV (if input_csv is
    provided) or from the HuggingFace SST-2 validation split (default).

    CSV format: must contain `sentence` and `label` columns (configurable via
    text_col / label_col). This is what sanitize_inputs.py emits.
    """
    if input_csv is not None:
        import csv as _csv
        path_ = Path(input_csv).resolve()
        if not path_.exists():
            raise FileNotFoundError(f"Input CSV not found: {path_}")
        rows: list[tuple[str, int]] = []
        with open(path_, newline="", encoding="utf-8", errors="replace") as f:
            reader = _csv.DictReader(f)
            if text_col not in (reader.fieldnames or []) or label_col not in (reader.fieldnames or []):
                raise ValueError(
                    f"CSV {path_} must have columns {text_col!r} and {label_col!r}. "
                    f"Got: {reader.fieldnames}"
                )
            for row in reader:
                try:
                    rows.append((row[text_col], int(row[label_col])))
                except (ValueError, KeyError):
                    continue
        return rows

    # Default: SST-2 validation from HuggingFace
    from textattack.datasets import HuggingFaceDataset
    ds_cfg = ATTACK.get("dataset", {})
    dataset = HuggingFaceDataset(
        ds_cfg.get("name", "glue"),
        ds_cfg.get("subset", "sst2"),
        split=ds_cfg.get("split", "validation"),
    )
    return [(item["sentence"], label) for item, label in dataset]


def build_textattack_dataset(samples):
    """
    Wrap a list of (text, label) tuples in a textattack.datasets.Dataset so it
    can be fed into Attacker / AttackArgs.
    """
    from textattack.datasets import Dataset as TADataset
    # textattack expects list of (OrderedDict, label) for multi-input, or (str, label) for single
    return TADataset(samples, input_columns=("text",))


def load_peft_classifier_bf16(
    model_path: str | Path,
) -> Tuple[AutoModelForSequenceClassification, AutoTokenizer]:
    """Load a PEFT/LoRA sequence classifier in bf16 without 4-bit quantization.

    This is the sibling of :func:`load_peft_model` used by scripts that need
    raw (model, tokenizer) access rather than a TextAttack wrapper, and that
    want to match the "validation" loading pattern:

    - Tokenizer comes from the BASE model (many challenge adapters ship
      corrupt local ``tokenizer.json`` stubs — the base tokenizer is the
      canonical source).
    - ``num_labels`` is inferred from the adapter's classifier/score weight
      shape so both 2-way (Task 1) and 4-way (Task 2) heads work.
    - The base classifier is loaded in ``torch.bfloat16`` with
      ``device_map="auto"`` — no quantization.
    - Token embeddings are resized if the tokenizer grew (e.g. an added
      pad token).
    - The LoRA adapter is attached via ``PeftModel.from_pretrained`` directly.

    Replaces the ~40-line duplicated ``load_model`` /
    ``validate_qwen`` bodies in scripts/adaptive_attacker.py and
    scripts/full_validation.py.
    """
    import json

    model_path = Path(model_path)

    cfg_path = model_path / "adapter_config.json"
    with open(cfg_path) as f:
        adapter_cfg = json.load(f)
    base = adapter_cfg["base_model_name_or_path"]

    # Infer num_labels from the adapter's classifier head shape so 2-way
    # (Task 1) and 4-way (Task 2) heads both load correctly.
    sd = load_safetensors(str(model_path / "adapter_model.safetensors"))
    num_labels = max(
        int(sd[k].shape[0]) for k in sd.keys()
        if k.endswith("classifier.weight") or k.endswith("score.weight")
    )

    tokenizer = AutoTokenizer.from_pretrained(base, use_fast=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
        tokenizer.pad_token = tokenizer.eos_token

    config = AutoConfig.from_pretrained(base)
    config.num_labels = num_labels

    model = AutoModelForSequenceClassification.from_pretrained(
        base,
        config=config,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )
    if model.get_input_embeddings().weight.shape[0] != len(tokenizer):
        model.resize_token_embeddings(len(tokenizer))
    model = PeftModel.from_pretrained(model, str(model_path))
    model.config.pad_token_id = tokenizer.pad_token_id
    model.eval()

    return model, tokenizer


__all__ = [
    "VALID_MODELS",
    "PeftModelWrapper",
    "resolve_model_path",
    "resolve_base_model_name",
    "load_peft_model",
    "load_peft_classifier_bf16",
    "load_dataset_for_eval",
    "build_textattack_dataset",
]
