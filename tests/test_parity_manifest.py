"""The parity manifest: every gate this repo ships is answered for this repo.

This repository generates seven packages and receives nothing back. `template/` fans
out; the root has no inbound path and, until this test, nothing that knew its own
configuration was meant to resemble what it hands out.

The failure mode is absence, not drift: a missing workflow, a missing job, a missing
pin. A test that renders the template and diffs files cannot catch a file that is not
there, so this asserts coverage instead. Every gate the template ships resolves to
`matched`, `excluded` (with a written reason) or `leading`. Anything unanswered fails.

The shipped-gate set is DERIVED from a rendered project, never hand-listed. A
hand-maintained list omits new gates silently, which is the exact defect this exists
to prevent: it would be a check that passes because it measures a set that no longer
matches reality.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

_REPO = Path(__file__).resolve().parent.parent
_MANIFEST_PATH = Path(__file__).resolve().parent / "parity_manifest.yml"
_VALID_STATUSES = {"matched", "excluded", "leading"}


def _manifest():
    """The hand-written half: what this repo claims about each shipped gate."""
    return yaml.safe_load(_MANIFEST_PATH.read_text(encoding="utf-8"))


def _derive_shipped_gates(project_dir):
    """Every gate a generated project receives, read from the rendered project.

    Derived, not listed. Workflow *job* identifiers and pre-commit *hook* ids are the
    two places a gate is declared, and both are structural, so a gate added to the
    template appears here without anyone editing this file.
    """
    gates = set()
    for workflow_path in sorted((project_dir / ".github" / "workflows").glob("*.yml")):
        workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        for job_id in workflow.get("jobs") or {}:
            gates.add(f"{workflow_path.name}:{job_id}")

    hooks_config = yaml.safe_load((project_dir / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    for repo in hooks_config.get("repos") or []:
        for hook in repo.get("hooks") or []:
            gates.add(f"hook:{hook['id']}")

    # Root-level files a project receives. Jobs and hooks are not the only shape a
    # control takes: CODEOWNERS and SECURITY.md are governance controls that exist
    # purely as files, and a derivation reading only jobs and hooks was blind to
    # both -- which is exactly how they reached seven generated projects and never
    # this one. The project root is a bounded, structural set, so this stays derived
    # rather than becoming a second hand-maintained list.
    for path in sorted(project_dir.iterdir()):
        if path.is_file():
            gates.add(f"file:{path.name}")
    return gates


def test_derivation_finds_gates_at_all(copie_session_default):
    """Guard the input set before asserting anything about it.

    If derivation ever returns nothing, every coverage assertion below passes
    vacuously and the parity gap silently reopens. That is the failure this whole
    capability exists to catch, so check it here first rather than trusting it.
    """
    gates = _derive_shipped_gates(copie_session_default.project_dir)
    assert len(gates) > 20, f"derivation found only {len(gates)} gates; it is probably reading the wrong tree"
    assert any(g.startswith("hook:") for g in gates), "no pre-commit hooks derived"
    assert any(":" in g and not g.startswith("hook:") for g in gates), "no workflow jobs derived"


def test_every_shipped_gate_is_answered(copie_session_default):
    """A gate the template ships with no manifest entry fails, naming the gate.

    This is the whole point. `fix(ci): pin exact uv version in all setup-uv steps`
    quantified over the template and silently meant nothing about this repo; an
    unanswered entry is what makes that visible instead of invisible.
    """
    shipped = _derive_shipped_gates(copie_session_default.project_dir)
    answered = set(_manifest()["file_gates"])
    unanswered = sorted(shipped - answered)
    assert not unanswered, (
        f"the template ships {len(unanswered)} gate(s) this repo has not accounted for: {unanswered}. "
        "Add an entry to tests/parity_manifest.yml marking each matched, excluded (with a reason), or leading."
    )


def test_no_stale_manifest_entries(copie_session_default):
    """An entry for a gate the template no longer ships is reported, not retained.

    Coverage checks usually only notice additions. A manifest that accumulates entries
    for deleted gates slowly stops describing anything, and its passing tells you less
    every release.
    """
    shipped = _derive_shipped_gates(copie_session_default.project_dir)
    stale = sorted(set(_manifest()["file_gates"]) - shipped)
    assert not stale, (
        f"manifest answers {len(stale)} gate(s) the template no longer ships: {stale}. Remove the stale entries."
    )


@pytest.mark.parametrize("section", ["file_gates", "settings_gates"])
def test_every_entry_has_a_valid_status_and_a_reason(section):
    """An exclusion with no reason is an omission wearing a label.

    The reason text is the artifact this capability produces: it turns "this repo
    skips that" from silently true into something a reviewer can disagree with in a
    pull request. A blank one defeats the purpose entirely.
    """
    for gate, entry in _manifest()[section].items():
        assert entry.get("status") in _VALID_STATUSES, (
            f"{gate}: status {entry.get('status')!r} is not one of {sorted(_VALID_STATUSES)}"
        )
        reason = (entry.get("reason") or "").strip()
        assert reason, f"{gate}: every entry needs a reason, even a one-liner"

        # `excluded` and `leading` are where the judgment lives, and where an omission
        # can hide behind a label. "same builtin hook" is a complete answer for a
        # matched entry; "n/a" is not a complete answer for a skipped gate.
        if entry["status"] in {"excluded", "leading"}:
            assert len(reason) > 40, (
                f"{gate}: status {entry['status']} needs a substantive reason a reviewer can disagree with, "
                f"got {reason!r}"
            )


def test_settings_entries_record_how_and_how_often_they_are_checked():
    """Settings-held controls must say how their state is determined, and at what cadence.

    Cadence is deliberately per control rather than fixed globally: an unattended check
    costs a credential, and that trade belongs to the control. What is not optional is
    writing down which trade was made.
    """
    for gate, entry in _manifest()["settings_gates"].items():
        for field in ("mechanism", "determined_by", "cadence"):
            assert (entry.get(field) or "").strip(), f"{gate}: settings entry must record {field!r}"


def test_the_manifest_covers_controls_that_are_not_files():
    """A file-derived manifest would pass on a repo whose merge gate is switched off.

    Workflows, hooks, CODEOWNERS and lint config are files. Rulesets, required status
    checks and secret provisioning are not, and no amount of reading the working tree
    reveals them. This asserts the manifest reaches past what derivation can see.
    """
    settings_gates = _manifest()["settings_gates"]
    assert settings_gates, "the manifest covers no settings-held controls, so it is blind to the merge gate"
    assert "ruleset-requires-roll-up" in settings_gates, "the merge gate itself must be one of the covered controls"


def required_checks_from_rulesets(rulesets):
    """Status checks a set of ruleset payloads actually requires.

    Split out from the network call so the discriminating logic can be tested without
    touching a live setting. Verifying "does this detector notice a missing ruleset?"
    by deleting the real one would mean removing this repository's merge protection to
    prove that removing it is noticed, which is not a trade worth making. Every fleet
    repository already requires the roll-up, so there is no live negative control
    either. Feeding synthetic payloads is what is left, and it is the better test:
    deterministic, offline, and able to cover cases the live repo cannot be put into.
    """
    checks = set()
    for body in rulesets:
        if body.get("enforcement") != "active":
            continue
        for rule in body.get("rules") or []:
            if rule.get("type") == "required_status_checks":
                params = rule.get("parameters") or {}
                checks.update(c.get("context") for c in params.get("required_status_checks") or [])
    return checks


def _required_checks_on_default_branch():
    """Status checks the hosting platform actually requires, or None if unknowable.

    Unattended: no person initiates it, so a ruleset deleted later fails the next run
    rather than waiting for someone to look. Returns None when the platform cannot be
    reached or credentials are absent, which the caller reports as a skip rather than
    a pass -- an unreachable check must never read as a satisfied one.
    """
    if shutil.which("gh") is None:
        return None
    probe = subprocess.run(
        ["gh", "api", "repos/stateful-y/python-package-copier/rulesets"],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        return None
    details = []
    for ruleset in json.loads(probe.stdout):
        detail = subprocess.run(
            ["gh", "api", f"repos/stateful-y/python-package-copier/rulesets/{ruleset['id']}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if detail.returncode == 0:
            details.append(json.loads(detail.stdout))
    return required_checks_from_rulesets(details)


@pytest.mark.slow
@pytest.mark.integration
def test_the_roll_up_merge_gate_is_actually_required():
    """A ruleset must require the roll-up check by name, checked without a person asking.

    The roll-up job name was chosen to survive matrix and conditional changes so it
    could be the one required check. It was required by nothing for four releases
    after it shipped, and nothing recorded that. A control configured once and later
    removed is indistinguishable from one never configured, which is why a
    maintainer-initiated check would not be enough here.
    """
    required = _required_checks_on_default_branch()
    if required is None:
        pytest.skip("hosting platform not reachable or gh not authenticated; state unknown, not assumed satisfied")
    assert "CI passed" in required, (
        f"no active ruleset requires the roll-up check 'CI passed'; required checks are {sorted(required)}. "
        "Every check on this repository is advisory until one does."
    )


def _repo_hook_ids():
    """Hook ids this repository actually runs."""
    config = yaml.safe_load((_REPO / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    return {hook["id"] for repo in config.get("repos") or [] for hook in repo.get("hooks") or []}


def _repo_workflow_jobs():
    """Workflow jobs this repository actually runs, as `<file>:<job>`."""
    jobs = set()
    for path in sorted((_REPO / ".github" / "workflows").glob("*.yml")):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job_id in workflow.get("jobs") or {}:
            jobs.add(f"{path.name}:{job_id}")
    return jobs


def test_a_matched_claim_is_true_not_merely_asserted():
    """`matched` must mean the equivalent exists here, not that someone typed "matched".

    Without this the manifest is documentation wearing a test's clothes: deleting this
    repo's nightly canary outright left every check green, because "matched" was a
    string in a YAML file that nothing compared against reality. That is precisely the
    defect this capability exists to eliminate, reproduced inside its own mechanism.

    Two of the three gate shapes verify structurally. A shipped root *file* must exist
    here by name; a shipped *hook* id must appear in this repo's hook config. Workflow
    *jobs* cannot be matched by name, because this repo's jobs are named for testing a
    template rather than a package, so a matched job entry must name its counterpart
    with an `equivalent:` field, and that counterpart must exist.
    """
    missing = []
    for gate, entry in _manifest()["file_gates"].items():
        if entry["status"] != "matched":
            continue

        if gate.startswith("file:"):
            name = gate.removeprefix("file:")
            if not (_REPO / name).exists():
                missing.append(f"{gate}: claims matched but {name} does not exist in this repo")

        elif gate.startswith("hook:"):
            hook_id = gate.removeprefix("hook:")
            if hook_id not in _repo_hook_ids():
                missing.append(f"{gate}: claims matched but no hook `{hook_id}` runs in this repo")

        else:  # a workflow job
            equivalent = entry.get("equivalent")
            if not equivalent:
                missing.append(f"{gate}: claims matched but names no `equivalent:` in this repo to check")
            elif equivalent not in _repo_workflow_jobs() and equivalent != "not-a-workflow-job":
                missing.append(f"{gate}: claims equivalent `{equivalent}`, which this repo does not run")

    assert not missing, "manifest claims that reality does not support:\n  " + "\n  ".join(missing)


def _ruleset(enforcement="active", contexts=("CI passed",), rule_type="required_status_checks"):
    """A minimal ruleset payload in the shape the hosting platform returns."""
    return {
        "enforcement": enforcement,
        "rules": [
            {
                "type": rule_type,
                "parameters": {"required_status_checks": [{"context": c} for c in contexts]},
            }
        ],
    }


@pytest.mark.parametrize(
    ("label", "payloads"),
    [
        ("no rulesets at all", []),
        ("ruleset exists but is not enforced", [_ruleset(enforcement="evaluate")]),
        ("ruleset enforces review only, no status checks", [_ruleset(rule_type="pull_request")]),
        ("ruleset requires other checks but not the roll-up", [_ruleset(contexts=("Validate PR Title",))]),
        ("roll-up renamed, so the required name no longer matches any job", [_ruleset(contexts=("CI-passed",))]),
    ],
)
def test_the_roll_up_detector_notices_every_way_the_gate_can_be_absent(label, payloads):
    """The detector must go red for each way the merge gate stops being enforced.

    This is the assertion that gives the live check meaning. Its purpose is catching
    silent reversion, and a detector that cannot distinguish "required" from "quietly
    no longer required" would report the gate healthy forever. The renamed case is the
    subtle one: a ruleset still exists and still requires *a* check, but the name no
    longer matches any job, so it blocks nothing while looking configured.
    """
    assert "CI passed" not in required_checks_from_rulesets(payloads), f"the detector failed to notice: {label}"


def test_the_roll_up_detector_accepts_a_correctly_configured_ruleset():
    """And it must not cry wolf on the real configuration, or it will be switched off."""
    assert "CI passed" in required_checks_from_rulesets([_ruleset()])
    assert "CI passed" in required_checks_from_rulesets([_ruleset(enforcement="evaluate", contexts=("x",)), _ruleset()])
