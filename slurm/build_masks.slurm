#!/bin/bash
#SBATCH --job-name=ucd2x2-masks
#SBATCH --constraint=cpu
#SBATCH --qos=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --time=01:00:00
#SBATCH --licenses=cfs,scratch
#SBATCH --output=ucd2x2-masks-%A_%a.log
set -euo pipefail

# Activate your installed environment BEFORE sbatch; no conda setup in workers.
# Pass --account=YOUR_ACCOUNT on sbatch. Defaults are 8 processes / 16 hyperthreads.
: "${UCD2X2_PYTHON:?Export UCD2X2_PYTHON=$(command -v python) before submitting}"
: "${UCD2X2_REPO:?Export UCD2X2_REPO=$PWD from the repository root}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
WORKERS=${WORKERS:-8}
SHARDS=${SLURM_ARRAY_TASK_COUNT:-1}
SHARD=${SLURM_ARRAY_TASK_ID:-0}
# Arrays must be consecutive, zero-based: --array=0-3%2, for example.
if [[ ${SLURM_ARRAY_TASK_MIN:-0} != 0 || ${SLURM_ARRAY_TASK_STEP:-1} != 1 ]]; then
    echo "Use a zero-based contiguous job array (e.g. --array=0-3%2)" >&2
    exit 2
fi
cd "$UCD2X2_REPO"
srun --ntasks=1 --cpu-bind=cores "$UCD2X2_PYTHON" scripts/build_masks.py \
    --workers "$WORKERS" --shards "$SHARDS" --shard-index "$SHARD" "$@"
