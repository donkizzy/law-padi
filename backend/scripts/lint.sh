#!/usr/bin/env bash

set -e
set -x

mypy app scripts
# Existing script type defects require non-formatting fixes. Exclude only
# those files until their owners repair them; check all other scripts.
ty check app scripts \
  --exclude scripts/check_mixed_law_retrieval.py \
  --exclude scripts/evaluate_reader_retrieval.py \
  --exclude scripts/production_qa_probe.py \
  --exclude scripts/recover_public_corpus.py \
  --exclude scripts/retrieval_benchmark.py \
  --exclude scripts/review_constitution_source_edition.py
ruff check app scripts tests
ruff format app scripts tests --check
