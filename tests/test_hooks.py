"""Tests for the docs build steps and the git-ref helper."""

import pytest
from _build_layout import BUILD_DIR, site_path
from test_template import _load_build, _load_git_ref


@pytest.fixture
def copie_with_examples(copie):
    """Copy template with examples enabled."""
    result = copie.copy(
        extra_answers={
            "include_examples": True,
        },
    )
    assert result.exit_code == 0
    return result


@pytest.fixture
def copie_without_examples(copie):
    """Copy template with examples disabled."""
    result = copie.copy(
        extra_answers={
            "include_examples": False,
        },
    )
    assert result.exit_code == 0
    return result


def test_hooks_file_created_with_examples(copie_with_examples):
    """The build steps ship in build.py when examples are enabled; hooks.py is gone."""
    build_file = copie_with_examples.project_dir / BUILD_DIR / "build.py"
    assert build_file.is_file(), "docs_build/build.py not created"
    assert not (copie_with_examples.project_dir / BUILD_DIR / "hooks.py").exists(), "hooks.py should be gone"

    # Verify build content
    build_content = build_file.read_text(encoding="utf-8")
    assert "def prebuild(" in build_content, "prebuild step not found"
    assert "def postbuild(" in build_content, "postbuild step not found"

    # The playground link is built at markdown level now -- by the marker
    # extension, not a hook -- so it lives in _markers.py, which imports the
    # single git-ref definition rather than deriving its own.
    markers_content = (copie_with_examples.project_dir / BUILD_DIR / "_markers.py").read_text(encoding="utf-8")
    assert "marimo.app" in markers_content, "marimo.app playground link not found in the marker extension"
    # The export itself lives in _notebooks.py; assert against the module that owns it
    # so this keeps failing if the export disappears, rather than passing because
    # build.py still happens to mention marimo.
    assert "_notebooks.export" in build_content, "prebuild does not delegate the notebook export"
    notebooks_content = (copie_with_examples.project_dir / BUILD_DIR / "_notebooks.py").read_text(encoding="utf-8")
    assert "marimo" in notebooks_content, "marimo export logic not found"
    assert "--no-sandbox" in notebooks_content, "--no-sandbox flag not found"


def test_hooks_file_created_without_examples(copie_without_examples):
    """The build steps ship in build.py even when examples are disabled; hooks.py is gone."""
    build_file = copie_without_examples.project_dir / BUILD_DIR / "build.py"
    assert build_file.is_file(), "docs_build/build.py not created"
    assert not (copie_without_examples.project_dir / BUILD_DIR / "hooks.py").exists(), "hooks.py should be gone"

    # Verify build content has both steps
    build_content = build_file.read_text(encoding="utf-8")
    assert "def postbuild(" in build_content, "postbuild step not found"

    # prebuild should always exist (for API page generation)
    assert "def prebuild(" in build_content, "prebuild should exist for API page generation"


def test_on_post_build_copies_markdown(copie_with_examples, tmp_path):
    """The postbuild step copies markdown files into the built site."""
    build = _load_build(copie_with_examples.project_dir, "post_md")

    site_dir = tmp_path / "site"
    site_dir.mkdir()

    # postbuild reads the docs dir from build.py's own location; site_dir is where
    # the cleaned markdown lands.
    build.postbuild(str(site_dir))

    # Verify markdown files were copied
    assert (site_dir / "index.md").is_file(), "index.md not copied"
    assert (site_dir / "pages" / "tutorials" / "getting-started.md").is_file(), "getting-started.md not copied"
    assert (site_dir / "pages" / "how-to" / "contribute.md").is_file(), "contribute.md not copied"


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.skip(reason="Marimo HTML export feature not fully implemented in examples.md template")
def test_on_post_build_copies_html(copie_with_examples, tmp_path):
    """Test that on_post_build hook copies standalone HTML files."""
    import subprocess

    # First export notebooks using build_docs to trigger hooks
    subprocess.run(
        ["uvx", "nox", "-s", "build_docs"],
        cwd=copie_with_examples.project_dir,
        capture_output=True,
        timeout=60,
        check=True,
    )

    # Verify HTML was exported
    html_file = copie_with_examples.project_dir / "docs" / "examples" / "hello" / "index.html"
    assert html_file.is_file(), "HTML file not exported by on_pre_build"

    # Verify HTML was also copied to site by on_post_build
    site_html = site_path(copie_with_examples.project_dir) / "examples" / "hello" / "index.html"
    assert site_html.is_file(), "Standalone HTML not copied to site"

    # Verify the HTML file is substantial (not just a stub)
    html_size = site_html.stat().st_size
    assert html_size > 10000, f"HTML file too small ({html_size} bytes), may not be properly exported"


@pytest.mark.skip(reason="Marimo HTML export feature not fully implemented in examples.md template")
@pytest.mark.integration
@pytest.mark.slow
def test_on_pre_build_exports_notebooks(copie_with_examples):
    """Test that on_pre_build exports marimo notebooks."""
    import subprocess

    # Build docs which triggers on_pre_build
    result = subprocess.run(
        ["uvx", "nox", "-s", "build_docs"],
        cwd=copie_with_examples.project_dir,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert result.returncode == 0, f"build_docs failed: {result.stderr}"

    # Verify exported HTML exists
    html_file = copie_with_examples.project_dir / "docs" / "examples" / "hello" / "index.html"
    assert html_file.is_file(), "Notebook not exported to HTML"

    # Verify it's a valid HTML file
    html_content = html_file.read_text(encoding="utf-8")
    assert "<html" in html_content, "Exported file is not valid HTML"
    assert "marimo" in html_content.lower(), "HTML doesn't contain marimo runtime"


def test_on_post_build_handles_missing_examples_dir(copie_with_examples, tmp_path):
    """postbuild gracefully handles a missing examples directory."""
    build = _load_build(copie_with_examples.project_dir, "post_missing")

    site_dir = tmp_path / "site"
    site_dir.mkdir()

    # Remove examples directory if it exists
    docs_examples = copie_with_examples.project_dir / "docs" / "examples"
    if docs_examples.exists():
        import shutil

        shutil.rmtree(docs_examples)

    # Should not raise
    build.postbuild(str(site_dir))


def test_hooks_integrated_in_mkdocs_yml(copie_with_examples):
    """The marker extension is wired in mkdocs.yml; the hooks: key is gone."""
    import re

    mkdocs_yml = copie_with_examples.project_dir / "mkdocs.yml"
    content = mkdocs_yml.read_text(encoding="utf-8")

    # The `hooks:` config key is gone -- the successor engine does not execute it.
    # Match it at the start of a line so the explanatory comment that mentions
    # `hooks:` in backticks does not count as the key.
    assert not re.search(r"^hooks:", content, re.MULTILINE), "the hooks: key should be gone from mkdocs.yml"
    assert "docs_build._markers" in content, "the marker extension is not registered in mkdocs.yml"
    assert "docs_build._glossary" in content, "the glossary extension is not registered in mkdocs.yml"


@pytest.mark.integration
@pytest.mark.slow
def test_on_post_build_converts_html_to_markdown(copie_with_examples, tmp_path):
    """Test that on_post_build converts HTML to markdown for LLM consumption."""
    import subprocess

    # Build docs to generate both HTML and markdown
    result = subprocess.run(
        ["uvx", "nox", "-s", "build_docs"],
        cwd=copie_with_examples.project_dir,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, f"build_docs failed: {result.stderr}"

    # Verify markdown files exist in site directory
    site_dir = site_path(copie_with_examples.project_dir)
    assert (site_dir / "index.md").is_file(), "index.md not found in site"
    assert (site_dir / "pages" / "tutorials" / "getting-started.md").is_file(), "getting-started.md not found in site"
    assert (site_dir / "pages" / "reference" / "api.md").is_file(), "api.md not found"

    # Verify markdown content is cleaned (not just raw source)
    index_md = (site_dir / "index.md").read_text(encoding="utf-8")
    assert len(index_md) > 100, "Markdown file is too short"
    assert "# " in index_md, "Markdown doesn't contain headers"


def test_on_post_build_copies_llms_txt_if_exists(copie_with_examples, tmp_path):
    """postbuild copies llms.txt if it exists."""
    build = _load_build(copie_with_examples.project_dir, "post_llms")

    # Create llms.txt in docs
    docs_dir = copie_with_examples.project_dir / "docs"
    llms_txt = docs_dir / "llms.txt"
    llms_txt.write_text("# LLM Context\nProject documentation", encoding="utf-8")

    site_dir = tmp_path / "site"
    site_dir.mkdir()

    build.postbuild(str(site_dir))

    # Verify llms.txt was copied
    assert (site_dir / "llms.txt").is_file(), "llms.txt not copied to site"
    content = (site_dir / "llms.txt").read_text(encoding="utf-8")
    assert "LLM Context" in content, "llms.txt content not preserved"


def test_on_post_build_removes_legacy_llm_directory(copie_with_examples, tmp_path):
    """postbuild removes a legacy llm/ directory."""
    build = _load_build(copie_with_examples.project_dir, "post_legacy")

    site_dir = tmp_path / "site"
    site_dir.mkdir()

    # Create legacy llm directory
    legacy_dir = site_dir / "llm"
    legacy_dir.mkdir()
    (legacy_dir / "old_file.md").write_text("old content", encoding="utf-8")

    build.postbuild(str(site_dir))

    # Verify legacy directory was removed
    assert not legacy_dir.exists(), "Legacy llm/ directory not removed"


def test_html_to_markdown_conversion_preserves_structure(copie_with_examples):
    """HTML to markdown conversion preserves document structure."""
    build = _load_build(copie_with_examples.project_dir, "h2m_struct")

    # Test HTML with various elements
    test_html = """
    <h1>Main Title</h1>
    <p>This is a paragraph with <strong>bold</strong> and <em>italic</em> text.</p>
    <pre><code class="language-python">def example():
    return "hello"</code></pre>
    <ul>
        <li>First item</li>
        <li>Second item</li>
    </ul>
    """

    markdown = build._markdown_export._html_to_markdown(test_html)

    # Verify structure is preserved
    assert "# Main Title" in markdown, "H1 not converted"
    assert "**bold**" in markdown, "Bold not converted"
    assert "*italic*" in markdown, "Italic not converted"
    assert "```python" in markdown, "Code fence not created"
    assert "def example():" in markdown, "Code content not preserved"
    assert "- First item" in markdown or "- First item" in markdown, "List not converted"


def test_html_to_markdown_handles_tables(copie_with_examples):
    """HTML to markdown conversion handles tables correctly."""
    build = _load_build(copie_with_examples.project_dir, "h2m_tables")

    test_html = """
    <table>
        <tr>
            <th>Header 1</th>
            <th>Header 2</th>
        </tr>
        <tr>
            <td>Cell 1</td>
            <td>Cell 2</td>
        </tr>
    </table>
    """

    markdown = build._markdown_export._html_to_markdown(test_html)

    # Verify table structure
    assert "|" in markdown, "Table pipes not found"
    assert "---" in markdown, "Table separator not found"
    assert "Header 1" in markdown, "Table headers not preserved"
    assert "Cell 1" in markdown, "Table cells not preserved"


@pytest.mark.integration
@pytest.mark.slow
def test_markdown_accessible_after_docs_build(copie_with_examples):
    """Test that markdown files are accessible after docs build completes."""
    import subprocess

    # Build docs
    result = subprocess.run(
        ["uvx", "nox", "-s", "build_docs"],
        cwd=copie_with_examples.project_dir,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, f"build_docs failed: {result.stderr}"

    site_dir = site_path(copie_with_examples.project_dir)

    # Verify both HTML and markdown exist for each page
    pages = [
        "index",
        "pages/tutorials/getting-started",
        "pages/explanation/concepts",
        "pages/reference/api",
        "pages/how-to/contribute",
    ]

    for page in pages:
        # MkDocs uses directory URLs: pages/foo.md → pages/foo/index.html
        if page == "index":
            html_path = site_dir / f"{page}.html"
        else:
            html_path = site_dir / f"{page}/index.html"
        md_path = site_dir / f"{page}.md"

        assert html_path.is_file(), f"HTML not found: {html_path}"
        assert md_path.is_file(), f"Markdown not found: {md_path}"

        # Verify markdown is not empty
        md_content = md_path.read_text(encoding="utf-8")
        assert len(md_content) > 50, f"Markdown too short for {page}"


def test_git_ref_has_exactly_one_definition(copie_with_examples):
    """The build must not carry two notions of "which commit is this".

    There used to be two: a git-ref helper shelled out to ``git rev-parse``, and
    the marimo playground link read ``READTHEDOCS_*`` on its own. They disagree
    whenever git is unavailable but Read the Docs is not, and the page then
    published "View on GitHub" at ``main`` next to "Open in marimo" at a real
    commit. The ref now has a single home, ``_git_ref.py``; asserting on the
    source, not just behaviour, is what stops a second lookup from being
    reintroduced.
    """
    build_dir = copie_with_examples.project_dir / BUILD_DIR
    git_ref_content = (build_dir / "_git_ref.py").read_text(encoding="utf-8")
    markers_content = (build_dir / "_markers.py").read_text(encoding="utf-8")
    source_links_content = (build_dir / "_source_links.py").read_text(encoding="utf-8")

    # The environment reads and the git shell-out live once, in _git_ref.py. Count
    # the reads, not the string: the docstring names the variables to explain the
    # precedence order, and matching prose would pass on a second lookup written
    # slightly differently -- an assertion over the wrong set.
    assert git_ref_content.count('os.environ.get("READTHEDOCS_GIT_COMMIT_HASH")') == 1, (
        "READTHEDOCS_GIT_COMMIT_HASH is not read exactly once in _git_ref.py"
    )
    assert git_ref_content.count('os.environ.get("READTHEDOCS_GIT_IDENTIFIER"') == 1
    assert "rev-parse" in git_ref_content, "the git rev-parse fallback left _git_ref.py"

    # No consumer reads the ref a second way: the marker extension and the
    # Source Code links both resolve it through the single definition, so the
    # GitHub and marimo links cannot point at different commits.
    for name, content in (("_markers.py", markers_content), ("_source_links.py", source_links_content)):
        assert "READTHEDOCS_GIT_COMMIT_HASH" not in content, f"{name} reads the git ref itself instead of importing it"
        assert "rev-parse" not in content, f"{name} shells out for the git ref itself instead of importing it"
        assert "from _git_ref import git_ref" in content, f"{name} does not import the single git-ref definition"


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({"READTHEDOCS_GIT_COMMIT_HASH": "deadbeefcafe"}, "deadbeefcafe"),
        ({"READTHEDOCS_GIT_IDENTIFIER": "v1.2.3"}, "v1.2.3"),
        ({}, "main"),
    ],
    ids=["commit-hash-wins", "identifier-fallback", "last-resort"],
)
def test_get_git_ref_prefers_readthedocs_over_missing_git(copie_with_examples, monkeypatch, tmp_path, env, expected):
    """Read the Docs' commit is authoritative when git cannot answer.

    The checkout there can be shallow or detached, and some builds have no
    usable ``.git`` at all -- which is exactly when the old implementation
    reported ``main`` for a build that was really at a known commit.
    """
    git_ref = _load_git_ref(copie_with_examples.project_dir, f"gitref_{expected.replace('.', '_')}")

    for var in ("READTHEDOCS_GIT_COMMIT_HASH", "READTHEDOCS_GIT_IDENTIFIER"):
        monkeypatch.delenv(var, raising=False)
    for var, value in env.items():
        monkeypatch.setenv(var, value)

    # Run where `git rev-parse` cannot answer, so the fallback chain is what is
    # under test rather than whatever repo the suite happens to run in.
    monkeypatch.chdir(tmp_path)
    git_ref._CACHE = None
    try:
        assert git_ref.git_ref() == expected
    finally:
        git_ref._CACHE = None
