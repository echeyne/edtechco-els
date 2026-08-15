"""Put the repo root on `sys.path` for the whole test suite.

`els_pipeline` is importable without this because `pip install -e ".[dev]"`
installs it, but `evaluation/` is not a distributed package — it is a plain
directory in the repo. Under pytest's default `prepend` import mode the path
inserted for a test file is the first ancestor directory WITHOUT an
`__init__.py`; `tests/unit/` has one, so pytest inserts `tests/` and the repo
root never lands on `sys.path`. That makes `import evaluation` fail under the
documented `pytest tests/ -v` while succeeding under `python -m pytest`, which
adds the cwd itself — a difference that silently depends on how you invoke the
runner.

Anchoring the path here keeps both invocations equivalent, so a test that
exercises the eval harness (e.g. `test_eval_description.py`) behaves the same
way in local runs and in CI.
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
