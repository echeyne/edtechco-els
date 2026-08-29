"""Decisive A/B: run NV's detector at 14374dba with the OLD stride sampler.

Everything else is held constant — same code, same prompts, same extraction,
same grader, no cache. The ONLY difference from the recorded 46/46 run is which
blocks Pass-1 sees. If this returns 44/46 on NV-DOM-02/03, the sampler is the
cause and the rule-4 prompt change (b35b9666) is exonerated.
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import els_pipeline.detector as D
from evaluation.eval_detector import evaluate_state

def old_sampler(blocks, target_tokens=D.DEPTH_MAP_SAMPLE_TOKENS):
    if not blocks: return []
    total = sum(D.estimate_tokens(b.text) for b in blocks)
    if total <= target_tokens: return blocks
    stride = max(1, total // target_tokens)
    out, tok = [], 0
    for i, b in enumerate(blocks):
        if i % stride == 0:
            out.append(b); tok += D.estimate_tokens(b.text)
            if tok >= target_tokens: break
    return out

D._sample_blocks_for_depth_map = old_sampler
print("PATCHED: Pass-1 now uses the OLD stride sampler")

rep, _ = evaluate_state(
    state="NV",
    extraction_path=Path("outputs/08-26-26-2/NV-extraction.json"),
    golden_path=Path("evaluation/ground_truth_detector/NV.json"),
    use_cache=False,
    stability_runs=0,
)
out = {
    "arm": "OLD stride sampler, everything else at 14374dba",
    "n_detected": rep.n_detected, "matched": rep.matched, "n_golden": rep.n_golden,
    "recall": rep.recall, "precision": rep.precision,
    "code_matches": rep.code_matches, "code_total": rep.code_total,
    "code_accuracy": rep.code_accuracy,
    "code_mismatches": rep.code_mismatches,
    "description_matches": rep.description_matches, "description_total": rep.description_total,
}
Path("paper/results/task2_20260826/nv_oldsampler_arm.json").write_text(json.dumps(out, indent=2))
print(json.dumps({k: v for k, v in out.items() if k != "code_mismatches"}, indent=1))
print("code_mismatches:", json.dumps(out["code_mismatches"], indent=1))
