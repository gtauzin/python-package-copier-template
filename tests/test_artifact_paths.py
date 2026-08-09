"""Every throwaway path a generated project writes has exactly one definition.

Coverage reports, the JUnit report, the tool caches, the nox environments and the
built site all land under a single ignored directory instead of at the repo root.
That only holds if the place that *writes* each path and the places that *read* it
agree, and nothing checked that they did.

They did not. The Codecov step uploaded ``coverage.<version>.xml``, a filename no
noxfile or ``pyproject.toml`` had written since the report paths moved into
``addopts``. It stayed green for releases because ``disable_search`` was off, so the
uploader searched the workspace and found ``coverage.xml`` on its own. The configured
path was dead and ``fail_ci_if_error: true`` could never fire.

The built site had the same shape of exposure, worse: seven separate places named
``site/`` by hand -- the Read the Docs publish step, two justfile recipes, two nox
sessions and four assertions inside one workflow step. The Read the Docs one cannot
be checked locally at all; that file says so in its own header.

So these tests do not check "the path is correct". They check that every reader
derives from the single writer, which is the only property that survives the next
relocation.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

_REPO = Path(__file__).resolve().parent.parent

# Paths that used to sit at the repository root. A generated project must not name
# any of them outside the one config key that defines where it now goes.
#
# `site/` carries the trailing slash deliberately. It is the entry that matters most
# -- seven separate places read the built site -- but bare `site` also appears in
# `site_url`, `site_name` and ordinary prose. Requiring the slash matches the path
# and not the word.
_RELOCATED = ("site/", "htmlcov", "coverage.xml", "junit.xml", ".nox", ".pytest_cache", ".ruff_cache")

# How each file format names the artifacts directory. A line carrying one of these
# is defining or deriving a path, not hardcoding a stray one.
_ARTIFACT_ANCHORS = (".artifacts", "ARTIFACTS_DIR", "artifacts_dir", "SITE_DIR", "site_dir")


def _mkdocs_config(project_dir):
    """Load a generated project's mkdocs.yml, tolerating its custom YAML tags."""

    class _Loader(yaml.SafeLoader):
        pass

    _Loader.add_multi_constructor("tag:yaml.org,2002:python/name:", lambda _loader, suffix, _node: suffix)
    _Loader.add_constructor("!ENV", lambda _loader, _node: None)
    return yaml.load((project_dir / "mkdocs.yml").read_text(encoding="utf-8"), Loader=_Loader)


def _read(project_dir, relative):
    return (project_dir / relative).read_text(encoding="utf-8")


def test_site_dir_is_nested_not_the_artifacts_root(copie_session_default):
    """`site_dir` must be a subdirectory, because the build empties it first.

    The docs build clears `site_dir` before writing. Pointing it at the artifacts
    directory itself would therefore delete the nox environments, every tool cache
    and the coverage data on each docs build -- a data-loss bug that no test would
    notice, because the build itself would still succeed.
    """
    site_dir = _mkdocs_config(copie_session_default.project_dir)["site_dir"]

    assert site_dir.count("/") >= 1, f"site_dir is {site_dir!r}; it must nest inside the artifacts directory"
    assert Path(site_dir).name != Path(site_dir).parent.name


def test_every_reader_of_the_built_site_agrees_with_mkdocs(copie_session_default):
    """`site_dir` in mkdocs.yml is the only thing that decides where the site lands.

    Zensical has no site-dir flag, so nothing overrides this key and nothing warns
    when a reader disagrees with it. A stale reader is silent: Read the Docs
    publishes an empty directory, and the link check examines a site that is not
    the one that was built.
    """
    project_dir = copie_session_default.project_dir
    site_dir = _mkdocs_config(project_dir)["site_dir"]

    # Readers that spell the path out, because their format has no variables to
    # compose with: a Read the Docs command list and a workflow step's `env:`.
    for name in (".readthedocs.yml", ".github/workflows/tests.yml"):
        text = _read(project_dir, name)
        assert site_dir in text, f"{name} does not reference the built site at {site_dir!r} from mkdocs.yml `site_dir`"

    # The noxfile composes it from a single constant instead of repeating the
    # literal, so check the composition rather than the string.
    noxfile = _read(project_dir, "noxfile.py")
    root = re.search(r"ARTIFACTS_DIR\s*=\s*Path\(\"([^\"]+)\"\)", noxfile)
    leaf = re.search(r"SITE_DIR\s*=\s*ARTIFACTS_DIR\s*/\s*\"([^\"]+)\"", noxfile)
    assert root and leaf, "noxfile.py does not derive SITE_DIR from ARTIFACTS_DIR"
    assert f"{root.group(1)}/{leaf.group(1)}" == site_dir, (
        f"noxfile.py composes {root.group(1)}/{leaf.group(1)!r}, mkdocs.yml says {site_dir!r}"
    )

    # The justfile composes the path from its own variables rather than repeating
    # the literal, which is the shape we want -- so ask just what the value resolves
    # to instead of string-matching a path that deliberately is not spelled out.
    if shutil.which("just") is None:
        pytest.skip("just is not installed; cannot resolve the justfile's site_dir")

    resolved = subprocess.run(
        ["just", "--evaluate", "site_dir"],
        cwd=project_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if resolved.returncode != 0:
        pytest.skip(f"just could not evaluate site_dir: {resolved.stderr.strip()}")

    assert resolved.stdout.strip() == site_dir, (
        f"justfile resolves site_dir to {resolved.stdout.strip()!r}, mkdocs.yml says {site_dir!r}"
    )


def test_no_file_names_a_relocated_path_by_hand(copie_session_default):
    """A path that moved may not survive as a literal anywhere in the project.

    This is the check that would have caught the Read the Docs `cp -r site/.` and
    the justfile's `linkchecker site/index.html`. Both were found by reading, which
    is exactly the method that missed four more of them in a single workflow step.
    """
    offenders = _hardcoded_relocated_paths(copie_session_default.project_dir)

    assert not offenders, "relocated paths still named by hand:\n" + "\n".join(offenders)


def test_the_hardcoded_path_scan_can_fail(copie_session_default, tmp_path):
    """The scan must actually catch a path someone spells out again.

    Its first version did not. `site/` was missing from the relocated list, and the
    word-boundary guard rejected the entry once it was added, so a deliberately
    reintroduced `linkchecker site/index.html` sailed through a green run. Both are
    fixed -- and the fix is worth nothing unless something keeps exercising the
    failure path, which is the whole argument this change is built on.
    """
    project_dir = tmp_path / "regressed"
    shutil.copytree(copie_session_default.project_dir, project_dir, symlinks=True)

    # Exactly the line that slipped through: a real path, in a real recipe, with no
    # tie to the artifacts directory.
    justfile = project_dir / "justfile"
    justfile.write_text(
        justfile.read_text(encoding="utf-8") + "\nstale:\n    uvx linkchecker site/index.html\n",
        encoding="utf-8",
    )

    offenders = _hardcoded_relocated_paths(project_dir)

    assert any("linkchecker site/index.html" in offender for offender in offenders), (
        f"the scan missed a hardcoded site path; it reported {offenders}"
    )


def test_coverage_upload_path_is_the_path_coverage_writes(copie_session_default):
    """The Codecov `files:` input must name the file the coverage config produces.

    These drifted apart once already and nothing noticed, because the uploader's
    fallback search found the real report and reported success.
    """
    project_dir = copie_session_default.project_dir

    pyproject = _read(project_dir, "pyproject.toml")
    written = re.search(r"\[tool\.coverage\.xml\][^\[]*?output\s*=\s*\"([^\"]+)\"", pyproject, re.S)
    assert written, "pyproject.toml does not set [tool.coverage.xml] output; the report path is undefined"

    workflow = _read(project_dir, ".github/workflows/tests.yml")
    uploaded = re.search(r"files:\s*'\$\{\{ github\.workspace \}\}/([^']+)'", workflow)
    assert uploaded, "the coverage upload step does not name a file"

    assert uploaded.group(1) == written.group(1), (
        f"coverage upload reads {uploaded.group(1)!r} but the coverage config writes {written.group(1)!r}"
    )


def test_test_results_upload_path_is_the_path_pytest_writes(copie_session_default):
    """The test-results `file:` input must name the JUnit report the nox session writes."""
    project_dir = copie_session_default.project_dir

    noxfile = _read(project_dir, "noxfile.py")
    written = re.search(r"JUNIT_XML\s*=\s*ARTIFACTS_DIR\s*/\s*\"([^\"]+)\"", noxfile)
    assert written, "noxfile.py does not define JUNIT_XML; the report path is undefined"

    workflow = _read(project_dir, ".github/workflows/tests.yml")
    uploaded = re.search(r"file:\s*'\$\{\{ github\.workspace \}\}/([^']+)'", workflow)
    assert uploaded, "the test-results upload step does not name a file"

    assert uploaded.group(1).endswith(written.group(1)), (
        f"test-results upload reads {uploaded.group(1)!r} but the session writes {written.group(1)!r}"
    )


def test_coverage_upload_does_not_fall_back_to_searching(copie_session_default):
    """`fail_ci_if_error` only means something with the uploader's search disabled.

    With search on, a `files:` input that names nothing is not an error: the CLI
    scans the workspace, uploads whatever it finds, and the step passes. That is
    precisely how a dead upload path survived several releases.
    """
    workflow = _read(copie_session_default.project_dir, ".github/workflows/tests.yml")

    assert "disable_search: true" in workflow, (
        "the coverage upload leaves search enabled, so a wrong `files:` path cannot fail the build"
    )


def test_artifacts_directory_is_ignored(copie_session_default):
    """One ignore entry has to cover everything that was redirected."""
    project_dir = copie_session_default.project_dir
    site_dir = _mkdocs_config(project_dir)["site_dir"]
    artifacts_dir = site_dir.split("/", 1)[0]

    ignored = _read(project_dir, ".gitignore").splitlines()

    assert f"{artifacts_dir}/" in ignored, f"{artifacts_dir}/ is not in .gitignore, so build output would be committed"


def _hardcoded_relocated_paths(project_dir):
    """Lines that name a relocated path with no tie to the artifacts directory."""
    offenders = []

    for path in project_dir.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        relative = path.relative_to(project_dir)
        for name in _RELOCATED:
            # An entry ending in `/` is already delimited by the slash, and what
            # follows it is the rest of the path. Applying the word-boundary guard
            # there would reject every real use (`site/index.html`) and match none.
            trailing = "" if name.endswith("/") else r"(?![\w-])"
            for match in re.finditer(rf"(?<![\w./-]){re.escape(name)}{trailing}", text):
                line = text[: match.start()].rsplit("\n", 1)[-1] + text[match.start() :].split("\n", 1)[0]
                # A comment explaining the layout may name any of these freely.
                if line.lstrip().startswith("#"):
                    continue
                # The point is not that the basename never appears -- it has to appear
                # where the path is defined. What must never appear is a basename used
                # as a path with no tie to the artifacts directory, whether spelled
                # literally or reached through the one constant each format uses.
                if any(anchor in line for anchor in _ARTIFACT_ANCHORS):
                    continue
                offenders.append(f"{relative}: {line.strip()}")

    return sorted(set(offenders))


def _docs_dir(project_dir):
    """The configured `docs_dir`, defaulting to `docs` as both engines do."""
    return project_dir / _mkdocs_config(project_dir).get("docs_dir", "docs")


def _build_tooling_under_docs_dir(project_dir):
    """Build-tooling files that sit under `docs_dir`, where a build would publish them."""
    docs_dir = _docs_dir(project_dir)

    return sorted(
        path.relative_to(project_dir).as_posix()
        for path in docs_dir.rglob("*")
        if path.is_file()
        and (
            path.suffix == ".jinja"
            or path.name == "api-submodule.html"
            or "overrides" in path.relative_to(docs_dir).parts
            or "templates" in path.relative_to(docs_dir).parts
        )
    )


def test_no_build_tooling_resolves_under_docs_dir(copie_session_default):
    """Build tooling stays outside `docs_dir`, enforced by location rather than config.

    Everything under `docs_dir` is copied into the built site as a static asset.
    MkDocs can suppress that with `exclude_docs`, but the successor engine ignores
    that key entirely, so position in the tree is the only control that holds under
    both engines. That is why the theme overrides, the mkdocstrings templates and the
    build scripts all live in `docs_build/`, a sibling of `docs/`.

    The integration test that builds a site and inspects it proves the same thing more
    directly, but it needs a real build. This one is structural and runs in the fast
    suite, so a reorganisation that moves tooling under `docs/` fails immediately
    rather than at the next full run.
    """
    leaked = _build_tooling_under_docs_dir(copie_session_default.project_dir)

    assert not leaked, (
        "build tooling sits under docs_dir, where the successor engine will publish it "
        f"and exclude_docs cannot stop it: {leaked}"
    )


def test_the_docs_dir_invariant_can_fail(copie_session_default, tmp_path):
    """The scan above must actually catch tooling placed under `docs_dir`.

    A check whose failure path never runs is the shape of defect this whole change
    exists to stop shipping, so exercise it against a project that violates the rule.
    """
    project_dir = tmp_path / "violating"
    shutil.copytree(copie_session_default.project_dir, project_dir, symlinks=True)

    planted = _docs_dir(project_dir) / "overrides" / "main.html"
    planted.parent.mkdir(parents=True, exist_ok=True)
    planted.write_text("a theme override that must not be publishable", encoding="utf-8")

    assert _build_tooling_under_docs_dir(project_dir) == ["docs/overrides/main.html"]


@pytest.mark.parametrize(
    ("config_file", "key"),
    [
        ("pyproject.toml", "cache_dir"),
        ("pyproject.toml", "cache-dir"),
        ("pyproject.toml", "data_file"),
        ("pyproject.toml", "directory"),
        ("noxfile.py", "envdir"),
    ],
)
def test_each_redirect_points_under_the_artifacts_directory(copie_session_default, config_file, key):
    """Every redirect knob resolves under the single artifacts directory.

    A knob set to some other location is not a bug the root listing reveals: the
    root stays clean while the output lands somewhere nobody cleans.
    """
    project_dir = copie_session_default.project_dir
    site_dir = _mkdocs_config(project_dir)["site_dir"]
    artifacts_dir = site_dir.split("/", 1)[0]

    text = _read(project_dir, config_file)
    match = re.search(rf"{re.escape(key)}\s*=\s*\"([^\"]+)\"", text)

    assert match, f"{config_file} does not set {key}; that output would land at the project root"
    assert match.group(1).startswith(artifacts_dir), (
        f"{config_file} sets {key} to {match.group(1)!r}, outside {artifacts_dir!r}"
    )
