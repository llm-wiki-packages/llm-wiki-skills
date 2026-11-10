"""A stand-in for the plugin's `llm_wiki_browser`, which `llm-wiki-ops run` puts on a unit script's path: here on
this process's path and on every child's PYTHONPATH, as the run's would be."""

from __future__ import annotations

import sys

import pytest

# `child_env` as the plugin's launcher rules it: the environment, its own directory first on PYTHONPATH.
STAND_IN = '''import os


def child_env(environ=None):
    env = dict(os.environ if environ is None else environ)
    here = os.path.dirname(os.path.abspath(__file__))
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [here, env.get("PYTHONPATH")]))
    return env
'''


@pytest.fixture(autouse=True)
def launcher(tmp_path_factory, monkeypatch):
    """The stand-in's directory."""
    lib = tmp_path_factory.mktemp("unitlib")
    (lib / "llm_wiki_browser.py").write_text(STAND_IN)
    monkeypatch.syspath_prepend(str(lib))
    monkeypatch.delitem(sys.modules, "llm_wiki_browser", raising=False)
    monkeypatch.setenv("PYTHONPATH", str(lib))
    return lib
