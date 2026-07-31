"""Find every tool a workflow shells out to, pinned or not.

The `setup-uv` assertions in `test_repo_workflows.py` and `test_github_workflows.py`
quantify over steps that already carry a `version:` input. That shape cannot see a tool
that was never pinned at all, which is precisely how `uvx --from cyclonedx-bom` reached
seven repos: it resolved to the newest release on every run, and broke every generated
project's release on the day cyclonedx-bom 7.0 removed a flag the step was passing. The
check passed throughout, because an unpinned invocation was not in the set it measured.

So this enumerates *invocations* and reports each one's pin status, rather than
enumerating pins. An unpinned tool is a failure, not an absence.

Text-based rather than YAML-based, for two reasons. The `# renovate:` marker is a
comment, so a parser drops it and a structural check cannot see it missing. And these
invocations live inside `run:` script bodies, which are opaque strings to a YAML parser.
"""

import re
from dataclasses import dataclass

# `uvx --from <spec> <cmd>`, `uvx <spec>`, and `uv tool install <spec>`. The spec is
# everything up to the first whitespace, so `nox@2026.7.11` and `twine==7.0.0` both
# arrive intact and a bare `nox` arrives unpinned.
_FROM = re.compile(r"\buvx\s+(?:--\S+\s+)*--from\s+(?P<spec>\S+)")
_UVX = re.compile(r"\buvx\s+(?!--from\b)(?:--\S+\s+)*(?P<spec>\S+)")
_INSTALL = re.compile(r"\buv\s+tool\s+install\s+(?:--\S+\s+)*(?P<spec>\S+)")

# A pinned spec carries an exact version, either `pkg==1.2.3` (PyPI) or `pkg@1.2.3`
# (uv's tool syntax). A range or a bare name is not a pin.
_PINNED = re.compile(r"^[A-Za-z0-9._-]+(==|@)\d[\w.+-]*$")


@dataclass(frozen=True)
class Invocation:
    """One tool invocation found in a workflow's shell body."""

    path: str
    line: int
    spec: str
    text: str
    annotated: bool

    @property
    def name(self):
        """The tool name, with any version stripped."""
        return re.split(r"==|@", self.spec, maxsplit=1)[0]

    @property
    def pinned(self):
        """True when the spec carries an exact version."""
        return bool(_PINNED.match(self.spec))


def _job_start_lines(lines):
    """Line indices where a new job begins, so `uv tool install` scope can be bounded.

    A tool installed in one job is not on PATH in another, so a pin in job A must not
    excuse a bare invocation in job B.
    """
    return [i for i, line in enumerate(lines) if re.match(r"^  [A-Za-z0-9_-]+:\s*$", line)]


def find_invocations(path):
    """Every tool invocation in one workflow file, with its pin and annotation status.

    Lines that are themselves comments are skipped: the changelog workflow explains in
    prose why `uvx prek` would float, and a scan that matched prose would fail on the
    documentation of the very rule it enforces.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    found = []
    for i, line in enumerate(lines):
        if line.strip().startswith("#"):
            continue
        for pattern in (_FROM, _UVX, _INSTALL):
            match = pattern.search(line)
            if not match:
                continue
            # The annotation sits above the step's `run:` key, which may be several
            # lines up when the body is a block scalar.
            window = lines[max(0, i - 6) : i]
            found.append(
                Invocation(
                    path=path.name,
                    line=i + 1,
                    spec=match.group("spec"),
                    text=line.strip(),
                    annotated=any(w.strip().startswith("# renovate:") for w in window),
                )
            )
            break
    return found


def unpinned(invocations, lines_by_path):
    """Invocations with no exact version, excusing those pinned by a preceding install.

    `uv tool run` (`uvx`) reuses an already-installed tool unless `--isolated` is
    passed, so `uvx nox -s fix` after `uv tool install nox==2026.7.11` in the same job
    runs the pinned nox. Flagging it would be a false positive that teaches people to
    silence the check.
    """
    offenders = []
    for inv in invocations:
        if inv.pinned:
            continue
        starts = _job_start_lines(lines_by_path[inv.path])
        job_start = max((s for s in starts if s < inv.line), default=0)
        installed = {
            other.name
            for other in invocations
            if other.path == inv.path and other.pinned and job_start < other.line < inv.line
        }
        if inv.name not in installed:
            offenders.append(inv)
    return offenders
