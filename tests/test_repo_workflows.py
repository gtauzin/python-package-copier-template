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

_REPO = Path(__file__).resolve().parent.parent
_WORKFLOWS = _REPO / ".github" / "workflows"
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


def _copier_default_uv_version():
    """The uv version copier.yml pins for generated projects.

    Read rather than hardcoded so this repo's pin is checked against the same source of
    truth the fleet gets, and a bump in one place fails here instead of drifting.
    """
    config = yaml.safe_load((_REPO / "copier.yml").read_text(encoding="utf-8"))
    return str(config["uv_version"]["default"])


def test_the_assertion_reads_this_repository_not_generated_output():
    """This test file's inputs are the root workflows, which is the whole point.

    The generated-output test passed for years while this repo went unchecked. If this
    ever collects nothing, the pin assertions below would pass vacuously and the gap
    would silently reopen, so assert the inputs before asserting anything about them.
    """
    assert _WORKFLOWS.is_dir(), "this repository has no .github/workflows to check"
    assert _repo_workflow_paths(), "no workflows found; the pin assertions would pass over an empty set"
    assert _setup_uv_steps(), "no astral-sh/setup-uv steps found in this repository's workflows"


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
    assert versions == {_copier_default_uv_version()}, (
        f"this repo pins uv {sorted(versions)} but copier.yml ships {_copier_default_uv_version()} to projects"
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
    if first != second:
        only_first = [ln for ln in first if ln and ln not in second]
        only_second = [ln for ln in second if ln and ln not in first]
        raise AssertionError(
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
            if any(ch in cited for ch in "<>{}"):
                continue  # a placeholder, not a literal path
            target = _REPO / cited.rstrip("/")
            assert target.exists(), f"{rel} cites `{cited}`, which does not exist on this branch"
