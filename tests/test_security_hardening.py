"""Fail-loud checks for the security controls the template ships.

Each control here is one a green CI run could otherwise hide: a workflow that quietly
regained a broad default token, a paid scanner that silently shipped to a private repo,
a secret-scan job that runs but never gates the merge. These assert the control is
observably present (or absent) in the generated project, so a regression fails a test
rather than passing unnoticed.
"""

from _workflow_expressions import injection_sites

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


def test_codeql_analyses_source_and_not_the_test_harness(copie):
    """CodeQL ships a config scoping the scan to shipped code, and the workflow reads it.

    Presence of the file is not enough and neither is the `config-file` input alone: a
    config that no `init` step points at is inert, and an input pointing at a path that
    does not ship makes the whole workflow fail. Both ends are asserted, plus the actual
    exclusions -- without them the default suite reads test assertions as production
    code paths and reports false positives that recur faster than they can be dismissed.
    """
    result = copie.copy(extra_answers={"repo_visibility": "public", "include_actions": True, "include_examples": True})
    config = result.project_dir / ".github/codeql/codeql-config.yml"
    assert config.exists(), "no CodeQL config; the default suite would scan tests and examples"

    workflow = _read(result.project_dir, ".github/workflows/codeql.yml")
    assert "config-file: ./.github/codeql/codeql-config.yml" in workflow, (
        "codeql.yml does not point at the config, so the config changes nothing"
    )

    ignored = config.read_text(encoding="utf-8")
    assert "- tests" in ignored
    assert "- examples" in ignored


def test_codeql_config_is_absent_wherever_codeql_is(copie):
    """No orphan config where no CodeQL workflow runs, and none for a project without examples.

    A config for a workflow that does not ship is dead weight that later reads as a
    control the project has. The examples exclusion is likewise conditional: listing a
    directory the project does not generate would document a scope decision that was
    never made.
    """
    private = copie.copy(
        extra_answers={"repo_visibility": "private", "include_actions": True, "include_codecov": False}
    )
    assert not (private.project_dir / ".github/codeql").exists()

    no_examples = copie.copy(
        extra_answers={"repo_visibility": "public", "include_actions": True, "include_examples": False}
    )
    config = _read(no_examples.project_dir, ".github/codeql/codeql-config.yml")
    assert "- tests" in config
    assert "- examples" not in config


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


def test_no_untrusted_expression_reaches_a_shell(copie):
    """No generated workflow substitutes `${{ github.event.* }}` into a script body.

    An expression is spliced into the script before bash parses it, so a PR title
    carrying shell metacharacters executes. `publish-release.yml` did exactly this, in
    the job holding ``contents: write`` that gates publication, and shipped it to seven
    projects; the value now passes through ``env:``, where the shell reads it as data.

    Quantified over every generated workflow rather than the one that was broken, and
    over the whole of each one rather than the release job, so the next workflow to
    interpolate a PR body or an issue title fails here instead of on a Scorecard run.
    """
    result = copie.copy(extra_answers={"repo_visibility": "public", "include_actions": True})
    workflows = sorted((result.project_dir / ".github" / "workflows").glob("*.yml"))
    assert workflows, "no workflows generated; this assertion would pass over an empty set"

    sites = [site for path in workflows for site in injection_sites(path)]
    assert not sites, "untrusted expressions substituted into a script body (move them to `env:`): " + ", ".join(
        f"{name}:{line} {expr}" for name, line, expr in sites
    )


def test_release_tag_is_parsed_from_the_environment(copie):
    """The release job reads the PR title from `env:`, and never re-interpolates it.

    The generic scan above would stay green if someone "fixed" this by adding an `env:`
    block and leaving the `${{ }}` in the script, or by dropping the title parsing
    entirely. This pins the specific shape the release path depends on.
    """
    result = copie.copy(extra_answers={"include_actions": True})
    publish = _read(result.project_dir, ".github/workflows/publish-release.yml")

    assert "PR_TITLE: ${{ github.event.pull_request.title }}" in publish, (
        "the PR title no longer reaches the release job through the environment"
    )
    assert 'PR_TITLE="${{' not in publish, "the PR title is still interpolated into the shell"
    assert '"$PR_TITLE"' in publish, "nothing reads the PR title, so the version can no longer be found"


def test_publish_action_is_not_a_branch_ref(copie):
    """The PyPI publish action is pinned to a tag, not the mutable @release/v1 branch."""
    result = copie.copy(extra_answers={"include_actions": True})
    publish = _read(result.project_dir, ".github/workflows/publish-release.yml")
    assert "gh-action-pypi-publish@release/v1" not in publish
    assert "gh-action-pypi-publish@v" in publish


def _floor(pyproject, package):
    """The `>=` floor the generated pyproject declares for one package, as a tuple."""
    spec = next(line.split('"')[1] for line in pyproject.splitlines() if line.strip().startswith(f'"{package}>='))
    return tuple(int(part) for part in spec.split(">=", 1)[1].split("."))


def test_docs_dependencies_clear_the_published_advisories(copie):
    """pymdown-extensions floors above both advisories, and marimo floors high enough to allow it.

    pymdown-extensions 10.x carries a path traversal (GHSA-9xwg-3r6f-jcx2, fixed in
    11.0.0) and 11.0.0 a ReDoS (GHSA-gm37-52c6-37mw, fixed in 11.0.1). Both sat in five
    generated repositories, unreachable, because the examples group's marimo capped
    pymdown-extensions at <11 and nothing rechecked that cap after the advisories landed.

    Asserted as a version comparison rather than a string match, so moving the floor
    forward passes and moving it back fails. The two floors are checked together because
    they are one decision: lowering the marimo floor silently reintroduces the CVEs by
    making the pymdown floor unresolvable for any project with examples.
    """
    result = copie.copy(extra_answers={"include_examples": True})
    pyproject = _read(result.project_dir, "pyproject.toml")

    assert _floor(pyproject, "pymdown-extensions") >= (11, 0, 1), (
        "pymdown-extensions floors below 11.0.1, which is vulnerable to GHSA-9xwg-3r6f-jcx2 "
        "(path traversal) or GHSA-gm37-52c6-37mw (ReDoS)"
    )
    assert _floor(pyproject, "marimo") >= (0, 23, 16), (
        "marimo floors below 0.23.16, whose pymdown-extensions<11 cap makes the security "
        "floor above unresolvable for a project with examples"
    )


def test_security_posture_page_present_and_in_nav(copie):
    """A user-facing security posture page ships and is listed in the docs nav."""
    result = copie.copy()
    page = result.project_dir / "docs/pages/explanation/security.md"
    assert page.exists(), "no security posture explanation page"
    assert "trusted-publishing" in page.read_text(encoding="utf-8").lower() or "OIDC" in page.read_text(
        encoding="utf-8"
    )
    nav = _read(result.project_dir, "mkdocs.yml")
    assert "pages/explanation/security.md" in nav, "security page missing from the docs nav"


def test_security_page_gates_public_only_controls(copie):
    """The page presents CodeQL/Scorecard as active for public repos and not for private."""
    public = _read(
        copie.copy(extra_answers={"repo_visibility": "public"}).project_dir,
        "docs/pages/explanation/security.md",
    )
    assert "Deep analysis (CodeQL)" in public
    assert "independent security grade" in public

    private = _read(
        copie.copy(extra_answers={"repo_visibility": "private", "include_codecov": False}).project_dir,
        "docs/pages/explanation/security.md",
    )
    assert "Deep analysis (CodeQL)" not in private
    assert "independent security grade" not in private
    # The page still describes the controls a private repo DOES run.
    assert "Static security analysis" in private
    assert "Secret scanning" in private


def test_codeowners_uses_a_valid_owner(copie):
    """CODEOWNERS ships a concrete owner, not a bare org name GitHub rejects."""
    result = copie.copy()
    codeowners = _read(result.project_dir, "CODEOWNERS")
    owner_line = next(line for line in codeowners.splitlines() if line.startswith("*"))
    owner = owner_line.split()[1]
    assert owner.startswith("@"), "code owner should be an @user or @org/team"
    # A bare "@org" with no team is the invalid form; a user handle or @org/team is fine.
    assert owner != "@" and len(owner) > 1
