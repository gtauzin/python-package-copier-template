"""Tests for the References Griffe extension (`docs_build/_references.py`).

The extension normalizes a numpydoc "References" section into a markdown ordered
list at Griffe collection time, before mkdocstrings renders the docstring. Griffe
hands the section to mkdocstrings as raw text, so without this pass RST citation
syntax (`.. [1]`) renders literally and a bare-bracket block collapses into one
run-on paragraph. These tests drive the extension through a real Griffe load and
assert on the rewritten docstring; one test builds the docs and checks that a
References section reaches the page as a list with no RST artifacts.
"""

import importlib.util
import logging
import sys

import pytest
from _build_layout import BUILD_DIR, site_path

_MODELS = '''\
"""Models."""


class RstStyle:
    """RST style.

    References
    ----------
    .. [1] Akiba, T. (2019). Optuna. <https://doi.org/10.1145/3292500.3330701>
    """


class BareBracket:
    """Bare bracket.

    References
    ----------
    [1] Hyndman, R.J. (2021). "Forecasting: principles and
        practice," 3rd edition.
    """


class MultiEntry:
    """Multi entry.

    References
    ----------
    [1] First reference.

    [2] Second reference.
    """


class MarkdownList:
    """Markdown list.

    References
    ----------
    1. [NumPy guide](https://numpydoc.readthedocs.io/):
        the convention used here.
    2. [PEP 498](https://peps.python.org/pep-0498/):
        f-strings.
    """


class BodyCite:
    """Body cite.

    Uses the method [1]_ described below.

    References
    ----------
    [1] Some Author (2020).
    """


class FollowedBySection:
    """Followed by section.

    References
    ----------
    [1] Only reference.

    Examples
    --------
    >>> FollowedBySection()
    """


class ResidualRst:
    """Residual RST.

    References
    ----------
    [1] An entry embedding a stray .. [note] directive mid-text.
    """


class FlushLeft:
    """Flush left.

    References
    ----------
    [1] Akiba, T. (2019). Optuna: A Next-generation Framework.
    In Proceedings of the 25th ACM SIGKDD International Conference.
    https://doi.org/10.1145/3292500.3330701
    """
'''


def _load_extension(project_dir, suffix):
    """Load the generated `_references` extension under a unique module name."""
    sys.modules.pop("_references", None)
    spec = importlib.util.spec_from_file_location(
        f"generated_references_{suffix}", project_dir / BUILD_DIR / "_references.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rewritten(project_dir, extension_module, package_name, obj_path):
    """Load the package through Griffe with the extension; return obj's docstring."""
    import griffe

    extensions = griffe.load_extensions(extension_module.ReferencesExtension())
    loader = griffe.GriffeLoader(search_paths=[str(project_dir / "src")], extensions=extensions)
    package = loader.load(package_name)
    return package[obj_path].docstring.value


@pytest.fixture
def rewritten(copie):
    """Render a project, drop in a models module, return a per-object rewriter."""
    result = copie.copy(extra_answers={"include_examples": False})
    assert result.exit_code == 0
    project_dir = result.project_dir
    (project_dir / "src" / "test_project" / "models.py").write_text(_MODELS, encoding="utf-8")
    ext = _load_extension(project_dir, "references")

    def _get(obj_path):
        return _rewritten(project_dir, ext, "test_project", obj_path)

    return _get


def test_rst_citation_definition_becomes_a_list_item(rewritten):
    """`.. [1] ...` is normalized to `1. ...` with no RST marker left behind."""
    out = rewritten("models.RstStyle")
    assert "1. Akiba, T. (2019). Optuna." in out
    assert ".. [" not in out
    assert "[1]" not in out


def test_bare_bracket_entry_joins_its_continuation(rewritten):
    """`[1] ...` with an indented continuation becomes one list item, not a code block."""
    out = rewritten("models.BareBracket")
    assert '1. Hyndman, R.J. (2021). "Forecasting: principles and practice," 3rd edition.' in out
    assert "[1] Hyndman" not in out


def test_multiple_entries_become_distinct_list_items(rewritten):
    """Blank-line-separated entries each get their own number, not one paragraph."""
    out = rewritten("models.MultiEntry")
    assert "1. First reference." in out
    assert "2. Second reference." in out
    # The bracket markers are gone and the two references are not run together.
    assert "[1]" not in out
    assert "[2]" not in out


def test_existing_markdown_list_is_preserved(rewritten):
    """An already-markdown list keeps its links and is not double-numbered."""
    out = rewritten("models.MarkdownList")
    assert "1. [NumPy guide](https://numpydoc.readthedocs.io/):" in out
    assert "2. [PEP 498](https://peps.python.org/pep-0498/):" in out
    assert "1. 1." not in out
    assert "](https://numpydoc.readthedocs.io/)" in out  # link intact


def test_body_citation_reference_loses_its_underscore(rewritten):
    """An inline `[1]_` reference in prose becomes plain `[1]`."""
    out = rewritten("models.BodyCite")
    assert "the method [1] described below." in out
    assert "[1]_" not in out


def test_flush_left_multiline_citation_is_one_item(rewritten):
    """A bare-bracket citation whose continuations are NOT indented stays one item.

    numpydoc recommends indenting a wrapped continuation, but many docstrings write
    it flush with the `[1]` marker. Splitting entries by indentation turned such a
    citation into one list item per physical line; splitting on the citation marker
    folds it back into a single entry.
    """
    out = rewritten("models.FlushLeft")
    assert (
        "1. Akiba, T. (2019). Optuna: A Next-generation Framework. "
        "In Proceedings of the 25th ACM SIGKDD International Conference. "
        "https://doi.org/10.1145/3292500.3330701" in out
    )
    assert "2." not in out  # not split into multiple numbered items


def test_section_boundary_stops_at_the_next_section(rewritten):
    """A section after References is preserved, not swallowed into the block."""
    out = rewritten("models.FollowedBySection")
    assert "1. Only reference." in out
    assert "Examples" in out
    assert ">>> FollowedBySection()" in out


def test_unnormalizable_rst_warns(rewritten, caplog):
    """RST citation syntax that survives normalization warns (fatal under --strict).

    A stray `.. [` inside an entry's text is not a leading marker the strip
    reaches, so it would render literally. The extension logs under the ``mkdocs``
    logger tree, which mkdocs counts and a ``--strict`` build treats as an error.
    """
    with caplog.at_level(logging.WARNING, logger="mkdocs.hooks"):
        out = rewritten("models.ResidualRst")
    assert "1. An entry embedding a stray" in out
    assert any("references:" in r.message and "ResidualRst" in r.message for r in caplog.records)


@pytest.mark.integration
@pytest.mark.slow
def test_references_render_as_a_list_end_to_end(copie):
    """A full build renders a References section as a list with no RST leak.

    The unit tests prove the rewrite; this proves it reaches the rendered page.
    The sample package's ``Greeter`` ships a References section, so its generated
    page is the one to inspect.
    """
    import subprocess

    result = copie.copy(extra_answers={"include_examples": False})
    assert result.exit_code == 0
    project_dir = result.project_dir

    build = subprocess.run(
        ["uvx", "nox", "-s", "build_docs"],
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert build.returncode == 0, f"build failed:\n{build.stdout}\n{build.stderr}"

    page = site_path(project_dir) / "pages" / "api" / "generated" / "test_project.hello.Greeter" / "index.html"
    assert page.is_file(), "generated page for Greeter not found"
    html = page.read_text(encoding="utf-8")
    # The References section reached the page as a list, and no RST marker leaked.
    assert "numpydoc.readthedocs.io" in html, "References content missing from the page"
    assert ".. [" not in html, "RST citation syntax leaked into the rendered page"
