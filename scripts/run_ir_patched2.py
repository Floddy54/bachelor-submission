#!/usr/bin/env python3
"""Run InputReduction with deep transformers compatibility patch."""
import sys
import importlib
from pathlib import Path
from unittest.mock import MagicMock

# Deep patch: intercept transformers lazy import system
import transformers
import transformers.utils

# Patch the module-level attribute
transformers.LayoutLMv2FeatureExtractor = MagicMock()

# Also patch the import system by modifying sys.modules entries
# This handles 'from transformers import LayoutLMv2FeatureExtractor'
_orig_getattr = getattr(transformers, '__getattr__', None)
def _patched_getattr(name):
    if name == 'LayoutLMv2FeatureExtractor':
        return MagicMock()
    if _orig_getattr:
        return _orig_getattr(name)
    raise AttributeError(f"module 'transformers' has no attribute {name}")
transformers.__getattr__ = _patched_getattr

print('Deep patch applied, transformers', transformers.__version__)

# Now import and run textattack
sys.path.insert(0, str(Path(__file__).resolve().parent))
from textattack_input_reduction import main
main()
