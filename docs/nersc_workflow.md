# NERSC: masks → candidates → a served event browser

The workflow reads the original **completed, reconstructed FLOW HDF5** in place.
It writes separate pixel-statistics PKLs and event-summary CSVs. No 14 GB copy,
no hit deletion, no HDF5 reference rewriting, and no notebook monkeypatch are required.
“Raw” here means unfiltered calibrated FLOW hits, **not** a PACMAN packet file.

## 1. Install once

Activate your existing Python environment, enter the repository, and run:

```bash
python -m pip install -e .
ucd2x2 --help
```

Python 3.11 is a useful environment choice. All dependencies are already declared
by the project. The batch worker does not import Panel, Plotly, or scikit-learn.
Mask construction and candidate scans belong on allocated **compute nodes**.
A Jupyter terminal is sufficient for launching the lightweight interactive viewer.

For a fresh environment on NERSC:

```bash
module load python
conda create -n ucd2x2 python=3.11 pip -y
conda activate ucd2x2
python -m pip install -e .
```

## 2. Prepare a list of completed FLOW files

From the repository root, in the activated environment:

```bash
FILE="/global/cfs/cdirs/YOUR_PROJECT/path/to/run.FLOW.hdf5"
OUT="${PSCRATCH:?PSCRATCH is not set}/ucd2x2-products"
mkdir -p "$OUT"
printf '%s\n' "$FILE" > flow_files.txt
```

For many files, replace `flow_files.txt` with one **absolute** path per line.
Blank lines and lines beginning with `#` are ignored. Paths containing spaces are
supported. Do not include files still being written or raw packet HDF5s.

Scratch is suitable for disposable products, but not permanent storage. Keep
validated masks/candidates in an appropriate shared project directory on CFS.
Nothing needs to be written beside the source HDF5 itself.

## 3. Submit mask construction and candidate scans to a compute node

```bash
export UCD2X2_REPO="$PWD"
export UCD2X2_PYTHON="$(python -c 'import sys; print(sys.executable)')"
export WORKERS=8

sbatch --account=YOUR_NERSC_ACCOUNT slurm/build_masks.slurm \
    --file-list "$PWD/flow_files.txt" \
    --output-dir "$OUT" \
    --scan --resume
```

The supplied job requests one shared CPU node allocation, 16 Slurm CPUs
(hyperthreads), and one hour. It launches eight independent per-file processes
within that allocation. Change `--time`/`--qos` on `sbatch` as appropriate for your
account. No batch job is submitted automatically by the Python script.

`--scan` performs a **second pass** after file-wide statistics are known, writing
cleaned-charge candidate summaries. Omit it for masks only. The source is opened
read-only in each worker. All failures are reported in the manifest, and any
failed file makes the job exit nonzero rather than pretending everything succeeded.

Monitor with:

```bash
squeue -u "$USER"
ls -lh "$OUT"
```

Logs are `ucd2x2-masks-<job>_<array-task>.log` in the submission directory.

### More files / more nodes

A bounded job array partitions the input list without processing a file twice:

```bash
sbatch --account=YOUR_NERSC_ACCOUNT --array=0-3%2 \
    slurm/build_masks.slurm \
    --file-list "$PWD/flow_files.txt" --output-dir "$OUT" --scan --resume
```

This creates four shards, with at most two active simultaneously. Arrays must
start at zero and be contiguous. With eight workers per shard, this example has
at most 16 concurrent file readers. Increase concurrency cautiously: CFS bandwidth
and compression may dominate, so more processes need not make it faster.

Inside an existing allocation, the equivalent direct command is:

```bash
python scripts/build_masks.py --file-list flow_files.txt \
    --output-dir "$OUT" --workers 8 --scan --resume
```

### Outputs and resume

Each file has a deterministic, collision-resistant product stem:

```text
<input-basename>.<absolute-path-hash>.prompt.hot_pixels.pkl
<input-basename>.<absolute-path-hash>.prompt.event_candidates.csv
<input-basename>.<absolute-path-hash>.prompt.event_candidates.csv.json
manifest.shard-0.jsonl
```

The manifest maps input paths to their outputs and records timing/counts/errors.
Different input directories with the same basename do not collide.
`--resume` validates and reuses completed statistics. Explicit threshold overrides
retune those statistics without rebuilding them. With `--scan`, candidate CSVs
are regenerated under the effective policy. Old notebook PKLs lack the required
statistics/provenance: rebuild them rather than loading them as new-format masks.

To obtain predictable paths for the single file above:

```bash
STEM="$(python -c 'from ucd2x2.core.hot_pixels import product_stem; import sys; print(product_stem(sys.argv[1]))' "$FILE")"
MASK="$OUT/$STEM.hot_pixels.pkl"
CSV="$OUT/$STEM.event_candidates.csv"
ls -lh "$MASK" "$CSV" "$CSV.json"
```

## 4. Launch the browser from the NERSC Jupyter terminal

Open NERSC Jupyter, start your server, and open a **Terminal inside that server**.
Activate the same environment. Define `FILE`, `MASK`, and `CSV` there (shell
variables from another SSH/Jupyter terminal do not automatically carry over).
Then:

```bash
ucd2x2 event-display "$FILE" \
    --hot-mask "$MASK" --candidates "$CSV" \
    --jupyter --port 5006 --no-show
```

The command prints a URL such as:

```text
https://jupyter.nersc.gov/user/<your-server>/proxy/5006/clean_panel
```

Open the **exact printed URL** in your browser. This is a running Panel server,
not an exported HTML file and not an inline notebook renderer. Keep the terminal
process running; Ctrl-C stops it. A different port, e.g. `--port 5007`, is allowed.

The launcher sets loopback binding, the WebSocket origin, and the stripped-path
proxy root. It never opens the server on all network interfaces. This is your
personal authenticated Jupyter session, not a public collaboration service.
Proxy availability and the final authenticated NERSC route must be verified in
your actual session; they cannot be verified by unit tests on another machine.

Before launching, `--dry-run` prints the generated command/URL without starting
Panel. If Panel reports an unknown `--root-path` option, update Panel in the
activated environment. A 404 or WebSocket error requires checking the printed
prefix and that the process is running on the **same host as the Jupyter server**.
Do not substitute a random SSH login-node process for the Jupyter-terminal process.

### Browser controls

- Raw/clean comparison, per-event multiplicity and file-wide occupancy thresholds.
- 3D, 2D and charge/drift distributions, with the original module geometry.
- Direct event index navigation and previous/next high-charge candidates.
- Candidate sorting by total cleaned Q, or diagnostic Q inside nominal geometry.
- A detector-frame toggle that locks both the 3D scene and all three spatial 2D
  projections to the nominal detector envelope. Extreme reconstructed coordinates
  remain in statistics/scores but cannot stretch the displayed axes by metres.
- Browser-side **▶ Spin / ⏸ Pause** controls above the 3D figure. The speed slider
  sets seconds per 360-degree rotation. The animation changes only the camera;
  event data are not resent or duplicated in every animation frame.
- Plotly's normal modebar camera button can save a PNG at any paused orientation.
  For a short movie, run the 360-degree spin and screen-record the browser; no
  server-side video encoder is required.
- An **Export current event HTML** card writes a standalone interactive page with
  the 3D view (including spin controls), 2D projections, distributions and event
  metadata. It defaults to `$PSCRATCH/ucd2x2-event-exports` when `$PSCRATCH`
  exists, otherwise `outputs/event_exports`.

The exported HTML embeds Plotly and the plotted event data, so treat it as a data
product: do not copy it to a public web directory unless that event is approved
for public release.

The tile-5/IOG-6 highlight is removed from both old and new plotting paths.
Nonpositive charges remain in the arrays and charge sums; they are displayed at
the bottom of the positive-Q color scale rather than stretching it down to −12.

The cleaned browser focuses on real-data cleaning and candidate inspection. The
original full Stage-2/truth-overlay editor remains available through the ordinary
command without cleaning flags:

```bash
ucd2x2 event-display tests/sample_data.hdf5
```

For cleaning without a global PKL, explicitly use `--clean`. A mask automatically
selects the new browser. `--hit-type final` requires a separately built final-hit
mask and CSV; switching collections never silently bypasses the mask.

## 5. What the filters mean

The default policy is exactly:

```text
local:  remove ALL hits from a hardware pixel with >3 hits in this event
file:   remove a pixel with total_hits > N_events in this file
```

The pixel ID is `(io_group, io_channel, chip_id, channel_id)`, packed losslessly
into 64 bits after range/type checks. `io_channel` is a route, not a tile number.
No drift coordinate is used as identity. Routing aliases are not merged without
a validated hardware/geometry mapping. Missing hardware fields are an error;
there is no silent `(y,z)` fallback.

The file-wide denominator includes all `charge/events` rows, including empty
events. Counts use hits reached through the **event→hit reference table**, not
unassociated rows elsewhere in the hit dataset. `ref_region` indexes reference
rows; it is not generally a direct calibrated-hit slice. The new reader tests
non-contiguous, shuffled, sparse and empty mappings.

Local multiplicities are counted on the original event, before other removals.
The report partitions rejected hits as invalid, disabled, global, then local, so
counters do not double-count hits rejected for multiple reasons. `is_disabled`
hits and nonfinite charge/coordinates are removed in the cleaned view. Negative
finite charge is not a rejection criterion. All original hit arrays remain intact.

The PKL saves, for each pixel: total hits, events with a hit, events with ≥2/≥3/≥4
hits, and the largest per-event multiplicity. Thus an additional persistence cut
can be explored without rescanning the file to rebuild the statistics:

```bash
# On a compute node: reuse mask statistics, rescan event scores with a new policy.
ucd2x2 scan-events "$FILE" --hot-mask "$MASK" \
    --max-event-fraction 0.10 -o "$OUT/retuned.csv"

# Inside the Jupyter terminal: use the SAME override.
ucd2x2 event-display "$FILE" --hot-mask "$MASK" \
    --max-event-fraction 0.10 --candidates "$OUT/retuned.csv" \
    --jupyter --port 5006 --no-show
```

Here `0.10` means **more than** 10% of events; it is an exploratory threshold,
not a validated default. The persistence cut is off by default. Globally frequent
activity can be genuine under some running conditions, and a strict local cut
can also remove real multi-hit signal. Validate on representative control data.

`--event-max-hits-per-pixel 0` disables the local cut. `--global-mean-max none`
disables the mean-occupancy cut. Threshold changes in the browser immediately
change the view, but disable cached candidate navigation until the policy matches
again or a matching candidate scan is loaded.

**Only load trusted PKLs.** Python pickle is executable, not a safe interchange
format for arbitrary downloads. Masks record resolved source path, size, mtime,
hit collection, event/hit counts and dtype; mismatches fail loudly. The source
must be complete and unchanged while processing. These checks are not a full
cryptographic hash of the entire multi-GB input.

## 6. Candidate scores are not yet a physics selection

The CSV retains signed `total_Q`, `positive_Q`, hit/pixel counts, spatial spans,
largest-hit charge fraction, and native `ts_pps` spans. Q is in the input file's
units; no ADC-to-electron or charge-to-energy conversion is guessed.

It also records `n_in_nominal_volume`, `nominal_volume_fraction` and
`Q_in_nominal_volume`, using the existing module boxes with a 1 cm tolerance.
These are **stored-coordinate diagnostics**, not a timing correction and not an
automatic extra hit cut. Out-of-volume x coordinates can indicate an event-window,
t0 or drift-coordinate problem; simply tightening a hot-pixel mask does not fix
that. Long windows can collect more residual noise and therefore larger ΣQ.
Inspect both time spans and geometry before calling a high-Q entry a real cosmic.
Do not use a few selected events as a production file-wide occupancy calibration.

## 7. Performance and validation

The implementation uses bounded hit/reference read-ahead, vectorized per-event
pixel counting, batched NumPy reductions, and independent processes across files.
It does not load the whole HDF5 or create a Python tuple/dictionary entry per hit.
The candidate pass reads the required charge datasets, not unrelated light/truth
data. Peak memory still depends on the largest event and the number of pixels.

Run the complete project suite after installing the repository:

```bash
pytest -q
python -c "import ucd2x2.display.app_panel"
```

New tests cover reference correctness, empty events, exact threshold boundaries,
read-only behavior, provenance, scanner/browser policy agreement, CLI proxy
construction, Q color behavior, and removal of the tile highlight. Live Panel
rendering, authenticated NERSC proxy access, and production-scale CFS throughput
require an actual NERSC run; small synthetic tests are not substitutes for those.

Official references:
- https://docs.nersc.gov/services/jupyter/reference/
- https://docs.nersc.gov/jobs/examples/
- https://panel.holoviz.org/how_to/server/proxy.html
