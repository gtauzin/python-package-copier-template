"""Tests for the See Also Griffe extension (`docs_build/_see_also.py`).

The extension rewrites numpydoc "See Also" blocks into markdown cross-references
at Griffe collection time, before mkdocstrings renders the docstring. It replaces
the HTML post-processing the docs hooks used to do (`_linkify_see_also`), which
reached into rendered HTML and was fragile against changes in mkdocstrings'
output shape. These tests drive the extension through a real Griffe load and
assert on the rewritten docstring; one test builds the docs and checks that
autorefs resolves the references into links.
"""

import importlib.util
import sys

import pytest
from _build_layout import BUILD_DIR, site_path

_MODELS = '''\
"""Models."""


class Beta:
    """Beta."""


class Gamma:
    """Gamma."""

    def fit(self):
        """Fit."""


class Alpha:
    """Alpha.

    See Also
    --------
    Beta : A sibling class.
    Gamma.fit : A method entry.
    numpy.ndarray : An external type.
    NotAThing : An unknown bare name.
    """


class Solo:
    """Solo.

    See Also
    --------
    Beta : The only entry.
    """


class Wrapped:
    """Wrapped.

    See Also
    --------
    Beta : A description that wraps onto
        a second indented line.
    """


class NameOnly:
    """NameOnly.

    See Also
    --------
    Beta
    Gamma
    """


class Bulleted:
    """Bulleted.

    See Also
    --------
    - [`Beta`][test_project.models.Beta] : Hand-written bullet with a link.
    - [`Gamma`][test_project.models.Gamma] : Another.
    """
'''


def _load_extension(project_dir, suffix):
    """Load the generated `_see_also` extension under a unique module name."""
    sys.modules.pop("_see_also", None)
    spec = importlib.util.spec_from_file_location(
        f"generated_see_also_{suffix}", project_dir / BUILD_DIR / "_see_also.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rewritten(project_dir, extension_module, package_name, obj_path):
    """Load the package through Griffe with the extension; return obj's docstring."""
    import griffe

    extensions = griffe.load_extensions(extension_module.SeeAlsoExtension())
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
    ext = _load_extension(project_dir, "seealso")

    def _get(obj_path):
        return _rewritten(project_dir, ext, "test_project", obj_path)

    return _get


def test_project_symbol_becomes_a_cross_reference(rewritten):
    """A See Also entry naming a project class links to that class's page."""
    assert "[`Beta`][test_project.models.Beta]" in rewritten("models.Alpha")


def test_member_entry_resolves_through_its_class(rewritten):
    """`Class.member` links to the member's anchor on the class page."""
    assert "[`Gamma.fit`][test_project.models.Gamma.fit]" in rewritten("models.Alpha")


def test_external_dotted_name_is_left_as_plain_code(rewritten):
    """A See Also name from another package renders as plain code, not an autoref.

    At collection time there is no way to know an inventory will resolve a
    dependency symbol, and an unresolved autoref is a FATAL warning under mkdocs
    ``--strict`` -- not the harmless plain text this once assumed. yohou-nixtla's
    ``See Also: yohou.point.BasePointForecaster`` reddened check_docs this way,
    while the identical source built clean before the rewrite existed (the old
    HTML hook rendered these as plain text). Only same-package and known project
    names link; a foreign-package dotted name is left unlinked.
    """
    out = rewritten("models.Alpha")
    assert "`numpy.ndarray`" in out
    assert "[`numpy.ndarray`]" not in out


def test_bare_unresolvable_name_is_left_unlinked(rewritten):
    """A bare name that is not a project symbol is not linked.

    A wrong link to an unrelated same-named symbol is worse than no link.
    """
    out = rewritten("models.Alpha")
    assert "`NotAThing`" in out
    assert "[`NotAThing`]" not in out


def test_multiple_entries_become_a_markdown_list(rewritten):
    """More than one entry renders as a list, one entry per line."""
    out = rewritten("models.Alpha")
    assert "- [`Beta`][test_project.models.Beta]" in out
    assert out.count("\n- ") >= 3


def test_name_only_entries_each_become_a_linked_list_item(rewritten):
    """Name-only See Also targets (no description) each get their own list item.

    numpydoc allows a target with no ``: description``, one per line. Splitting on
    a colon collapsed such a block onto a single, unlinked line -- yohou's See Also
    (written name-only) rendered exactly that way. Splitting by indentation gives
    each target its own linked list item instead.
    """
    out = rewritten("models.NameOnly")
    assert "- [`Beta`][test_project.models.Beta]" in out
    assert "- [`Gamma`][test_project.models.Gamma]" in out
    assert "Beta Gamma" not in out  # not collapsed onto one flowed line


def test_pre_bulleted_entries_render_as_a_flat_list(rewritten):
    """Hand-written bullet-list See Also entries render as a flat list, not nested.

    Some docstrings already write See Also as markdown bullets with author links
    (``- [`X`][ref] : desc``). Re-wrapping ``- [X]`` into ``- - [X]`` renders a
    nested, double-bulleted list once markdown converts it -- yohou (the fleet's
    largest curated docs) does this in 169 blocks. The leading list marker is
    stripped so each entry becomes a single clean list item, the author's link
    preserved.
    """
    out = rewritten("models.Bulleted")
    assert "- [`Beta`][test_project.models.Beta] : Hand-written bullet with a link." in out
    assert "- [`Gamma`][test_project.models.Gamma] : Another." in out
    assert "- -" not in out, "entries were double-bulleted -- markdown renders that as a nested list"


def test_single_entry_stays_a_paragraph(rewritten):
    """A lone entry is not turned into a list."""
    out = rewritten("models.Solo")
    assert "[`Beta`][test_project.models.Beta]" in out
    assert "- [`Beta`]" not in out


def test_wrapped_description_stays_one_entry(rewritten):
    """A description wrapping onto an indented line does not become a new entry."""
    out = rewritten("models.Wrapped")
    # One linked entry, and the continuation text is kept with it.
    assert out.count("[`Beta`][test_project.models.Beta]") == 1
    assert "a second indented line" in out


def test_description_text_is_preserved(rewritten):
    """The prose after the colon is carried through unchanged."""
    assert "A sibling class." in rewritten("models.Alpha")


@pytest.mark.integration
@pytest.mark.slow
def test_see_also_renders_as_a_resolved_link_end_to_end(copie):
    """A full build resolves a See Also reference into an autorefs link.

    The unit tests above prove the rewrite; this proves the rewrite reaches the
    rendered page and autorefs resolves it -- the property that matters to a reader.
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

    # hello()'s See Also names Greeter (the sample package ships this).
    page = site_path(project_dir) / "pages" / "api" / "generated" / "test_project.hello.hello" / "index.html"
    assert page.is_file(), "generated page for hello() not found"
    html = page.read_text(encoding="utf-8")
    assert 'class="autorefs' in html and "Greeter" in html, "See Also reference did not resolve to an autorefs link"
