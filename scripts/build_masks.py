#!/usr/bin/env python3
"""Parallel per-file mask construction; optional second-pass candidate scan.

Use on allocated compute nodes. Each worker opens its OWN read-only HDF5 handle.
No threads, source copies, nested BLAS pools, or data publishing. See docs/nersc_workflow.md.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
import json
import multiprocessing
import os
from pathlib import Path
import sys
import time

# Set before importing numpy in worker processes.
for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[name] = "1"

from ucd2x2.cli import add_cleaning_arguments, policy_from_args
from ucd2x2.core.hot_pixels import EventHitReader, HotPixelMask, CleaningPolicy, build_hot_mask, product_stem
from ucd2x2.core.event_scan import scan_events


def process_file(job):
    source, outdir, collection, block_rows, policy_dict, resume, scan = job
    started = time.monotonic()
    stem = product_stem(source,collection)
    mask_path = Path(outdir)/(stem+".hot_pixels.pkl")
    csv_path = Path(outdir)/(stem+".event_candidates.csv")
    policy = CleaningPolicy(**policy_dict)
    reused = False
    if resume and mask_path.is_file():
        mask = HotPixelMask.load(mask_path)
        with EventHitReader(source,collection,block_rows) as reader:
            mask.validate(reader)
        policy = policy_from_args(argparse.Namespace(**policy_dict), mask)
        # Raw statistics remain valid when only thresholds change.
        mask.payload["policy"] = asdict(policy)
        mask.policy = policy
        mask.save(mask_path)
        reused = True
    else:
        mask = build_hot_mask(source,mask_path,collection,policy,block_rows)
    if scan:
        scan_events(source,csv_path,mask,policy,collection,block_rows)
    return dict(source=source, mask=str(mask_path), candidates=str(csv_path) if scan else None,
                reused_statistics=reused, policy=asdict(policy), seconds=round(time.monotonic()-started,3), **mask.summary(policy))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*")
    parser.add_argument("--file-list", help="One completed FLOW path per line; # comments allowed")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--hit-type", choices=("prompt","final"),default="prompt")
    parser.add_argument("--block-rows", type=int,default=250_000)
    parser.add_argument("--scan", action="store_true",help="Also produce cleaned-charge CSVs (second read pass)")
    parser.add_argument("--resume", action="store_true",help="Validate/reuse completed statistics; rescan candidates if requested")
    parser.add_argument("--shards",type=int,default=1)
    parser.add_argument("--shard-index",type=int,default=0)
    add_cleaning_arguments(parser)
    args = parser.parse_args(argv)
    if args.workers < 1 or args.shards < 1 or not 0 <= args.shard_index < args.shards:
        parser.error("workers/shards must be positive and shard-index must be in [0,shards)")
    files = list(args.files)
    if args.file_list:
        for line in Path(args.file_list).read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                files.append(line)
    files = sorted(set(str(Path(path).expanduser().resolve()) for path in files))
    if not files:
        parser.error("Provide input files or --file-list")
    for path in files:
        if not Path(path).is_file():
            parser.error(f"Input file missing: {path}")
    files = files[args.shard_index::args.shards]
    output = Path(args.output_dir).expanduser().resolve()
    output.mkdir(parents=True,exist_ok=True)
    policy_from_args(args)  # Validate explicit thresholds before starting workers.
    overrides = {key:getattr(args,key) for key in asdict(CleaningPolicy()) if hasattr(args,key)}
    jobs = [(path,str(output),args.hit_type,args.block_rows,overrides,args.resume,args.scan) for path in files]
    print(f"Processing {len(jobs)} files with at most {args.workers} worker processes",flush=True)
    manifest = output/f"manifest.shard-{args.shard_index}.jsonl"
    failures = 0
    # Spawn avoids inheriting HDF5 handles. A single worker runs in-process for debugging.
    def record(stream, job, result=None, error=None):
        nonlocal failures
        if error is not None:
            failures += 1
            result = {"source":job[0],"error":str(error)}
        stream.write(json.dumps(result)+"\n");stream.flush()
        print(json.dumps(result),flush=True)
    with manifest.open("w",encoding="utf-8") as stream:
        if args.workers == 1:
            for job in jobs:
                try:
                    record(stream,job,process_file(job))
                except Exception as exc:
                    record(stream,job,error=exc)
        else:
            with ProcessPoolExecutor(max_workers=args.workers,mp_context=multiprocessing.get_context("spawn")) as pool:
                pending = {pool.submit(process_file,job):job for job in jobs}
                for future in as_completed(pending):
                    job = pending[future]
                    try:
                        record(stream,job,future.result())
                    except Exception as exc:
                        record(stream,job,error=exc)
    print(f"Manifest: {manifest}; failed files: {failures}",flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
