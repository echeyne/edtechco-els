"""Rule-based baselines for the arXiv paper's comparison tables.

⚠️ THROWAWAY BY DESIGN. Everything in this package is a deliberately
rule-driven contrast to the LLM-first pipeline, built only so the paper can
quantify the LLM lift with the same suite and the same goldens. None of it is
imported by ``src/els_pipeline/`` and none of it may be moved there — see the
"Design direction" section of CLAUDE.md, which makes per-state regexes in
``detector.py`` / ``parser.py`` a regression in disguise.
"""
