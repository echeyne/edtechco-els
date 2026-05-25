# Eval run snapshots

Each subdirectory here is one invocation of `python -m evaluation.eval_suite`.
Runs are written automatically (skip with `--no-persist`).

Layout:
```
20260503-153012-a3b9c1d/
  manifest.json          # timestamp, git sha, model ids, prompt hashes, args, summary
  report.json            # full per-state report (same shape as --report-json)
  console.txt            # the human-readable text printed at the end of the run
  states/
    AZ.detected.json     # raw detector output for AZ
    AZ.depth_map.json    # depth map inferred for AZ
    CA.detected.json
    ...
```

The dir name is `YYYYMMDD-HHMMSS-<git-sha>[-dirty][-<label>]`.
Add `--label fewshot-v2` and `--notes "tightened indicator rules"` to make
runs easier to identify later.

Useful commands:
```sh
python -m evaluation.eval_suite --list-runs
python -m evaluation.eval_suite --compare latest <older-run-id-or-prefix>
```

The `prompt_hashes` field in `manifest.json` is what tells you whether two
runs used the same prompt — when those hashes change, the score change is
attributable to the prompt edit (rather than to a model change or
non-determinism).
