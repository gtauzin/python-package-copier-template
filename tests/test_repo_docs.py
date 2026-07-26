"""Engine-independence invariants for THIS repository's own documentation.

The `docs-engine-portability` change made the docs this template *generates* for
downstream projects survive a migration off Material for MkDocs (EOL 2026-11-05)
to Zensical. This pins the same guarantee for the docs this repo publishes about
*itself* -- the root `mkdocs.yml` and `docs/`.

These docs are pure prose plus the Material theme: no `hooks:`, no markers, no
mkdocstrings rendering, no build-step modules. So the guarantee is mostly
"already true", and most of these assertions pin an invariant rather than test a
fix -- they fail loudly if a future edit reintroduces the engine-locked patterns
the fleet change had to remove.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

_REPO = Path(__file__).resolve().parent.parent


def _repo_mkdocs_config():
    """Load the repository's own mkdocs.yml, tolerating custom YAML tags."""

    class _Loader(yaml.SafeLoader):
        pass

    _Loader.add_multi_constructor("tag:yaml.org,2002:python/name:", lambda _loader, suffix, _node: suffix)
    _Loader.add_constructor("!ENV", lambda _loader, _node: None)
    return yaml.load((_REPO / "mkdocs.yml").read_text(encoding="utf-8"), Loader=_Loader)


def test_repo_docs_config_does_not_watch_itself():
    """A config that names itself in `watch:` makes the successor engine build an empty site.

    Zensical treats a self-referencing `watch:` as a signal to watch nothing and
    emits ZERO html at exit 0, `--strict` included. MkDocs watches its own config
    during `serve` regardless, so the entry is pure downside.
    """
    config = _repo_mkdocs_config()
    watch = config.get("watch") or []
    assert "mkdocs.yml" not in watch, "mkdocs.yml watches itself; the successor engine builds an empty site from that"
    assert "docs" in watch, "the docs directory must still be watched during serve"


def test_repo_docs_have_no_engine_hooks_or_in_source_build_tooling():
    """The repo's own docs depend on no mkdocs event hooks and ship no in-docs build tooling.

    Both are already true and pinned here: unlike the generated projects, these
    docs never had a `hooks.py` or a `docs_build/`. A `hooks:` key would not run
    under the successor engine, and any build-tooling `.py` under `docs_dir` would
    be published as a static asset.
    """
    config = _repo_mkdocs_config()
    assert "hooks" not in config, "the repo's own docs declare a hooks: key; the successor engine never runs it"
    stray = sorted(p.relative_to(_REPO).as_posix() for p in (_REPO / "docs").rglob("*.py"))
    assert not stray, f"build-tooling .py under docs/ would be published as a static asset: {stray}"


def test_repo_docs_theme_override_is_excluded_by_location():
    """The theme override is kept out of the built site by living outside docs_dir.

    `main.html` moved from `docs/material/overrides/` to `docs_theme/overrides/`,
    a sibling of `docs/`. The successor engine ignores `exclude_docs`, so location
    -- not that key -- is what keeps the override unpublished, under either engine.
    """
    assert not (_REPO / "docs" / "material").exists(), "the theme override still sits under docs_dir"
    assert (_REPO / "docs_theme" / "overrides" / "main.html").is_file(), "the relocated override is missing"
    config = _repo_mkdocs_config()
    assert config.get("theme", {}).get("custom_dir") == "docs_theme/overrides"
    assert "exclude_docs" not in config, "no exclude_docs is needed once the override is outside docs_dir"


def _publishing_engine():
    """The engine `.readthedocs.yml` actually publishes with.

    Read from the config rather than hardcoded, so switching engines cannot leave the
    gate asserting over the old one -- which is precisely the state this replaced.
    """
    commands = yaml.safe_load((_REPO / ".readthedocs.yml").read_text(encoding="utf-8"))["build"]["commands"]
    engines = {e for e in ("zensical", "mkdocs") for c in commands if f" {e} " in f" {c} "}
    assert len(engines) == 1, f".readthedocs.yml runs {engines or 'no known engine'}; cannot tell what publishes"
    return engines.pop()


def test_every_docs_entry_point_uses_the_publishing_engine():
    """No build or serve entry point may invoke an engine other than the published one.

    This repo ran four entry points across two engines: `.readthedocs.yml` and the
    `justfile` on Zensical, `noxfile.py` and the content gate below on MkDocs. The two
    that verified the docs were the two that disagreed with the one that shipped them,
    so the gate could not observe the failure it was written for. A cheap textual check
    keeps that split from reopening.
    """
    engine = _publishing_engine()
    other = "mkdocs" if engine == "zensical" else "zensical"

    # The two entry points spell an invocation differently: the justfile writes
    # `uv run mkdocs build`, the noxfile writes `session.run("mkdocs", "build", ...)`.
    # Matching the literal string "mkdocs build" finds the first and silently never
    # matches the second, so the check would pass over the file that actually broke.
    # Allow quotes, commas and whitespace between the engine and its verb.
    invocation = re.compile(rf"{other}[\"']?\s*,?\s*[\"']?(build|serve)\b")

    for name in ("noxfile.py", "justfile"):
        text = (_REPO / name).read_text(encoding="utf-8")
        offending = [ln.strip() for ln in text.splitlines() if invocation.search(ln)]
        assert not offending, (
            f"{name} invokes {other} while .readthedocs.yml publishes with {engine}: {offending}. "
            "A gate that builds with a different engine than the one that ships cannot see its failures."
        )


@pytest.mark.slow
@pytest.mark.integration
def test_repo_docs_build_ships_content_not_an_empty_site(tmp_path):
    """A real build produces non-empty pages and leaks no theme override.

    A green `--strict` build is not evidence: the empty-site bug and a leaked asset
    both pass at exit 0. This asserts on content instead.

    Built with the *publishing* engine. Zensical has no `--site-dir`, so instead of
    redirecting the output the sources are copied into a scratch tree and built there:
    that keeps the repo's own `site/` untouched and stops parallel workers racing over
    one output directory. Only the inputs a build needs are copied, so the copy is
    cheap and a stray file in the repo cannot influence the result.
    """
    if shutil.which("uv") is None:
        pytest.skip("uv is required to build the docs")

    engine = _publishing_engine()
    work = tmp_path / "docs-build"
    work.mkdir()
    for item in ("docs", "docs_theme", "mkdocs.yml", "pyproject.toml", "uv.lock"):
        source = _REPO / item
        if source.is_dir():
            shutil.copytree(source, work / item)
        else:
            shutil.copy2(source, work / item)

    build = subprocess.run(
        ["uv", "run", "--no-project", "--group", "docs", engine, "build", "-s"],
        cwd=work,
        capture_output=True,
        text=True,
        check=False,
    )
    assert build.returncode == 0, build.stderr[-2000:]

    site = work / "site"
    assert site.is_dir(), f"{engine} produced no site directory at all"

    index = site / "index.html"
    assert index.is_file() and index.stat().st_size > 500, (
        "the home page is missing or empty -- the build shipped nothing"
    )
    assert not list(site.glob("material/overrides/*.html")), "the Material theme override leaked into the built site"
    assert len(list(site.rglob("index.html"))) > 5, "the site has too few pages; content collapsed"
