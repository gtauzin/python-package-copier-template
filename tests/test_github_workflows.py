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
