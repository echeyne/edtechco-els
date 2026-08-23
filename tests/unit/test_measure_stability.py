"""Regression tests for `eval_detector.measure_stability`.

The pre-2026-08-23 implementation reported a reassuring 0.000 disagreement in
the very same invocation whose graded output carried four malformed primary
keys. Three separate blind spots produced that, and each test below pins one
shut. If one of these fails, the instrument has gone blind again in the way its
docstring warns about.
"""
from pathlib import Path

import pytest

from evaluation import eval_detector as ed


def _el(title, level="indicator", code=None, description=None, age_band=None):
    return {"title": title, "level": level, "code": code,
            "description": description, "age_band": age_band}


@pytest.fixture
def stub_runs(monkeypatch):
    """Feed measure_stability a scripted sequence of probe-run outputs."""
    def _install(sequence):
        calls = {"n": 0}

        def fake(state, path, use_cache, cache_suffix):
            out = sequence[calls["n"] % len(sequence)]
            calls["n"] += 1
            return out
        monkeypatch.setattr(ed, "run_detector_cached", fake)
    return _install


def test_graded_run_is_included_as_an_observation(stub_runs):
    """Blind spot 1: the graded run was never in the comparison.

    Here every PROBE agrees with every other probe, and only the GRADED run
    differs. The old implementation compared probes to each other and reported
    0.000; the fix must see it.
    """
    stub_runs([[_el("Alpha", level="strand")]])
    graded = [_el("Alpha", level="sub_strand")]   # differs from all probes
    r = ed.measure_stability("XX", Path("x"), runs=3, graded_elements=graded)

    assert r["graded_run_included"] is True
    assert r["n_observations"] == 4              # 3 probes + graded
    assert r["n_titles_unstable"] == 1, "graded run's disagreement was missed"
    assert r["disagreements_by_dimension"]["level"] == 1
    assert r["observations_differing_from_graded_run"] == 3


def test_a_changed_code_counts_instead_of_vanishing(stub_runs):
    """Blind spot 2: identity was keyed on (code, title).

    An element whose CODE changed got a different key, failed the membership
    test, and was silently skipped -- so the instrument was blindest to the
    intermittent malformed-code defect it most needed to catch.
    """
    stub_runs([[_el("Alpha", code="AL.1.1")]])
    graded = [_el("Alpha", code="TCPHS")]        # the real KY defect shape
    r = ed.measure_stability("XX", Path("x"), runs=2, graded_elements=graded)

    assert r["n_titles_compared"] == 1, "element dropped out of the comparison"
    assert r["disagreements_by_dimension"]["code"] == 1
    assert r["disagreement_rate"] > 0


def test_an_element_missing_from_some_runs_counts(stub_runs):
    """Blind spot 3: absence was invisible, showing up only in size stdev."""
    stub_runs([[_el("Alpha"), _el("Beta")]])
    graded = [_el("Alpha")]                       # Beta absent from graded
    r = ed.measure_stability("XX", Path("x"), runs=2, graded_elements=graded)

    assert r["disagreements_by_dimension"]["presence_or_multiplicity"] == 1
    assert any(u["dimension"] == "presence" for u in r["unstable_examples"])


def test_identical_runs_report_zero_but_carry_the_denominator(stub_runs):
    """A clean result must still say how many observations produced it.

    'rate 0.000' alone is what made the original result misleading."""
    stub_runs([[_el("Alpha"), _el("Beta")]])
    graded = [_el("Alpha"), _el("Beta")]
    r = ed.measure_stability("XX", Path("x"), runs=4, graded_elements=graded)

    assert r["disagreement_rate"] == 0.0
    assert r["n_titles_compared"] == 2
    assert r["n_observations"] == 5
    assert r["observations_differing_from_graded_run"] == 0
    assert "NOT evidence of determinism" in r["interpretation_warning"]


def test_multiplicity_change_counts(stub_runs):
    """A title detected once in one run and twice in another is instability."""
    stub_runs([[_el("Alpha"), _el("Alpha")]])
    graded = [_el("Alpha")]
    r = ed.measure_stability("XX", Path("x"), runs=2, graded_elements=graded)

    assert r["disagreements_by_dimension"]["presence_or_multiplicity"] == 1
    assert any(u["dimension"] == "multiplicity" for u in r["unstable_examples"])


def test_description_appearing_and_vanishing_counts(stub_runs):
    """The AZ defect shape: an indicator's description intermittently null."""
    stub_runs([[_el("Alpha", description="some prose")]])
    graded = [_el("Alpha", description=None)]
    r = ed.measure_stability("XX", Path("x"), runs=2, graded_elements=graded)

    assert r["disagreements_by_dimension"]["description_present"] == 1


def test_works_without_a_graded_run_but_says_so(stub_runs):
    """Back-compat: callers that pass no graded run still get a result, and the
    output records that the graded run was excluded rather than implying it
    was included."""
    stub_runs([[_el("Alpha")]])
    r = ed.measure_stability("XX", Path("x"), runs=2)

    assert r["graded_run_included"] is False
    assert r["n_observations"] == 2
    assert r["observations_differing_from_graded_run"] is None


def test_rate_never_exceeds_one_when_a_title_moves_in_many_dimensions(stub_runs):
    """A title unstable in level AND code AND description is ONE unstable title.

    Summing the per-dimension counters to form the rate produced 2.000 against a
    denominator of 2 -- caught by rendering a report, not by the unit tests that
    existed at the time. The per-dimension breakdown may still sum higher than
    the distinct-title count; that is intended and is why the two are reported
    separately.
    """
    stub_runs([[_el("Alpha", level="strand", code="A.1", description="prose")]])
    graded = [_el("Alpha", level="sub_strand", code="TCPHS", description=None)]
    r = ed.measure_stability("XX", Path("x"), runs=2, graded_elements=graded)

    assert r["n_titles_compared"] == 1
    assert r["n_titles_unstable"] == 1
    assert 0.0 <= r["disagreement_rate"] <= 1.0
    assert r["disagreement_rate"] == 1.0
    # three separate dimensions moved on that one title
    assert r["n_dimension_disagreements"] == 3


def test_report_renders_without_error_and_bounds_the_rate(stub_runs):
    """render_report is a real consumer; exercise it so a formatting change to
    the stability block cannot ship untested."""
    from evaluation.eval_detector import StateReport, render_report
    stub_runs([[_el("Alpha", level="strand", code="A.1")]])
    graded = [_el("Alpha", level="sub_strand", code="TCPHS"), _el("Beta")]
    d = ed.measure_stability("XX", Path("x"), runs=2, graded_elements=graded)

    rep = StateReport(state="XX")
    rep.stability_runs = 2
    rep.stability_detail = d
    rep.stability_disagreement_rate = d["disagreement_rate"]
    rep.stability_size_stdev = d["size_stdev"]
    txt = render_report(rep)

    assert "observations:" in txt
    assert "the graded run" in txt
    assert 0.0 <= d["disagreement_rate"] <= 1.0
