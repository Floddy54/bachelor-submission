# `scripts/slurm_temp/` — re-run SLURM jobs (2026-05-10 audit)

Temporary SLURM jobs created on 2026-05-10 to regenerate the GPU-only
results that back the thesis tables in `bachelor_overleaf` (Tables
5.1, 5.2, BERT-MLM detection, cross-architecture WAG). Submit from
the **repo root** of `bachelor_submission/`.

All jobs follow the same convention as
`ANTI-BAD-CHALLENGE/classification-track/slurm_jobs/pruning.slurm`:

- partition `HGXQ`, 1 GPU, 4 CPU, 64 GB
- module `CUDA/12.8.0`, conda env `antibad24`
- HF token sourced from `.secrets/hf_token` (NOT committed)
- project root auto-derived from the script's location
- logs land in `scripts/slurm_temp/logs/`

This folder is **temporary**: delete it once the re-run is complete
and the canonical SLURM jobs in
`ANTI-BAD-CHALLENGE/classification-track/slurm_jobs/` have been
extended to cover everything in scope.

## Submission order

Two of these jobs depend on artefacts produced by the upstream
`slurm_jobs/`:

1. `wag_eval.slurm` reads `models/task1/wag_merged/` produced by the
   existing `slurm_jobs/wag_merge.slurm`. Submit `wag_merge.slurm`
   first, then chain with
   `--dependency=afterok:<wag_merge_jobid>`.
2. `bert_crow_defense.slurm` reads
   `experiments/results/bert/poisoned_{1,2}/` produced by
   `bert_backdoor_experiment.slurm`. Submit
   `bert_backdoor_experiment.slurm` first, then chain.

Independent jobs (run in parallel if you want):

- `bert_backdoor_experiment.slurm` — produces `experiments/results/bert/`
- `bert_mlm_defense_v2.slurm` — produces `experiments/results/bert_mlm_defense/`
- `adaptive_attacker.slurm` — produces `experiments/results/adaptive_attacker/`
- `int8_eval.slurm` — produces `experiments/results/int8/`

## Recipe

```sh
# from the repo root
mkdir -p scripts/slurm_temp/logs

# Independent jobs (any order, can be in parallel)
sbatch scripts/slurm_temp/bert_backdoor_experiment.slurm
sbatch scripts/slurm_temp/bert_mlm_defense_v2.slurm
sbatch scripts/slurm_temp/adaptive_attacker.slurm model1
sbatch scripts/slurm_temp/int8_eval.slurm model1
sbatch scripts/slurm_temp/int8_eval.slurm model2
sbatch scripts/slurm_temp/int8_eval.slurm model3

# Dependent jobs (must wait on the upstream merge / backdoor train)
WAG=$(sbatch --parsable ANTI-BAD-CHALLENGE/classification-track/slurm_jobs/wag_merge.slurm 1)
sbatch --dependency=afterok:$WAG scripts/slurm_temp/wag_eval.slurm

BERT=$(sbatch --parsable scripts/slurm_temp/bert_backdoor_experiment.slurm)
sbatch --dependency=afterok:$BERT scripts/slurm_temp/bert_crow_defense.slurm
```

## Output paths

| Job | Output |
|-----|--------|
| `bert_backdoor_experiment.slurm` | `experiments/results/bert/{clean,poisoned_1,poisoned_2}/`, `experiments/results/bert/results.json` |
| `bert_crow_defense.slurm` | `experiments/results/bert_crow_defense/results.json` and per-run subdirs |
| `bert_mlm_defense_v2.slurm` | `experiments/results/bert_mlm_defense/results_v2.json` |
| `adaptive_attacker.slurm` | `experiments/results/adaptive_attacker/adaptive_attacker_report.{md,json}` |
| `wag_eval.slurm` | `experiments/results/wag/wag_merged_eval.csv` (cited in `ch05-results.tex`) |
| `int8_eval.slurm` | `experiments/results/int8/<model>_eval.csv` |

## Post-run checklist

After each job finishes:

1. Confirm the output file exists and the timestamp is post 2026-05-10.
2. Move the pre-2026-05-10 sibling (if any) into
   `experiments/_archive_pre_rerun_2026-05-10/<original-relative-path>`
   — do **not** delete; keep one full pre-rerun snapshot until
   submission is final.
3. Update the wiki page under
   `bachelor_submission_obsidian/wiki/files/...` for the source
   script (bump `updated:` date).
