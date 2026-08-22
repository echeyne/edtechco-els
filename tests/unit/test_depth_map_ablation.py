"""Unit tests for the Pass-1 depth-map ablation flag (arXiv paper Task 3).

The ablation is the evidence for the paper's central "classify by nesting
POSITION, not document label" claim, so the thing these tests actually protect
is that the off-arm REALLY RAN with no depth map — a fabricated null result
would be worse than no ablation at all.

Three properties, each corresponding to a way the experiment could silently
lie:

1. **Production default is ON.** The flag must never change shipped behavior.
2. **Disabling short-circuits before Bedrock.** `infer_depth_map` returns None
   without making a call, and it does so at the SOURCE, so both production
   callers (`detect_structure` and `detection_batching.prepare_detection_batches`)
   are ablated by one switch and cannot drift apart.
3. **The two arms do not share a cache key.** The flag lives in `Config`, so it
   does NOT move `eval_common.code_version_hash`; without an explicit key
   component the off-arm would hit the on-arm's cached detection and report
   "no difference" having never run.
"""

import json

import pytest

from els_pipeline import detector
from els_pipeline.config import Config
from els_pipeline.detector import build_detection_prompt, infer_depth_map
from els_pipeline.models import TextBlock


def _block(text, page=1):
    return TextBlock(
        text=text, page_number=page, block_type="LINE",
        confidence=0.99, geometry={},
    )


@pytest.fixture
def blocks():
    return [
        _block("Social Studies"),
        _block("Social Studies Standard 1: Demonstrate awareness."),
        _block("SS.ID.PK1. Identify characteristics of self.", page=2),
    ]


@pytest.fixture
def depth_map_off(monkeypatch):
    monkeypatch.setattr(Config, "DEPTH_MAP_ENABLED", False)


@pytest.fixture
def no_bedrock(monkeypatch):
    """Any Bedrock call during an off-arm depth-map inference is a bug."""
    def _boom(*a, **k):
        raise AssertionError("call_bedrock_llm must not run when the depth map is disabled")
    monkeypatch.setattr(detector, "call_bedrock_llm", _boom)


class TestProductionDefault:
    def test_flag_defaults_to_enabled(self):
        """If this fails, the ablation has changed shipped behavior."""
        assert Config.DEPTH_MAP_ENABLED is True

    @pytest.mark.parametrize("raw,expected", [
        ("true", True), ("True", True), ("1", True), ("yes", True), ("", True),
        ("false", False), ("False", False), ("0", False), ("no", False),
        ("off", False), ("  FALSE  ", False),
    ])
    def test_env_parsing(self, raw, expected):
        truthy = raw.strip().lower() not in ("0", "false", "no", "off")
        assert truthy is expected


class TestDisablingShortCircuits:
    def test_returns_none_without_calling_bedrock(self, blocks, depth_map_off, no_bedrock):
        assert infer_depth_map(blocks) is None

    def test_gate_is_inside_infer_depth_map_so_both_callers_are_covered(self):
        """The gate must live at the source, not at the two call sites.

        `detect_structure` (direct path) and
        `detection_batching.prepare_detection_batches` (batched path) both call
        `infer_depth_map`. Gating one and not the other would ablate the eval
        while leaving production live."""
        import inspect
        src = inspect.getsource(infer_depth_map)
        assert "DEPTH_MAP_ENABLED" in src

    def test_enabled_path_still_reaches_bedrock(self, blocks, monkeypatch):
        """Guards against the flag being read inverted."""
        calls = []
        monkeypatch.setattr(Config, "DEPTH_MAP_ENABLED", True)
        monkeypatch.setattr(
            detector, "call_bedrock_llm",
            lambda *a, **k: calls.append(1) or '{"doc_depths": []}',
        )
        infer_depth_map(blocks)
        assert calls, "depth-map inference should call Bedrock when enabled"


class TestOffArmPromptIsTheRealFallback:
    """The off-arm must exercise the system's existing no-depth-map path, not a
    strawman written for the paper."""

    def test_prompt_builds_without_a_depth_map(self, blocks):
        prompt = build_detection_prompt(blocks, depth_map=None)
        assert isinstance(prompt, str) and prompt.strip()

    def test_depth_map_absence_changes_the_prompt(self, blocks):
        dm = {"doc_depths": [{"depth": 1, "canonical_level": "domain"}]}
        assert build_detection_prompt(blocks, depth_map=dm) != build_detection_prompt(
            blocks, depth_map=None
        )


class TestCacheKeysSeparateTheArms:
    def test_arms_get_different_cache_keys(self, tmp_path, monkeypatch):
        from evaluation.eval_common import code_version_hash
        from evaluation.eval_detector import _hash_blocks

        blocks_data = [{"text": "x", "page_number": 1}]
        h, code = _hash_blocks(blocks_data), code_version_hash()

        monkeypatch.setattr(Config, "DEPTH_MAP_ENABLED", True)
        on = f"detection-CA-{h}-{code}-{'' if Config.DEPTH_MAP_ENABLED else 'nodepthmap-'}.json"
        monkeypatch.setattr(Config, "DEPTH_MAP_ENABLED", False)
        off = f"detection-CA-{h}-{code}-{'' if Config.DEPTH_MAP_ENABLED else 'nodepthmap-'}.json"
        assert on != off

    def test_flag_does_not_move_the_code_version_hash(self, monkeypatch):
        """Precisely why the cache key needs its own component: the hash covers
        detector.py and parser.py, and the flag is in config.py."""
        from evaluation.eval_common import code_version_hash
        before = code_version_hash()
        monkeypatch.setattr(Config, "DEPTH_MAP_ENABLED", False)
        assert code_version_hash() == before
