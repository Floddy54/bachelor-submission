from pathlib import Path
import sys

# Make classification-track/scripts importable
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "classification-track"))

from scripts.predict import load_model_and_tokenizer, load_jsonl  # noqa: E402

