"""CI invariants for THIS repository's own workflows.

`test_github_workflows.py` asserts these properties over the workflows the template
*generates*. Nothing asserted them over the workflows this repository *runs*, which is
how `fix(ci): pin exact uv version in all setup-uv steps` (#220) pinned every step it
could see and left all of this repo's own steps floating: "all" silently meant "all in
the template". The count then grew from five to six while nobody was looking.

These tests are the other half of that pair. They exist so a property the template
enforces downstream cannot be quietly absent upstream.
"""

import filecmp
import re
import subprocess
from pathlib import Path

import yaml
from _tool_invocations import find_invocations, unreadable_annotations
from _tool_invocations import unpinned as unpinned_invocations
from _workflow_expressions import injection_sites, sites_in_text

_REPO = Path(__file__).resolve().parent.parent
_WORKFLOWS = _REPO / ".github" / "workflows"
_TEMPLATE_WORKFLOWS = _REPO / "template" / ".github" / "{% if include_actions %}workflows{% endif %}"
_EXACT_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def _repo_workflow_paths():
    """Every workflow file this repository runs."""
    return sorted(_WORKFLOWS.glob("*.yml"))


def _setup_uv_steps():
    """Collect every setup-uv step across this repo's workflows as (file, with-block).

    Discovered by walking the parsed workflows rather than from a hardcoded list, so a
    step added to any workflow, existing or new, is covered without editing this test.
    That is the property that failed before: the count changed and nothing noticed.
    """
    steps = []
    for path in _repo_workflow_paths():
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job in (workflow.get("jobs") or {}).values():
            for step in job.get("steps") or []:
                if str(step.get("uses", "")).startswith("astral-sh/setup-uv"):
                    steps.append((path.name, step.get("with") or {}))
    return steps


def _template_uv_version():
    """The uv version the template pins for generated projects.

    Read rather than hardcoded so this repo's pin is checked against the same source of
    truth the fleet gets, and a bump in one place fails here instead of drifting.

    The source moved: uv used to be a copier answer read from `copier.yml`, which meant
    every generated repo also stored the value in `.copier-answers.yml` where Renovate
    could not see it and it went stale. It is now a literal in the template's own
    workflows, maintained like `nox` and `git-cliff`, so that is what this reads.
    """
    versions = set()
    for path in sorted(_TEMPLATE_WORKFLOWS.glob("*.jinja")):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
            if not line.strip().startswith("version:"):
                continue
            preceding = "\n".join(path.read_text(encoding="utf-8").splitlines()[max(0, i - 4) : i])
            if "astral-sh/setup-uv" in preceding:
                versions.add(line.split(":", 1)[1].strip().strip('"').strip("'"))
    assert versions, "no templated setup-uv version pin found; this check would compare against nothing"
    assert len(versions) == 1, f"the template pins differing uv versions: {sorted(versions)}"
    return versions.pop()


def test_the_assertion_reads_this_repository_not_generated_output():
    """This test file's inputs are the root workflows, which is the whole point.

    The generated-output test passed for years while this repo went unchecked. If this
    ever collects nothing, the pin assertions below would pass vacuously and the gap
    would silently reopen, so assert the inputs before asserting anything about them.
    """
    assert _WORKFLOWS.is_dir(), "this repository has no .github/workflows to check"
    assert _repo_workflow_paths(), "no workflows found; the pin assertions would pass over an empty set"
    assert _setup_uv_steps(), "no astral-sh/setup-uv steps found in this repository's workflows"


def test_no_untrusted_expression_reaches_a_shell():
    """No `${{ github.event.* }}` is substituted into a `run:` or `script:` body here.

    The template's half of this pair lives in `test_security_hardening.py` and asserts it
    over the generated project. This half asserts it over the workflows this repository
    runs, because the two trees drift: the repo's own `publish-release.yml` carried the
    injection in a different job layout than the template's, so a fix to the template
    would not have reached it and a check reading only the template would have called
    this repository clean.

    Untrusted values belong in `env:`, where the runner sets them as environment
    variables and the shell reads them as data. See `_workflow_expressions` for why the
    quotes around an interpolation do not help.
    """
    sites = [site for path in _repo_workflow_paths() for site in injection_sites(path)]
    assert not sites, "untrusted expressions substituted into a script body (move them to `env:`): " + ", ".join(
        f"{name}:{line} {expr}" for name, line, expr in sites
    )


def test_this_repo_scopes_its_own_codeql_scan():
    """This repository reads a CodeQL config too, and it exists.

    The template's half is in `test_security_hardening.py`. This repository's `codeql.yml`
    is not generated from the template, so a fix there would leave this one scanning its
    own test suite -- which is where five of the seven CodeQL false positives were.
    """
    workflow = (_WORKFLOWS / "codeql.yml").read_text(encoding="utf-8")
    assert "config-file: ./.github/codeql/codeql-config.yml" in workflow, (
        "codeql.yml does not point at a config, so the default suite scans tests/"
    )
    config = _REPO / ".github" / "codeql" / "codeql-config.yml"
    assert config.is_file(), "codeql.yml points at a config that does not exist; the workflow would fail"
    assert "- tests" in config.read_text(encoding="utf-8")


def test_the_injection_scanner_finds_what_it_is_meant_to_find():
    """A clean result means the scanner looked, not that the walk fell off line one.

    `injection_sites` returning nothing is equally consistent with "no injections" and
    "the block-scalar walk read nothing". Both placements the vulnerable code actually
    took are exercised here, plus the two forms that must NOT fail: the safe `env:`
    handoff this repository now uses, and `if:` conditions, which are evaluated by
    Actions rather than spliced into a shell.
    """
    caught = sites_in_text(
        "jobs:\n"
        "  build:\n"
        "    steps:\n"
        "      - run: |\n"
        '          PR_TITLE="${{ github.event.pull_request.title }}"\n'
        "      - run: echo ${{ github.head_ref }}\n"
        "      - uses: actions/github-script@v9\n"
        "        with:\n"
        "          script: |\n"
        "            core.info(`${{ github.event.issue.title }}`)\n"
    )
    assert [expr for _, _, expr in caught] == [
        "github.event.pull_request.title",
        "github.head_ref",
        "github.event.issue.title",
    ]

    allowed = sites_in_text(
        "jobs:\n"
        "  build:\n"
        "    if: github.event.pull_request.merged == true\n"
        "    steps:\n"
        "      - env:\n"
        "          PR_TITLE: ${{ github.event.pull_request.title }}\n"
        "        run: |\n"
        "          printf '%s' \"$PR_TITLE\"\n"
    )
    assert allowed == []


def test_every_repo_setup_uv_step_pins_an_exact_version():
    """Every setup-uv step in this repo pins an exact X.Y.Z, matching what it ships.

    Resolving "latest" is an un-retried network call and the point at which a transient
    blip fails CI before any real work. A range like "0.10" still resolves over the
    network, so a non-empty version is not enough.
    """
    unpinned = [f for f, w in _setup_uv_steps() if not w.get("version")]
    assert not unpinned, f"setup-uv steps with no uv version pin in: {sorted(set(unpinned))}"

    inexact = [(f, w["version"]) for f, w in _setup_uv_steps() if not _EXACT_SEMVER.match(str(w["version"]))]
    assert not inexact, f"uv versions that are not an exact X.Y.Z pin: {inexact}"


def test_repo_uv_pin_is_uniform_and_matches_the_version_shipped_to_projects():
    """One uv version across this repo, and the same one generated projects get.

    A repo pinning a different uv than it hands out is testing the template against a
    toolchain no generated project uses.
    """
    versions = {str(w["version"]) for _, w in _setup_uv_steps() if w.get("version")}
    assert len(versions) == 1, f"setup-uv steps pin differing uv versions: {sorted(versions)}"
    assert versions == {_template_uv_version()}, (
        f"this repo pins uv {sorted(versions)} but the template ships {_template_uv_version()} to projects"
    )


def test_every_repo_uv_pin_carries_a_renovate_annotation():
    """A pin with no annotation is a pin Renovate never bumps.

    Checked against the raw text, not the parsed YAML: the annotation is a comment, so
    the parser drops it and a purely structural check cannot see it missing.
    """
    for path in _repo_workflow_paths():
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            preceding = "\n".join(lines[max(0, i - 4) : i])
            if line.strip().startswith("version:") and "astral-sh/setup-uv" in preceding:
                previous = lines[i - 1].strip() if i > 0 else ""
                assert previous.startswith("# renovate:"), (
                    f"{path.name} line {i + 1}: setup-uv version pin has no `# renovate:` annotation, "
                    "so Renovate cannot bump it and it will rot at whatever it was set to"
                )


def _tracked(prefix):
    """Files git tracks under a prefix, as paths relative to that prefix.

    Scoped to tracked files on purpose. Both skill trees deliberately ignore
    `openspec-*` skills, which `.gitignore` describes as "tool state that openspec
    rewrites, not project content", and the CLI writes them into whichever tree it
    likes. A working-tree comparison therefore reports differences that are neither
    drift nor actionable -- an earlier read of this pair did exactly that and reported
    drift that did not exist.
    """
    out = subprocess.run(
        ["git", "ls-files", "-z", "--", prefix],
        cwd=_REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    return sorted(p[len(prefix) :].lstrip("/") for p in out.stdout.split("\0") if p)


def test_repo_skill_mirrors_track_the_same_files():
    """The two skill trees ship the same set of files.

    `CLAUDE.md` tells contributors to edit both copies "or they will drift", and
    nothing has ever checked that. The template's own mirror test compares skill names
    and the presence of each SKILL.md, which two diverged copies would pass.
    """
    claude = _tracked(".claude/skills")
    github = _tracked(".github/skills")
    assert claude, "no tracked files under .claude/skills; this check would pass vacuously"
    assert claude == github, f"skill mirrors track different files: {sorted(set(claude) ^ set(github))}"


def test_repo_skill_mirrors_are_byte_identical():
    """Same files is not enough: the contents must match too.

    A name-level check passes while one copy silently carries different instructions,
    which is the failure mode that matters. Claude Code reads one tree and Copilot the
    other, so divergence means the two assistants are following different rules.
    """
    differing = [
        rel
        for rel in _tracked(".claude/skills")
        if not filecmp.cmp(_REPO / ".claude/skills" / rel, _REPO / ".github/skills" / rel, shallow=False)
    ]
    assert not differing, f"skill mirrors differ in content: {differing}"


_INSTRUCTION_FILES = (Path("CLAUDE.md"), Path(".github/copilot-instructions.md"))


def test_the_agent_instruction_files_are_tracked():
    """Both instruction files must be in version control.

    `CLAUDE.md` was gitignored, so the file telling every assistant how this repo works
    never entered a pull request, was never reviewed, and did not survive a clone. That
    is also why it drifted from its Copilot counterpart with nothing to notice: a file
    outside version control cannot be diffed against anything.
    """
    for rel in _INSTRUCTION_FILES:
        assert (_REPO / rel).is_file(), f"{rel} is missing"
        ignored = subprocess.run(["git", "check-ignore", "-q", str(rel)], cwd=_REPO, capture_output=True, check=False)
        assert ignored.returncode != 0, f"{rel} is gitignored, so it can never be reviewed or tested"


def instruction_body_difference(first, second):
    """Lines present in one instruction body and not the other, ignoring blanks.

    Extracted so the disagreement path can be exercised directly. It is the branch
    that only runs when the two files have already drifted, which is exactly when it
    needs to be right, and exactly when nobody has ever seen it run.
    """
    return (
        [ln for ln in first if ln and ln not in second],
        [ln for ln in second if ln and ln not in first],
    )


def test_the_agent_instruction_files_agree_on_shared_content():
    """The two files carry the same guidance below their titles.

    They diverged by exactly the section instructing that both be kept in step, which
    is the joke that writes itself: the rule lived in only one of the two files it
    governed. Only the top-level heading may differ, since one names its audience.
    """
    bodies = []
    for rel in _INSTRUCTION_FILES:
        lines = (_REPO / rel).read_text(encoding="utf-8").splitlines()
        body = lines[1:] if lines and lines[0].startswith("# ") else lines
        bodies.append((rel, [ln.rstrip() for ln in body]))

    (first_rel, first), (second_rel, second) = bodies
    only_first, only_second = instruction_body_difference(first, second)
    assert not (only_first or only_second), (
        f"{first_rel} and {second_rel} disagree.\n"
        f"  only in {first_rel}: {only_first[:3]}\n"
        f"  only in {second_rel}: {only_second[:3]}"
    )


def test_instruction_files_name_no_path_that_does_not_exist():
    """A path cited as a canonical source must actually be there.

    The instructions claimed `polish-changelog`'s canonical source was a directory
    under `template/`, and that directory exists only on an unmerged branch. Guidance
    that points at nothing sends whoever follows it looking for a file that is not
    there, and quietly licenses editing the wrong copy.
    """
    path_like = re.compile(r"`((?:template/|docs/|tests/|src/|openspec/)[\w./<>{}-]+)`")
    for rel in _INSTRUCTION_FILES:
        text = (_REPO / rel).read_text(encoding="utf-8")
        for cited in sorted(set(path_like.findall(text))):
            if any(ch in cited for ch in "<>{}"):  # pragma: no cover - no current citation is templated
                continue  # a placeholder, not a literal path
            # Tracked, not merely present. Checking existence made this test weaker on
            # a maintainer's machine than in CI: `openspec/` is gitignored, so a cited
            # path under it resolved locally and vanished in a fresh clone. CI caught a
            # citation that pointed at nothing for every reader but the author. Asking
            # git makes both environments agree, and matches what the guidance means.
            tracked = subprocess.run(
                ["git", "ls-files", "--error-unmatch", "--", cited.rstrip("/")],
                cwd=_REPO,
                capture_output=True,
                check=False,
            )
            assert tracked.returncode == 0, (
                f"{rel} cites `{cited}`, which git does not track. Whoever clones this repo will not find it, "
                "even if it exists on the machine the guidance was written on."
            )


def test_instruction_body_difference_reports_each_side():
    """Both directions are reported, so a one-sided read cannot hide a missing section.

    The section instructing that both files be kept in step existed in only one of
    them. A comparison that reported only additions would have called that clean.
    """
    only_first, only_second = instruction_body_difference(["shared", "", "extra-a"], ["shared", "extra-b"])
    assert only_first == ["extra-a"]
    assert only_second == ["extra-b"]
    assert instruction_body_difference(["same", ""], ["same"]) == ([], [])


def test_every_invoked_tool_in_this_repo_is_pinned_and_annotated():
    """Every tool this repo's workflows shell out to is pinned, not just the pinned ones.

    The generated-output half of this pair is in `test_github_workflows.py`, and the
    reason both exist is the reason this file exists at all: a property enforced
    downstream was silently absent upstream. `uvx --from cyclonedx-bom` floated in the
    template for months because the pin assertions quantified over steps that already
    carried a version, so an unpinned tool was not in the set being measured.

    This repo's own release path is smaller (no SBOM, no PyPI upload), but its nox
    invocations are the same class of dependency, and nothing asserted they stay
    pinned once someone adds a new one.
    """
    invocations, lines_by_path = [], {}
    for path in _repo_workflow_paths():
        invocations += find_invocations(path)
        lines_by_path[path.name] = path.read_text(encoding="utf-8").splitlines()

    assert invocations, "no tool invocations found in this repository's workflows; the scan is reading the wrong tree"

    floating = unpinned_invocations(invocations, lines_by_path)
    assert not floating, (
        "tools invoked with no exact version (they resolve to whatever is newest on the day): "
        + ", ".join(f"{i.path}:{i.line} `{i.text}`" for i in floating)
    )

    unreadable = []
    for path in _repo_workflow_paths():
        unreadable += [f"{path.name}:{d}" for d in unreadable_annotations(path)]
    assert not unreadable, "`# renovate:` annotations the preset's manager cannot read: " + ", ".join(unreadable)

    unannotated = [i for i in invocations if i.pinned and not i.annotated]
    assert not unannotated, (
        "pinned tools with no `# renovate:` annotation, so nothing can ever bump them: "
        + ", ".join(f"{i.path}:{i.line} `{i.spec}`" for i in unannotated)
    )


def test_this_repo_authenticates_git_cliff():
    """git-cliff's GitHub API calls are authenticated here too, not only downstream.

    `.git-cliff.toml` enables the GitHub integration, so every changelog run calls the
    API. Anonymous calls share a 60/hour budget with everything else on the runner's
    IP, and git-cliff panics on the resulting 403 rather than degrading to plain
    entries, so the job exits 101, no changelog PR opens, and the pushed tag is left
    with no release behind it. This repo shipped the fix to seven projects while
    carrying the identical defect in its own workflow.
    """
    changelog = _WORKFLOWS / "changelog.yml"
    content = changelog.read_text(encoding="utf-8")
    workflow = yaml.safe_load(content)

    assert (workflow.get("permissions") or {}).get("pull-requests") == "read", (
        "changelog.yml does not grant `pull-requests: read`; git-cliff queries the pulls "
        "endpoint as well as commits, so `contents: read` alone still 403s"
    )
    generate = [
        step
        for job in (workflow.get("jobs") or {}).values()
        for step in (job.get("steps") or [])
        if "git-cliff --config" in str(step.get("run", ""))
    ]
    assert generate, "no git-cliff generate step found in changelog.yml; this check would pass over nothing"
    for step in generate:
        assert "GITHUB_TOKEN" in (step.get("env") or {}), (
            "the git-cliff step has no GITHUB_TOKEN in its env, so its GitHub API calls go out "
            "anonymous and the release fails whenever the shared IP quota is exhausted"
        )
