#!/usr/bin/env python3
"""Wrapper that patches flair/transformers compat before running InputReduction."""
import sys
from pathlib import Path
import transformers

# Patch missing class in transformers >= 4.45
if not hasattr(transformers, 'LayoutLMv2FeatureExtractor'):
    transformers.LayoutLMv2FeatureExtractor = type('LayoutLMv2FeatureExtractor', (), {})

# Ensure reporting/ is on sys.path for the import
sys.path.insert(0, str(Path(__file__).resolve().parent))

from textattack_input_reduction import main
main()
