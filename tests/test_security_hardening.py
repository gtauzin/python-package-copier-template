"""Fail-loud checks for the security controls the template ships.

Each control here is one a green CI run could otherwise hide: a workflow that quietly
regained a broad default token, a paid scanner that silently shipped to a private repo,
a secret-scan job that runs but never gates the merge. These assert the control is
observably present (or absent) in the generated project, so a regression fails a test
rather than passing unnoticed.
"""

WORKFLOW_NAMES = [
    "tests.yml",
    "changelog.yml",
    "publish-release.yml",
    "pr-title.yml",
    "commit-message.yml",
    "nightly.yml",
]


def _read(project_dir, relpath):
    return (project_dir / relpath).read_text(encoding="utf-8")


def test_workflows_default_to_read_only_token(copie):
    """Every generated workflow declares a top-level read-only permissions default.

    A workflow with no top-level ``permissions`` inherits the repository default token
    scope, which can be broad. The read-only default plus per-job opt-in is the
    least-privilege posture.
    """
    result = copie.copy(extra_answers={"include_actions": True})
    workflows = result.project_dir / ".github" / "workflows"
    for name in WORKFLOW_NAMES:
        content = _read(result.project_dir, f".github/workflows/{name}")
        # A top-level (column-0) permissions block granting no more than contents: read.
        assert "\npermissions:\n  contents: read\n" in content, f"{name} has no top-level read-only permissions default"
    assert workflows.exists()


def test_codeql_and_scorecard_ship_for_public(copie):
    """CodeQL and Scorecard ship for public repos (free there)."""
    public = copie.copy(extra_answers={"repo_visibility": "public", "include_actions": True})
    assert (public.project_dir / ".github/workflows/codeql.yml").exists()
    assert (public.project_dir / ".github/workflows/scorecard.yml").exists()


def test_codeql_and_scorecard_absent_for_private(copie):
    """CodeQL and Scorecard are absent for private repos (paid there); ruff S covers SAST.

    A separate test (fresh directory) rather than a second copy into the public project's
    directory: copier's overwrite does not delete files that a new answer set no longer
    generates, so a stale codeql.yml would linger and mask this gate.
    """
    private = copie.copy(
        extra_answers={"repo_visibility": "private", "include_actions": True, "include_codecov": False}
    )
    assert not (private.project_dir / ".github/workflows/codeql.yml").exists()
    assert not (private.project_dir / ".github/workflows/scorecard.yml").exists()


def test_codecov_is_gated_on_include_codecov(copie):
    """Codecov wiring ships only when include_codecov is set.

    Private repos default it off (paid on private) and must not ship a half-wired
    codecov action or a dead coverage badge.
    """
    with_cov = copie.copy(extra_answers={"include_actions": True, "include_codecov": True})
    assert "codecov" in _read(with_cov.project_dir, ".github/workflows/tests.yml")
    assert "codecov.io" in _read(with_cov.project_dir, "README.md")

    without_cov = copie.copy(
        extra_answers={"repo_visibility": "private", "include_actions": True, "include_codecov": False}
    )
    assert "codecov" not in _read(without_cov.project_dir, ".github/workflows/tests.yml")
    assert "codecov.io" not in _read(without_cov.project_dir, "README.md")


def test_bandit_ruleset_is_selected(copie):
    """The generated ruff config selects the S (flake8-bandit) security ruleset."""
    result = copie.copy()
    pyproject = _read(result.project_dir, "pyproject.toml")
    # The select list carries the S ruleset (the always-on SAST floor).
    select = pyproject.split("select = [", 1)[1].split("]", 1)[0]
    assert '"S"' in select, "ruff S (flake8-bandit) is not selected in the generated pyproject"


def test_gitleaks_hook_and_gating_ci_job(copie):
    """gitleaks runs as a pre-commit hook and as a merge-gating CI job.

    The hook prevents secrets locally; the CI job is the un-bypassable backstop, and it
    must be a dependency of the ci-passed roll-up or it runs without blocking merges.
    """
    result = copie.copy(extra_answers={"include_actions": True})
    precommit = _read(result.project_dir, ".pre-commit-config.yaml")
    assert "gitleaks/gitleaks" in precommit, "no gitleaks pre-commit hook"

    tests_yml = _read(result.project_dir, ".github/workflows/tests.yml")
    assert "secret-scan:" in tests_yml, "no gitleaks CI job"
    assert "gitleaks detect" in tests_yml

    # The job must be a dependency of the single required roll-up, or it never gates.
    needs_block = tests_yml.split("ci-passed:", 1)[1].split("runs-on:", 1)[0]
    assert "- secret-scan" in needs_block, "secret-scan is not in the ci-passed roll-up needs list"


def test_governance_files_ship_for_every_repo(copie):
    """SECURITY.md and CODEOWNERS ship regardless of visibility."""
    for answers in ({}, {"repo_visibility": "private", "include_codecov": False}):
        result = copie.copy(extra_answers=answers)
        assert (result.project_dir / "SECURITY.md").exists()
        assert (result.project_dir / "CODEOWNERS").exists()


def test_publish_flow_is_self_contained_with_sbom(copie):
    """The publish path builds and publishes in one run, with no third-party broker, plus an SBOM."""
    result = copie.copy(extra_answers={"include_actions": True})
    publish = _read(result.project_dir, ".github/workflows/publish-release.yml")
    # No third-party cross-workflow artifact download in the release path.
    assert "dawidd6" not in publish
    # Native same-run artifact passing.
    assert "actions/upload-artifact" in publish
    assert "actions/download-artifact" in publish
    # SBOM produced and attached.
    assert "cyclonedx" in publish.lower()
    assert "sbom" in publish.lower()


def test_changelog_uses_app_token_not_pat(copie):
    """The changelog PR is opened with a short-lived GitHub App token, not a long-lived PAT."""
    result = copie.copy(extra_answers={"include_actions": True})
    changelog = _read(result.project_dir, ".github/workflows/changelog.yml")
    assert "create-github-app-token" in changelog
    assert "CHANGELOG_AUTOMATION_TOKEN" not in changelog


def test_publish_action_is_not_a_branch_ref(copie):
    """The PyPI publish action is pinned to a tag, not the mutable @release/v1 branch."""
    result = copie.copy(extra_answers={"include_actions": True})
    publish = _read(result.project_dir, ".github/workflows/publish-release.yml")
    assert "gh-action-pypi-publish@release/v1" not in publish
    assert "gh-action-pypi-publish@v" in publish
