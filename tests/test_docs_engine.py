"""End-to-end guards for the documentation engine (Zensical).

These build a generated project's docs through the same ``build_docs`` nox
session a contributor and CI run, and assert on the *rendered HTML*, not on the
build's exit status. That distinction is the whole point: the failure modes this
migration had to survive -- page-context markers silently rendering empty, and
build tooling leaking into the site -- both pass a green ``--strict`` build. A
test that trusts the exit code would not catch either.

``build_docs`` runs Zensical (the maintained successor to Material for MkDocs).
If these fail with an *empty* site on a developer machine, suspect exhausted
inotify instances rather than a real regression: the engine's file collector
needs them even for a one-shot build. See the contributor guide. CI runs in a
fresh environment and is unaffected.
"""

import posixpath
import re
import subprocess

import pytest
from _build_layout import OVERRIDES_DIR, TEMPLATES_DIR, site_path


@pytest.fixture(scope="module")
def built_site(session_projects_dir, request):
    """Render a project and build its docs once, returning the built-site dir.

    ``include_examples=False`` keeps the build fast (no notebook execution) while
    still exercising the API index, the section-index subpages, the mkdocstrings
    member pages and the theme overrides -- everything this migration touches.
    """
    from copier import run_copy

    project_dir = session_projects_dir / "engine-project"
    if not project_dir.exists():
        run_copy(
            str(request.config.rootpath),
            str(project_dir),
            data={
                "project_name": "Test Project",
                "project_slug": "test-project",
                "package_name": "test_project",
                "description": "A test project",
                "author_name": "Test Author",
                "author_email": "test@example.com",
                "github_username": "testuser",
                "version": "0.1.0",
                "min_python_version": "3.11",
                "max_python_version": "3.14",
                "license": "MIT",
                "include_actions": True,
                "include_examples": False,
            },
            defaults=True,
            overwrite=True,
            unsafe=True,
            vcs_ref="HEAD",
        )
        build = subprocess.run(  # noqa: S603
            ["uvx", "nox", "-s", "build_docs"],  # noqa: S607
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        assert build.returncode == 0, f"build_docs failed:\n{build.stdout}\n{build.stderr}"
    return site_path(project_dir)


def test_mkdocs_config_points_at_the_relocated_theme(copie_session_default):
    """The config references ``docs_build/`` and drops the tooling exclusions (task 7.3).

    A fast, build-free check: ``custom_dir``/``custom_templates`` must point at the
    relocated theme directory, and the old build-tooling ``exclude_docs`` entries
    (which the successor engine ignores anyway) must be gone.
    """
    content = (copie_session_default.project_dir / "mkdocs.yml").read_text(encoding="utf-8")
    assert f"custom_dir: {OVERRIDES_DIR}" in content
    assert f"custom_templates: {TEMPLATES_DIR}" in content
    assert "docs/material" not in content, "config still references the pre-relocation theme path"
    assert "material/overrides/*.html" not in content, "the tooling exclude_docs entry should be gone"
    # Zensical defaults to its "modern" theme variant; "classic" is the one that
    # reproduces the Material for MkDocs look the custom palette was written for.
    # Without it every generated site silently changes appearance.
    assert "variant: classic" in content, "theme.variant: classic is required so Zensical keeps the Material look"


def _real_pages(site):
    """Every rendered page, excluding the 404 stub."""
    return [p for p in site.rglob("*.html") if p.name != "404.html"]


@pytest.mark.integration
@pytest.mark.slow
def test_api_index_renders_a_populated_table(built_site):
    """The API index resolves ``<!-- API_TABLE -->`` to a real table (task 7.1).

    Before the seam fix this page rendered empty under Zensical -- the raw marker
    survived and there were zero rows -- at a green ``--strict`` build.
    """
    index = built_site / "pages" / "reference" / "api" / "index.html"
    assert index.is_file(), "the API index page was not generated"
    html = index.read_text(encoding="utf-8")
    assert "<!-- API_TABLE -->" not in html, "the API_TABLE marker did not resolve (rendered empty)"
    assert "<tr" in html, "the API index table has no rows"
    assert "test_project" in html, "the API index does not list the package's symbols"


@pytest.mark.integration
@pytest.mark.slow
def test_no_page_context_marker_survives_unresolved(built_site):
    """No raw marker comment is left in any rendered page (task 7.1).

    Catches the whole family (API_TABLE, SUBPAGES, GALLERY, companion) in one
    assertion: a surviving marker means a page rendered blank where it should
    have content.
    """
    markers = ("<!-- API_TABLE", "<!-- SUBPAGES", "<!-- GALLERY", "<!-- COMPANION")
    offenders = []
    for page in _real_pages(built_site):
        html = page.read_text(encoding="utf-8")
        if any(m in html for m in markers):
            offenders.append(page.relative_to(built_site).as_posix())
    assert not offenders, f"unresolved markers left in rendered pages: {offenders}"


@pytest.mark.integration
@pytest.mark.slow
def test_build_tooling_does_not_leak_into_the_site(built_site):
    """The theme overrides, mkdocstrings templates and scaffold stay unpublished (task 7.2).

    They live outside ``docs_dir`` (all of it under ``docs_build/``), so no
    engine can publish them -- the successor ignores ``exclude_docs``, so this is
    enforced by location, not configuration.
    """
    leaked = [
        p.relative_to(built_site).as_posix()
        for p in built_site.rglob("*")
        if p.is_file()
        and ("material" in p.parts or "overrides" in p.parts or p.suffix == ".jinja" or p.name == "api-submodule.html")
    ]
    assert not leaked, f"build tooling leaked into the built site: {leaked}"


@pytest.mark.integration
@pytest.mark.slow
def test_api_table_links_resolve(built_site):
    """Every API-table link points at a page that actually exists.

    The API table is injected as raw HTML, which the strict build never
    validates, so a wrong relative prefix 404s every row silently. The two
    engines resolve an injected relative href against different bases (MkDocs
    against the output url, Zensical against the source dir), so a prefix correct
    for one is off-by-one under the other. This resolves each link against the
    page's directory and asserts the target file exists.
    """
    # Sweep every rendered page, not just the API index: the module_toc sidebar
    # emits the same api links on every API submodule page, and the two engines
    # rewrite content links (the table) and template links (the sidebar)
    # differently, so a fix for one can break the other.
    checked = 0
    broken = []
    for page in _real_pages(built_site):
        html = page.read_text(encoding="utf-8")
        hrefs = re.findall(r'href="(\.\./[^"]*(?:pages/api|generated)[^"]*)"', html)
        if not hrefs:
            continue
        # the page's rendered url dir, e.g. site/pages/api/hello/index.html -> pages/api/hello/
        page_url_dir = page.parent.relative_to(built_site).as_posix() + "/"
        for href in hrefs:
            checked += 1
            target = posixpath.normpath(posixpath.join(page_url_dir, href.split("#")[0]))
            if target.startswith(".."):  # escaped above the site root -- always broken
                broken.append(f"{page_url_dir} -> {href}")
                continue
            if not (built_site / target / "index.html").exists() and not (built_site / target).exists():
                broken.append(f"{page_url_dir} -> {href}")
    assert checked, "no API links found in any page -- the table/sidebar did not render"
    assert not broken, f"api links 404 (target missing): {sorted(set(broken))[:8]}"


@pytest.mark.integration
@pytest.mark.slow
def test_homepage_title_is_the_bare_site_name(built_site):
    """The home page ``<title>`` is the bare ``site_name`` (matches Material).

    Zensical's ``base.html`` gates the bare-``site_name`` title branch on
    ``page.is_homepage``, a flag the engine never populates -- so every page,
    the home included, falls through to ``"<page title> - <site_name>"``, and a
    logo-led home with no H1 degrades further to the filename (``"Index - Site"``).
    Material set ``is_homepage`` and showed the bare name; the ``main.html``
    override restores that by matching the page url against ``nav.homepage.url``.
    The generated home *does* carry an H1, so a regression here surfaces as
    ``"Welcome to Test Project's documentation - Test Project"`` -- still wrong.
    """
    home = built_site / "index.html"
    assert home.is_file(), "the home page was not generated"
    match = re.search(r"<title>(.*?)</title>", home.read_text(encoding="utf-8"), re.S)
    assert match, "the home page has no <title>"
    title = match.group(1).strip()
    assert title == "Test Project", f"home <title> should be the bare site_name, got {title!r}"


@pytest.mark.integration
@pytest.mark.slow
def test_api_member_page_renders_at_parity(built_site):
    """A member page shows its Parameters, Returns and Source sections (task 7.6).

    mkdocstrings renders the API through Zensical's compatibility layer. This is
    the durable guard for the "renders at parity" requirement: a one-time manual
    comparison is not a regression test.
    """
    page = built_site / "pages" / "api" / "generated" / "test_project.hello.Greeter" / "index.html"
    assert page.is_file(), "the Greeter member page was not generated"
    html = page.read_text(encoding="utf-8")
    assert "Parameters" in html, "the member page is missing its Parameters section"
    assert "Returns" in html, "the member page is missing its Returns section"
    assert "Source code" in html, "the member page is missing its Source code section"
