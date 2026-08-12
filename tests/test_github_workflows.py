"""Comprehensive tests for GitHub Actions workflows in generated projects.

This test module validates:
- Workflow file generation based on include_actions option
- Consistent uv setup across all workflows
- Workflow triggers, permissions, and job configurations
- Integration between workflows (tests, publish, changelog, nightly)
"""


class TestWorkflowGeneration:
    """Test that workflows are generated correctly based on options."""

    def test_workflows_included_when_enabled(self, copie):
        """Test that all expected workflows exist when include_actions=True."""
        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        workflows_dir = result.project_dir / ".github" / "workflows"
        assert workflows_dir.is_dir()

        expected_workflows = [
            "tests.yml",
            "publish-release.yml",
            "changelog.yml",
            "nightly.yml",
            "pr-title.yml",
        ]

        for workflow_file in expected_workflows:
            workflow_path = workflows_dir / workflow_file
            assert workflow_path.is_file(), f"Missing workflow: {workflow_file}"

    def test_workflows_excluded_when_disabled(self, copie):
        """Test that no workflows exist when include_actions=False."""
        result = copie.copy(extra_answers={"include_actions": False})
        assert result.exit_code == 0

        workflows_dir = result.project_dir / ".github" / "workflows"
        # .github directory should not exist or workflows should be empty
        if workflows_dir.exists():
            assert len(list(workflows_dir.iterdir())) == 0


class TestTestsWorkflow:
    """Test the tests.yml workflow configuration."""

    def test_tests_workflow_structure(self, copie):
        """Test tests.yml has correct structure and jobs."""
        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        workflow_path = result.project_dir / ".github" / "workflows" / "tests.yml"
        workflow_content = workflow_path.read_text(encoding="utf-8")

        # Use string-based validation since GitHub Actions YAML has expressions
        # that cannot be parsed by standard YAML parsers
        assert "name:" in workflow_content
        assert "test" in workflow_content.lower() or "ci" in workflow_content.lower()

        # Check triggers
        assert "on:" in workflow_content
        assert "push:" in workflow_content or "pull_request:" in workflow_content

        # Check jobs
        assert "jobs:" in workflow_content

    def test_tests_workflow_uses_uv(self, copie):
        """Test that tests workflow uses uv for dependency management."""
        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        workflow_path = result.project_dir / ".github" / "workflows" / "tests.yml"
        workflow_content = workflow_path.read_text(encoding="utf-8")

        # Should use uv action or install uv
        assert "astral-sh/setup-uv" in workflow_content or "uv" in workflow_content

        # Should install nox via uv tool
        assert "uv tool install nox" in workflow_content or "uvx nox" in workflow_content

    def test_tests_workflow_matrix_strategy(self, copie):
        """Test that tests workflow uses matrix for Python versions."""
        result = copie.copy(extra_answers={"include_actions": True, "min_python_version": "3.11"})
        assert result.exit_code == 0

        workflow_path = result.project_dir / ".github" / "workflows" / "tests.yml"
        workflow_content = workflow_path.read_text(encoding="utf-8")

        # Use string-based validation since GitHub Actions YAML has expressions
        assert "strategy:" in workflow_content
        assert "matrix:" in workflow_content
        assert "python-version:" in workflow_content or "python:" in workflow_content

    def test_tests_workflow_includes_doctest(self, copie):
        """Test that tests workflow includes test_docstrings job."""
        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        workflow_path = result.project_dir / ".github" / "workflows" / "tests.yml"
        workflow_content = workflow_path.read_text(encoding="utf-8")

        # Should have test_docstrings job or step
        assert "test_docstrings" in workflow_content.lower()

    def test_tests_workflow_includes_examples_when_enabled(self, copie):
        """Test that tests workflow includes examples job when enabled."""
        result = copie.copy(extra_answers={"include_actions": True, "include_examples": True})
        assert result.exit_code == 0

        workflow_path = result.project_dir / ".github" / "workflows" / "tests.yml"
        workflow_content = workflow_path.read_text(encoding="utf-8")

        # Should have examples job or test_examples
        assert "example" in workflow_content.lower()

    def test_tests_workflow_excludes_examples_when_disabled(self, copie):
        """Test that tests workflow excludes examples when disabled."""
        result = copie.copy(extra_answers={"include_actions": True, "include_examples": False})
        assert result.exit_code == 0

        workflow_path = result.project_dir / ".github" / "workflows" / "tests.yml"
        workflow_content = workflow_path.read_text(encoding="utf-8")

        # Should NOT have examples-related content
        assert "test_examples" not in workflow_content and "run-examples" not in workflow_content

    def test_tests_workflow_compat_job_disabled(self, copie):
        """Test that test-compat job is disabled until pins are defined."""
        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        workflow_path = result.project_dir / ".github" / "workflows" / "tests.yml"
        workflow_content = workflow_path.read_text(encoding="utf-8")

        assert "if: false  # disabled until pins are defined" in workflow_content
        assert 'pins: ["placeholder"]' in workflow_content


class TestPublishWorkflow:
    """Test the publish-release.yml workflow."""

    def test_approval_gate_precedes_every_outward_facing_effect(self, copie):
        """Nothing is public until the PyPI upload has succeeded.

        The `pypi` environment gate exists so a human can stop a release. It used to sit
        only on the last job, so `create-release` published a public GitHub Release,
        with the wheels, sdist and SBOM attached, before the approval was ever
        requested. By the time anyone was asked, rejecting cost more than approving:
        deleting a release does not un-download it or retract its notifications, and the
        repo is left advertising a version that never reached PyPI.

        The fix is ordering, so this asserts ordering: the release is created as a
        draft (maintainer-visible, so artifacts can still be inspected while the gate is
        pending) and undrafted by a job that runs only after the upload succeeds.
        """
        import yaml

        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        workflow_path = result.project_dir / ".github" / "workflows" / "publish-release.yml"
        content = workflow_path.read_text(encoding="utf-8")
        jobs = yaml.safe_load(content)["jobs"]

        gated = [name for name, body in jobs.items() if (body.get("environment") or {})]
        assert gated == ["pypi-publish"], f"expected the pypi upload to be the gated job, found {gated}"

        assert "--draft \\" in content or "--draft\n" in content, (
            "the GitHub Release is not created as a draft, so it goes public before the approval gate"
        )

        assert "finalize-release" in jobs, "no finalize-release job, so a drafted release would never be published"
        needs = jobs["finalize-release"].get("needs") or []
        assert "pypi-publish" in needs, (
            f"finalize-release does not wait on pypi-publish (needs: {needs}), so the release could be "
            "made public before or without the upload succeeding"
        )
        assert "--draft=false" in content, "finalize-release never undrafts the release"

        # The undraft must not itself be gated on anything the approval could bypass.
        assert jobs["finalize-release"].get("environment") in (None, {}), (
            "finalize-release carries its own environment gate, which would strand approved releases as drafts"
        )

    def test_changelog_generation_is_authenticated(self, copie):
        """git-cliff's GitHub API calls carry a token.

        `.git-cliff.toml` enables the GitHub integration, so every run calls the API to
        attach PR links and @usernames. Anonymous, that is 60 requests/hour shared
        across every job on the runner's IP, and git-cliff panics on the resulting 403
        instead of degrading to plain entries: exit 101, no changelog PR, and a pushed
        tag with no release behind it. It failed roughly one run in ten, and the tenth
        was a release.
        """
        import yaml

        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        workflow_path = result.project_dir / ".github" / "workflows" / "changelog.yml"
        workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))

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
        assert generate, "no git-cliff generate step found; this check would pass over nothing"
        for step in generate:
            env = step.get("env") or {}
            assert "GITHUB_TOKEN" in env, (
                "the git-cliff step has no GITHUB_TOKEN in its env, so its API calls go out anonymous "
                "and the release fails whenever the shared runner IP has exhausted its quota"
            )
            assert "app-token" not in str(env["GITHUB_TOKEN"]), (
                "the git-cliff step borrows the App token; it only reads here, so it should use the "
                "scoped GITHUB_TOKEN rather than widening what the release path can write"
            )

    def test_publish_workflow_exists(self, copie):
        """Test that publish workflow exists when actions enabled."""
        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        workflow_path = result.project_dir / ".github" / "workflows" / "publish-release.yml"
        assert workflow_path.is_file()

    def test_publish_workflow_triggered_on_tags(self, copie):
        """Test that publish workflow triggers when changelog PR is merged."""
        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        workflow_path = result.project_dir / ".github" / "workflows" / "publish-release.yml"
        workflow_content = workflow_path.read_text(encoding="utf-8")

        # Use string-based validation since GitHub Actions YAML has expressions
        # Modern workflow triggers on pull_request close (changelog PR merge)
        assert "on:" in workflow_content
        assert ("pull_request:" in workflow_content) or ("push:" in workflow_content and "tags:" in workflow_content)

    def test_publish_workflow_uses_uv(self, copie):
        """Test that the build/publish workflow uses uv for building."""
        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        # Building happens in changelog.yml workflow, not publish-release.yml
        workflow_path = result.project_dir / ".github" / "workflows" / "changelog.yml"
        workflow_content = workflow_path.read_text(encoding="utf-8")

        # Should use uv for building
        assert "uv build" in workflow_content or "uv" in workflow_content

    def test_publish_workflow_has_pypi_upload(self, copie):
        """Test that publish workflow uploads to PyPI with manual approval."""
        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        # PyPI publishing now happens in publish-release.yml workflow
        workflow_path = result.project_dir / ".github" / "workflows" / "publish-release.yml"
        workflow_content = workflow_path.read_text(encoding="utf-8")

        # Should have pypi-publish job
        assert "pypi-publish" in workflow_content or "pypi" in workflow_content.lower()

        # Should use environment for manual approval
        assert "environment:" in workflow_content
        assert "name: pypi" in workflow_content

        # Should use PyPI upload action with Trusted Publishing
        assert "gh-action-pypi-publish" in workflow_content
        assert "id-token: write" in workflow_content

    def test_publish_workflow_creates_github_release(self, copie):
        """Test that publish workflow creates GitHub release."""
        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        workflow_path = result.project_dir / ".github" / "workflows" / "publish-release.yml"
        workflow_content = workflow_path.read_text(encoding="utf-8")

        # Should create GitHub release
        assert "release" in workflow_content.lower()

    def test_publish_workflow_pypi_job_dependencies(self, copie):
        """Test that pypi-publish job depends on create-release job."""
        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        workflow_path = result.project_dir / ".github" / "workflows" / "publish-release.yml"
        workflow_content = workflow_path.read_text(encoding="utf-8")

        # Should have pypi-publish job with needs dependency
        assert "pypi-publish" in workflow_content or "pypi_publish" in workflow_content

        # Verify job dependency structure
        lines = workflow_content.split("\n")
        in_pypi_job = False
        has_needs = False

        for line in lines:
            if "pypi-publish:" in line or "pypi_publish:" in line:
                in_pypi_job = True
            elif in_pypi_job and line.strip().startswith("needs:"):
                has_needs = True
            elif in_pypi_job and "create-release" in line:
                # Found the dependency
                assert has_needs or "needs:" in line, "pypi-publish should depend on create-release"
                break
            elif in_pypi_job and line.strip() and not line.startswith(" ") and not line.startswith("\t"):
                # Started a new job, stop looking
                break

        # Verify environment is set for manual approval
        assert "environment:" in workflow_content
        assert "name: pypi" in workflow_content

    def test_changelog_workflow_no_pypi_job(self, copie):
        """Changelog workflow only opens the changelog PR: no build, no publish.

        The build moved into publish-release.yml so the built artifacts pass natively
        within one workflow run, removing the third-party cross-workflow download action.
        """
        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        workflow_path = result.project_dir / ".github" / "workflows" / "changelog.yml"
        workflow_content = workflow_path.read_text(encoding="utf-8")

        # Should NOT have pypi-publish job (lives in publish-release.yml)
        assert "pypi-publish:" not in workflow_content
        assert "pypi_publish:" not in workflow_content

        # Build + artifact upload moved to publish-release.yml
        assert "uv build" not in workflow_content
        assert "upload-artifact" not in workflow_content

        # It opens the changelog PR
        assert "create-pull-request" in workflow_content


class TestChangelogWorkflow:
    """Test the changelog.yml workflow."""

    def test_changelog_workflow_exists(self, copie):
        """Test that changelog workflow exists when actions enabled."""
        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        workflow_path = result.project_dir / ".github" / "workflows" / "changelog.yml"
        assert workflow_path.is_file()

    def test_changelog_workflow_uses_git_cliff(self, copie):
        """Test that changelog workflow uses git-cliff."""
        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        workflow_path = result.project_dir / ".github" / "workflows" / "changelog.yml"
        workflow_content = workflow_path.read_text(encoding="utf-8")

        # Should use git-cliff action
        assert "git-cliff" in workflow_content

        # Opens the PR with a short-lived GitHub App token, not a long-lived PAT
        assert "CHANGELOG_AUTOMATION_TOKEN" not in workflow_content
        assert "create-github-app-token" in workflow_content

    def test_changelog_workflow_triggered_on_tags(self, copie):
        """Test that changelog workflow triggers on version tags."""
        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        workflow_path = result.project_dir / ".github" / "workflows" / "changelog.yml"
        workflow_content = workflow_path.read_text(encoding="utf-8")

        # Use string-based validation since GitHub Actions YAML has expressions
        assert "on:" in workflow_content
        assert "push:" in workflow_content
        assert "tags:" in workflow_content

    def test_the_release_tag_signature_is_verified_before_anything_else_runs(self, copie):
        """An unsigned release tag stops the release, and stops it first.

        The contributing guide and the security posture both state that release tags
        are signed. For five consecutive releases of this template they were not, and
        nothing noticed: the requirement was written down and measured nowhere, which
        is the same shape as every other control that turned out to be a claim.

        A person creates the tag and that push starts the workflow, so no check can run
        before the tag exists. What is available is order: this job must gate the rest
        rather than race them, or the changelog PR opens for a release that is about to
        be rejected.
        """
        import yaml

        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        workflow_path = result.project_dir / ".github" / "workflows" / "changelog.yml"
        workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        jobs = workflow.get("jobs") or {}

        assert "verify-tag-signature" in jobs, (
            "changelog.yml has no verify-tag-signature job, so an unsigned tag would reach "
            f"a changelog PR and a release unchallenged; jobs are {sorted(jobs)}"
        )
        assert "verify-tag-signature" in (jobs["changelog"].get("needs") or []), (
            "the changelog job does not depend on verify-tag-signature, so the two run in "
            "parallel and the changelog PR opens for a release the check is about to reject"
        )

    def test_the_signature_check_rejects_a_signature_it_cannot_verify(self, copie):
        """The check reads a verification verdict, not the presence of a PGP block.

        A tag signed with a key nobody can look up, or with a corrupted signature,
        still contains `BEGIN PGP SIGNATURE`. A grep for that block therefore passes on
        exactly the input the check exists to reject, which would make this another
        control that reports success without measuring anything. Assert on the
        mechanism, because the difference between the two implementations is invisible
        in a passing run.
        """
        import yaml

        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        workflow_path = result.project_dir / ".github" / "workflows" / "changelog.yml"
        workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        script = "\n".join(
            str(step.get("run", "")) for step in (workflow["jobs"]["verify-tag-signature"].get("steps") or [])
        )

        assert script.strip(), "the verify-tag-signature job runs no script at all"
        assert ".verification.verified" in script, (
            "the signature check does not read the forge's verification verdict; a check that "
            "greps the tag body for a signature block passes on a malformed or unknown-key "
            "signature, which is the case it exists to catch"
        )
        assert "'.object.type" in script or ".object.type" in script, (
            "the check does not distinguish a lightweight tag, which has no tag object to "
            "sign and so fails for a reason the operator cannot act on from the message alone"
        )
        # `${{ }}` is substituted before bash parses the line, so a tag name must reach the
        # shell as an environment variable. GITHUB_REF is the runner's own, not an expression.
        assert "GITHUB_REF" in script, "the tag name is not read from the environment"


class TestNightlyWorkflow:
    """Test the nightly.yml workflow."""

    def test_nightly_workflow_exists(self, copie):
        """Test that nightly workflow exists when actions enabled."""
        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        workflow_path = result.project_dir / ".github" / "workflows" / "nightly.yml"
        assert workflow_path.is_file()

    def test_nightly_workflow_scheduled(self, copie):
        """Test that nightly workflow runs on schedule."""
        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        workflow_path = result.project_dir / ".github" / "workflows" / "nightly.yml"
        workflow_content = workflow_path.read_text(encoding="utf-8")

        # Use string-based validation since GitHub Actions YAML has expressions
        assert "on:" in workflow_content
        assert "schedule:" in workflow_content
        assert "cron:" in workflow_content

    def test_nightly_workflow_uses_uv(self, copie):
        """Test that nightly workflow uses uv."""
        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        workflow_path = result.project_dir / ".github" / "workflows" / "nightly.yml"
        workflow_content = workflow_path.read_text(encoding="utf-8")

        # Should use uv
        assert "uv" in workflow_content


class TestPRTitleWorkflow:
    """Test the pr-title.yml workflow."""

    def test_pr_title_workflow_exists(self, copie):
        """Test that PR title workflow exists when actions enabled."""
        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        workflow_path = result.project_dir / ".github" / "workflows" / "pr-title.yml"
        assert workflow_path.is_file()

    def test_pr_title_workflow_validates_conventional_commits(self, copie):
        """Test that PR title workflow validates conventional commit format."""
        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        workflow_path = result.project_dir / ".github" / "workflows" / "pr-title.yml"
        workflow_content = workflow_path.read_text(encoding="utf-8")

        # Should validate conventional commit format
        assert "conventional" in workflow_content.lower() or "commitizen" in workflow_content.lower()

    def test_pr_title_workflow_triggered_on_pull_request(self, copie):
        """Test that PR title workflow triggers on pull requests."""
        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        workflow_path = result.project_dir / ".github" / "workflows" / "pr-title.yml"
        workflow_content = workflow_path.read_text(encoding="utf-8")

        # Use string-based validation since GitHub Actions YAML has expressions
        assert "on:" in workflow_content
        assert "pull_request:" in workflow_content or "pull_request_target:" in workflow_content


class TestWorkflowConsistency:
    """Test consistency across all workflows."""

    def test_all_workflows_use_consistent_uv_setup(self, copie):
        """Test that all workflows use the same uv setup approach."""
        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        workflows_dir = result.project_dir / ".github" / "workflows"
        workflow_files = [
            "tests.yml",
            "publish-release.yml",
            "changelog.yml",
            "nightly.yml",
        ]

        uv_setup_patterns = []

        for workflow_file in workflow_files:
            workflow_path = workflows_dir / workflow_file
            if workflow_path.exists():
                content = workflow_path.read_text(encoding="utf-8")

                # Track if it uses astral-sh/setup-uv action
                uses_setup_uv_action = "astral-sh/setup-uv" in content

                uv_setup_patterns.append({
                    "file": workflow_file,
                    "uses_action": uses_setup_uv_action,
                })

        # All should use the same approach (either all use action or all don't)
        uses_action_values = [p["uses_action"] for p in uv_setup_patterns]
        # They should all be consistent
        assert len(set(uses_action_values)) <= 2, f"Inconsistent uv setup: {uv_setup_patterns}"

    def test_all_setup_uv_steps_pin_exact_version(self, copie):
        """Every astral-sh/setup-uv step pins the same exact uv version.

        Resolving "latest" is an un-retried GitHub API call and the point at which a
        transient network blip fails CI before any real work (the "fetch failed"
        flake). An exact X.Y.Z pin skips that resolve; a range like "0.10" would still
        resolve over the network, so asserting the version is merely non-empty is not
        enough. This also guards that the pin is uniform (no step left on "latest"),
        that the previously-untested commit-message workflow is covered, and that the
        cache configuration of each step is preserved rather than disturbed.
        """
        import re

        import yaml

        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        workflows_dir = result.project_dir / ".github" / "workflows"
        exact_semver = re.compile(r"^\d+\.\d+\.\d+$")

        # Collect every setup-uv step across all generated workflows, wherever it
        # appears, so a step added to any workflow is covered without editing the test.
        setup_uv_steps = []  # (workflow_file, with_block)
        for workflow_path in sorted(workflows_dir.glob("*.yml")):
            workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
            for job in (workflow.get("jobs") or {}).values():
                for step in job.get("steps") or []:
                    if str(step.get("uses", "")).startswith("astral-sh/setup-uv"):
                        setup_uv_steps.append((workflow_path.name, step.get("with") or {}))

        assert setup_uv_steps, "no astral-sh/setup-uv steps found in generated workflows"

        # R1: every step pins an *exact* X.Y.Z version, never a range or "latest".
        pinned_versions = set()
        for workflow_file, with_block in setup_uv_steps:
            version = with_block.get("version")
            assert version, f"{workflow_file}: setup-uv step does not pin a uv version"
            assert exact_semver.match(str(version)), (
                f"{workflow_file}: uv version {version!r} is not an exact X.Y.Z pin; "
                "a range still resolves over the network and reintroduces the flake"
            )
            pinned_versions.add(str(version))

        # R2: the pin is uniform. The expected value is read from the rendered project,
        # not hardcoded, so bumping the copier default does not break this test.
        assert len(pinned_versions) == 1, f"setup-uv steps pin differing uv versions: {sorted(pinned_versions)}"
        covered_files = {f for f, _ in setup_uv_steps}
        assert "commit-message.yml" in covered_files, "commit-message.yml setup-uv step is not covered by the pin"

        # R3: cache configuration preserved. A step that enables the cache must also set
        # the dependency glob (never half-configured); the dependency-installing test
        # steps keep their cache; the commit-message step (which installs nothing) gets
        # no cache fabricated onto it.
        for workflow_file, with_block in setup_uv_steps:
            if with_block.get("enable-cache"):
                assert with_block.get("cache-dependency-glob") == "pyproject.toml", (
                    f"{workflow_file}: setup-uv enables the cache without the glob"
                )
        tests_steps = [w for f, w in setup_uv_steps if f == "tests.yml"]
        assert tests_steps and all(w.get("enable-cache") for w in tests_steps), (
            "tests.yml setup-uv steps should retain enable-cache (they install deps)"
        )
        commit_steps = [w for f, w in setup_uv_steps if f == "commit-message.yml"]
        assert commit_steps and all("enable-cache" not in w for w in commit_steps), (
            "commit-message.yml setup-uv step should pin version only, with no cache"
        )

    def test_all_workflows_install_nox_consistently(self, copie):
        """Test that all workflows that need nox install it the same way."""
        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        workflows_dir = result.project_dir / ".github" / "workflows"
        workflow_files = ["tests.yml", "nightly.yml"]

        for workflow_file in workflow_files:
            workflow_path = workflows_dir / workflow_file
            if workflow_path.exists():
                content = workflow_path.read_text(encoding="utf-8")

                # Should install nox via uv tool
                assert "uv tool install nox" in content or "uvx nox" in content, (
                    f"{workflow_file} doesn't install nox consistently"
                )

    def test_every_invoked_tool_is_pinned_and_annotated(self, copie):
        """Every tool the generated workflows shell out to is pinned, not just the pinned ones.

        `test_all_setup_uv_steps_pin_exact_version` quantifies over steps that already
        carry a `version:` input. A tool invoked with no constraint at all is not in
        that set, so it was never unpinned as far as the suite could tell. That is how
        `uvx --from cyclonedx-bom` shipped to seven repos and broke every one of their
        releases the day cyclonedx-bom 7.0 removed a flag the step passed, with this
        file green throughout. `uvx twine check` was the same defect, in the same job,
        four lines away, and equally invisible.

        So this enumerates invocations and requires each to carry an exact version and
        a `# renovate:` annotation. Without the version it floats; without the
        annotation nothing can bump it and it rots wherever it was last set.
        """
        from _tool_invocations import find_invocations, unpinned, unreadable_annotations

        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        workflows_dir = result.project_dir / ".github" / "workflows"
        invocations, lines_by_path = [], {}
        for workflow_path in sorted(workflows_dir.glob("*.yml")):
            invocations += find_invocations(workflow_path)
            lines_by_path[workflow_path.name] = workflow_path.read_text(encoding="utf-8").splitlines()

        # Guard the input set: if the scan ever finds nothing, every assertion below
        # passes over an empty set and the gap silently reopens.
        assert invocations, "no tool invocations found in generated workflows; the scan is reading the wrong tree"

        floating = unpinned(invocations, lines_by_path)
        assert not floating, (
            "tools invoked with no exact version (they resolve to whatever is newest on the day): "
            + ", ".join(f"{i.path}:{i.line} `{i.text}`" for i in floating)
        )

        unreadable = []
        for workflow_path in sorted(workflows_dir.glob("*.yml")):
            unreadable += [f"{workflow_path.name}:{d}" for d in unreadable_annotations(workflow_path)]
        assert not unreadable, (
            "`# renovate:` annotations the preset's manager cannot read (present, but placed where "
            "its forward scan cannot reach the version, so nothing will ever bump them): " + ", ".join(unreadable)
        )

        unannotated = [i for i in invocations if i.pinned and not i.annotated]
        assert not unannotated, (
            "pinned tools with no `# renovate:` annotation, so nothing can ever bump them: "
            + ", ".join(f"{i.path}:{i.line} `{i.spec}`" for i in unannotated)
        )


class TestReleaseSmokeGate:
    """The release path is exercised off the release path."""

    def test_smoke_job_runs_the_release_tools_without_publishing(self, copie):
        """A scheduled job builds, checks and generates the SBOM, and publishes nothing.

        `publish-release.yml` only ever executes on a merged, `changelog`-labelled PR,
        so nothing touches these tools until a real publish is already in flight. That
        is how three defects accumulated in one file, one of which -- an SBOM flag
        removed by a major version of an unpinned tool -- broke every generated
        project's release on the day it shipped.

        Pinning those tools converted silent drift into a Renovate pull request, which
        is the right fix and opens a new gap: nothing runs the SBOM step, so such a PR
        goes green on evidence that says nothing about whether releases still work.
        This job is what makes those PRs mean something.
        """
        import yaml

        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        workflow_path = result.project_dir / ".github" / "workflows" / "nightly.yml"
        content = workflow_path.read_text(encoding="utf-8")
        workflow = yaml.safe_load(content)
        jobs = workflow["jobs"]

        assert "release-smoke" in jobs, "no release-smoke job; release tooling is exercised only during a real publish"
        steps = jobs["release-smoke"]["steps"]
        runs = "\n".join(str(s.get("run", "")) for s in steps)

        assert "uv build" in runs, "the smoke job does not build, so it exercises nothing"
        assert "twine" in runs and "check" in runs, "the smoke job does not run twine check"
        assert "cyclonedx-py" in runs, "the smoke job does not generate an SBOM, which is the step that actually broke"

        # It must NOT publish. A smoke gate that uploads is a release, not a smoke gate.
        assert "gh release create" not in runs, "the smoke job creates a release"
        assert not any("pypi-publish" in str(s.get("uses", "")) for s in steps), "the smoke job publishes to PyPI"
        assert (jobs["release-smoke"].get("environment") or {}) == {}, (
            "the smoke job sits behind an environment gate, so it would need approval to tell you anything"
        )

        # Producing a file is not evidence it is usable, so the job must inspect it.
        assert "bomFormat" in runs, (
            "the smoke job does not validate the SBOM it generates; a step writing an empty or "
            "malformed document would pass a mere existence check"
        )

    def test_smoke_failure_is_reported(self, copie):
        """A failure has to reach a human, or the gate is decorative.

        The job runs on a schedule, so nobody is watching when it fails. The nightly
        workflow already files a deduplicated issue on failure; the smoke job has to be
        wired into that, not merely present alongside it.
        """
        import yaml

        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        jobs = yaml.safe_load(
            (result.project_dir / ".github" / "workflows" / "nightly.yml").read_text(encoding="utf-8")
        )["jobs"]
        needs = jobs["create-issue-on-failure"].get("needs") or []
        needs = [needs] if isinstance(needs, str) else needs
        assert "release-smoke" in needs, (
            f"create-issue-on-failure does not depend on release-smoke (needs: {needs}), so a smoke "
            "failure on a schedule would be silent"
        )


class TestWorkflowPermissions:
    """Test that workflows have appropriate permissions."""

    def test_publish_workflow_has_appropriate_permissions(self, copie):
        """Test that publish workflow has necessary permissions."""
        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        workflow_path = result.project_dir / ".github" / "workflows" / "publish-release.yml"
        workflow_content = workflow_path.read_text(encoding="utf-8")

        # Use string-based validation since GitHub Actions YAML has expressions
        # Should have permissions for PyPI trusted publishing and GitHub release
        assert "permissions:" in workflow_content

    def test_changelog_workflow_has_write_permissions(self, copie):
        """Test that changelog workflow can write to repository."""
        result = copie.copy(extra_answers={"include_actions": True})
        assert result.exit_code == 0

        workflow_path = result.project_dir / ".github" / "workflows" / "changelog.yml"
        workflow_content = workflow_path.read_text(encoding="utf-8")

        # Use string-based validation since GitHub Actions YAML has expressions
        # Should have permissions for writing to contents
        assert "permissions:" in workflow_content
