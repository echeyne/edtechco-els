"""Whole-document single-prompt detection arm (arXiv paper Task 10).

The comparison this exists for
------------------------------
The paper argues for a two-pass, chunked, deterministically-repaired pipeline.
The obvious question -- the one every reviewer asks -- is what you lose by not
bothering: hand the model the entire document in one prompt and read the JSON
back. The rule-based baseline answers a different question (what a regex
extractor cannot do); it does not answer "why not just prompt it".

This arm is that alternative, built to be as strong as it honestly can be:

  * **one Bedrock call** over the whole document, no chunking and therefore no
    chunk-overlap, no cross-chunk merge, no ``_dedup_elements``;
  * **no Pass-1 depth map** -- ``build_detection_prompt`` has always carried a
    ``depth_map=None`` branch, which tells the model to classify by nesting
    position and infer the levels itself;
  * **no deterministic repairs** -- no ``_resolve_code``, no
    ``_canonicalize_code``, no ``_is_title_grounded``, no ``_strip_label_prefix``,
    no age-band canonicalization, no cross-chunk code normalization. Whatever
    the model emits is what gets graded.

Everything else is held constant on purpose. It is the SAME detection prompt
body, the SAME model, the SAME temperature, the SAME extractions and the SAME
grader as the full method -- so a difference in score is attributable to the
architecture rather than to prompt or model differences. Only JSON extraction
survives from the pipeline, because a response that cannot be parsed at all
cannot be graded at all, and that is plumbing rather than a repair.

⚠️ Cost note. This arm calls the detector model (Opus by default) once per
state, on documents of 3.7K-7.9K tokens. That is far cheaper than a full
detector arm, but it is not free and it is NOT cached across code edits: the
cache key carries ``code_version_hash``, so editing ``detector.py`` or
``parser.py`` re-runs every state. See CLAUDE.md's cost-gate note.

⚠️ What a good score here would mean. If this arm matches the full method, the
honest reading is that the architecture is unnecessary AT THE SUBSET TIER --
where every document fits in one prompt. It would say nothing about the trimmed
or full tiers, where a document does not fit and chunking is not optional. That
distinction has to travel with any number this file produces.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from els_pipeline.config import Config  # noqa: E402
from els_pipeline.detector import (  # noqa: E402
    _extract_json_from_response,
    build_detection_prompt,
    call_bedrock_llm,
    estimate_tokens,
)
from els_pipeline.models import TextBlock  # noqa: E402
from evaluation.eval_common import _hash_blocks, as_plain_json, code_version_hash  # noqa: E402

logger = logging.getLogger(__name__)

CACHE_DIR = REPO / "evaluation" / ".cache"

# Fields the grader reads. Anything else the model emits is carried through
# untouched -- this arm's whole point is that nothing is normalized.
_GRADED_FIELDS = ("level", "code", "title", "description", "age_band",
                  "source_page", "source_text", "confidence")


def _raw_elements(response_text: str) -> List[dict]:
    """Parse the response into plain dicts, applying NO repairs.

    Deliberately does not go through ``detector.parse_llm_response``: that
    function is where ``_resolve_code``, ``_canonicalize_code``,
    ``_is_title_grounded`` and ``_strip_label_prefix`` run, and this arm exists
    to measure what happens without them. It also does not build
    ``DetectedElement``, because pydantic validation would drop a row the model
    got wrong -- and a dropped row is exactly the kind of failure this arm
    should be able to show.
    """
    payload = json.loads(_extract_json_from_response(response_text))
    if isinstance(payload, dict):
        payload = payload.get("elements", payload.get("structural_elements", []))
    out: List[dict] = []
    for item in payload or []:
        if not isinstance(item, dict):
            continue
        row = {k: item.get(k) for k in _GRADED_FIELDS}
        # `level` is the one field the grader cannot work without; a row that
        # omits it is kept (so it counts against precision) but normalized to
        # a string so the grader's `.strip()` does not raise.
        row["level"] = "" if row["level"] is None else str(row["level"])
        if row.get("code") is not None:
            row["code"] = str(row["code"])
        out.append(row)
    return out


def run_whole_document(
    state: str,
    extraction_path: Path,
    use_cache: bool = True,
) -> List[dict]:
    """``detect_fn``-compatible runner: one prompt, one call, no repairs."""
    extraction = json.loads(Path(extraction_path).read_text())
    blocks_data = extraction.get("blocks", [])
    cache_key = (
        f"wholedoc-{state}-{_hash_blocks(blocks_data)}-{code_version_hash()}.json"
    )
    cache_path = CACHE_DIR / cache_key
    if use_cache and cache_path.exists():
        logger.info(f"  [cache hit] {cache_path.name}")
        return json.loads(cache_path.read_text())

    blocks = [TextBlock(**b) for b in blocks_data]
    prompt = build_detection_prompt(blocks, depth_map=None)
    logger.info(
        f"  [whole-document] {state}: {len(blocks)} blocks, one call, "
        f"~{estimate_tokens(prompt)} prompt tokens, "
        f"model={Config.BEDROCK_DETECTOR_LLM_MODEL_ID}"
    )
    response_text = call_bedrock_llm(prompt)
    try:
        elements = _raw_elements(response_text)
    except Exception as exc:  # a parse failure IS a result for this arm
        logger.error(f"  [whole-document] {state}: response did not parse: {exc}")
        elements = []
        cache_path.with_suffix(".unparsed.txt").write_text(response_text)
    logger.info(f"  [whole-document] {state}: {len(elements)} elements")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(elements, indent=2, ensure_ascii=False))
    return as_plain_json(elements)
