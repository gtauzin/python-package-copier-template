"""Tests for the copier template."""


def test_template_creates_project(copie):
    """Test that the template creates a valid project."""
    expected_files = [
        ".gitignore",
        "README.md",
        "pyproject.toml",
        "noxfile.py",
        "mkdocs.yml",
        ".pre-commit-config.yaml",
    ]
    expected_dirs = [
        "src",
        "src/test_project",
        "docs",
        "tests",
        ".github",
        ".github/workflows",
        "examples",
    ]

    result = copie.copy()

    assert result.exit_code == 0, result.exception
    assert result.exception is None
    assert result.project_dir.is_dir()

    for path in expected_files:
        assert (result.project_dir / path).is_file(), f"Missing file: {path}"

    for path in expected_dirs:
        assert (result.project_dir / path).is_dir(), f"Missing directory: {path}"

    # git-cliff config should be included with GitHub Actions
    assert (result.project_dir / ".git-cliff.toml").is_file()


def test_readthedocs_config_included(copie):
    """Test that ReadTheDocs config is always included."""
    result = copie.copy()

    assert result.exit_code == 0, result.exception
    assert result.exception is None
    assert (result.project_dir / ".readthedocs.yml").is_file()


def test_generated_project_structure(copie):
    """Test that the generated project has the correct structure."""
    result = copie.copy()

    # Check source files
    src_dir = result.project_dir / "src" / "test_project"
    assert (src_dir / "__init__.py").is_file()
    assert (src_dir / "example.py").is_file()
    assert (src_dir / "py.typed").is_file()

    # Check test files
    tests_dir = result.project_dir / "tests"
    assert (tests_dir / "conftest.py").is_file()
    assert (tests_dir / "test_example.py").is_file()

    # Check docs
    docs_dir = result.project_dir / "docs"
    assert (docs_dir / "index.md").is_file()
    assert (docs_dir / "contributing.md").is_file()

    # Check GitHub workflows
    workflows_dir = result.project_dir / ".github" / "workflows"
    assert (workflows_dir / "tests.yml").is_file()
    assert (workflows_dir / "changelog.yml").is_file()
    assert (workflows_dir / "publish-release.yml").is_file()
    assert (workflows_dir / "nightly.yml").is_file()


def test_generated_pyproject_uses_correct_tools(copie):
    """Test that the generated pyproject.toml uses the correct tools."""
    result = copie.copy()

    pyproject_path = result.project_dir / "pyproject.toml"
    assert pyproject_path.is_file()

    content = pyproject_path.read_text()

    # Check for required tools in dependency groups
    assert "ty" in content, "ty not found in pyproject.toml"
    assert "ruff" in content, "ruff not found in pyproject.toml"
    assert "pytest" in content, "pytest not found in pyproject.toml"
    assert "mkdocs" in content, "mkdocs not found in pyproject.toml"
    assert "pre-commit-uv" in content, "pre-commit-uv not found in pyproject.toml"

    # Check for dependency groups structure
    assert "[dependency-groups]" in content, "dependency-groups not found in pyproject.toml"
    assert "tests" in content, "tests dependency group not found"
    assert "lint" in content, "lint dependency group not found"
    assert "docs" in content, "docs dependency group not found"
    assert "fix" in content, "fix dependency group not found"
    assert "examples" in content, "examples dependency group not found"
    assert "dev" in content, "dev dependency group not found"

    # nox should NOT be in pyproject.toml - it's installed globally via uvx
    assert "nox" not in content, "nox should not be in pyproject.toml (install globally with uvx)"


def test_generated_project_has_correct_license(copie):
    """Test that the generated project has the correct license."""
    result = copie.copy(
        extra_answers={
            "license": "MIT",
        },
    )

    license_path = result.project_dir / "LICENSE"
    assert license_path.is_file()

    content = license_path.read_text()
    assert "MIT" in content


def test_noxfile_configuration(copie):
    """Test that noxfile is properly configured."""
    result = copie.copy()

    noxfile_path = result.project_dir / "noxfile.py"
    assert noxfile_path.is_file()

    content = noxfile_path.read_text()

    # Check for uv backend
    assert 'default_venv_backend = "uv|virtualenv"' in content

    # Check for ty
    assert "ty" in content, "ty not found in noxfile.py"


def test_precommit_configuration(copie):
    """Test that pre-commit config is properly set up."""
    result = copie.copy()

    precommit_path = result.project_dir / ".pre-commit-config.yaml"
    assert precommit_path.is_file()

    content = precommit_path.read_text()

    # Check for ruff
    assert "ruff-pre-commit" in content or "ruff" in content

    # Check for ty
    assert "ty" in content, "ty not found in pre-commit config"

    # Check for commitizen
    assert "commitizen" in content, "commitizen not found in pre-commit config"


def test_github_workflows(copie):
    """Test that GitHub workflows are properly configured."""
    result = copie.copy()

    tests_workflow = result.project_dir / ".github" / "workflows" / "tests.yml"
    assert tests_workflow.is_file()

    content = tests_workflow.read_text()

    # Check for uv usage
    assert "astral-sh/setup-uv" in content

    # Check for ty
    assert "ty" in content, "ty not found in tests workflow"

    # Check for doctest job
    assert "doctest:" in content, "doctest job not found in tests workflow"
    assert "nox -s doctest" in content, "doctest nox session not run in CI"

    # Check PR title validation workflow
    pr_title_workflow = result.project_dir / ".github" / "workflows" / "pr-title.yml"
    assert pr_title_workflow.is_file(), "PR title validation workflow not found"

    pr_title_content = pr_title_workflow.read_text()
    assert "amannn/action-semantic-pull-request" in pr_title_content
    assert "feat" in pr_title_content
    assert "fix" in pr_title_content
    assert "docs" in pr_title_content


def test_release_workflow(copie):
    """Test that release workflow includes changelog automation."""
    result = copie.copy()

    # Check changelog.yml workflow
    changelog_workflow = result.project_dir / ".github" / "workflows" / "changelog.yml"
    assert changelog_workflow.is_file()

    changelog_content = changelog_workflow.read_text()

    # Check for git-cliff
    assert "git-cliff" in changelog_content, "git-cliff not found in changelog workflow"

    # Check for changelog job
    assert "changelog" in changelog_content.lower(), "changelog job not found in changelog workflow"

    # Check publish-release.yml workflow
    release_workflow = result.project_dir / ".github" / "workflows" / "publish-release.yml"
    assert release_workflow.is_file()

    release_content = release_workflow.read_text()

    # Check for GitHub release creation
    assert "gh release create" in release_content or "github-release" in release_content.lower(), (
        "GitHub release creation not found"
    )


def test_commitizen_configuration(copie):
    """Test that commitizen is properly configured."""
    result = copie.copy()

    pyproject_path = result.project_dir / "pyproject.toml"
    assert pyproject_path.is_file()

    content = pyproject_path.read_text()

    # Check for commitizen configuration
    assert "[tool.commitizen]" in content, "commitizen config not found in pyproject.toml"
    assert "cz_conventional_commits" in content, "conventional commits not configured"


def test_git_cliff_configuration(copie):
    """Test that git-cliff configuration exists."""
    result = copie.copy()

    cliff_config = result.project_dir / ".git-cliff.toml"
    assert cliff_config.is_file()

    content = cliff_config.read_text()

    # Check for conventional commits
    assert "conventional_commits" in content, "conventional commits not enabled in git-cliff"

    # Check for Keep a Changelog format
    assert "Keep a Changelog" in content, "Keep a Changelog format not mentioned"

    # Check that chore(release) commits are skipped
    assert 'message = "^chore\\\\(release\\\\)", skip = true' in content, (
        "chore(release) commits should be skipped in changelog"
    )


def test_different_licenses(copie):
    """Test that different licenses can be selected."""
    licenses = ["MIT", "Apache-2.0", "BSD-3-Clause", "GPL-3.0"]

    for license_name in licenses:
        result = copie.copy(
            extra_answers={
                "license": license_name,
                "project_slug": f"test-{license_name.lower()}",
            },
        )

        assert result.exit_code == 0
        assert result.project_dir.is_dir()

        # Check that LICENSE file exists
        license_path = result.project_dir / "LICENSE"
        assert license_path.is_file()


def test_doctest_configuration(copie):
    """Test that doctest configuration is properly set up."""
    result = copie.copy()

    assert result.exit_code == 0
    assert result.project_dir.is_dir()

    # Check pyproject.toml contains doctest configuration
    pyproject_content = (result.project_dir / "pyproject.toml").read_text()
    assert "[tool.pytest.ini_options.doctest]" in pyproject_content
    assert "--doctest-modules" in pyproject_content
    assert "--doctest-continue-on-failure" in pyproject_content

    # Check noxfile has doctest session
    noxfile_content = (result.project_dir / "noxfile.py").read_text()
    assert "def doctest(session:" in noxfile_content
    assert '"--doctest-modules"' in noxfile_content

    # Check justfile has doctest command
    justfile_content = (result.project_dir / "justfile").read_text()
    assert "doctest:" in justfile_content
    assert "--doctest-modules" in justfile_content

    # Check example.py has docstring examples
    example_py = (result.project_dir / "src" / "test_project" / "example.py").read_text()
    assert "Examples:" in example_py
    assert ">>>" in example_py


def test_examples_directory_when_enabled(copie):
    """Test that examples directory is created when include_examples=True."""
    result = copie.copy(
        extra_answers={
            "include_examples": True,
        },
    )

    assert result.exit_code == 0
    examples_dir = result.project_dir / "examples"
    assert examples_dir.is_dir(), "examples/ directory not created"

    # Check for notebook file
    hello_notebook = examples_dir / "hello.py"
    assert hello_notebook.is_file(), "examples/hello.py not created"

    # Check notebook content
    notebook_content = hello_notebook.read_text()
    assert "import marimo" in notebook_content
    assert "app = marimo.App" in notebook_content
    assert "plotly" in notebook_content
    assert "num_points" in notebook_content

    # Check marimo in dependencies
    pyproject_content = (result.project_dir / "pyproject.toml").read_text()
    assert "marimo" in pyproject_content
    assert "plotly" in pyproject_content
    assert "mkdocs-marimo" in pyproject_content

    # Check noxfile has run_examples session
    noxfile_content = (result.project_dir / "noxfile.py").read_text()
    assert "def run_examples(session:" in noxfile_content
    assert "examples/hello.py" in noxfile_content

    # Check justfile has example command
    justfile_content = (result.project_dir / "justfile").read_text()
    assert "example:" in justfile_content
    assert "marimo edit" in justfile_content

    # Check examples.md exists
    examples_md = result.project_dir / "docs" / "examples.md"
    assert examples_md.is_file(), "docs/examples.md not created"

    # Check mkdocs.yml includes examples in nav
    mkdocs_content = (result.project_dir / "mkdocs.yml").read_text()
    assert "Examples: examples.md" in mkdocs_content

    # Check GitHub workflow includes examples job
    tests_workflow = result.project_dir / ".github" / "workflows" / "tests.yml"
    workflow_content = tests_workflow.read_text()
    assert "examples:" in workflow_content
    assert "nox -s run_examples" in workflow_content


def test_examples_directory_when_disabled(copie):
    """Test that examples directory is NOT created when include_examples=False."""
    result = copie.copy(
        extra_answers={
            "include_examples": False,
        },
    )

    assert result.exit_code == 0

    # Examples directory should not exist or be empty when disabled
    examples_dir = result.project_dir / "examples"
    assert not examples_dir.is_dir(), "examples/ directory created"

    # Marimo should not be in examples dependencies
    pyproject_content = (result.project_dir / "pyproject.toml").read_text()
    # examples group should not exist or be empty
    assert (
        "examples = [" not in pyproject_content
        or "examples = []" in pyproject_content
        or "examples = [\n]" in pyproject_content
    )
    # marimo should not be in dependencies
    assert "marimo" not in pyproject_content
    assert "plotly" not in pyproject_content
    # mkdocs-marimo should not be in docs dependencies
    assert "mkdocs-marimo" not in pyproject_content

    # Check noxfile doesn't have run_examples session
    noxfile_content = (result.project_dir / "noxfile.py").read_text()
    assert "def run_examples(session:" not in noxfile_content

    # Check justfile doesn't have example command
    justfile_content = (result.project_dir / "justfile").read_text()
    # Should not have the example command, but might have other content
    lines = justfile_content.split("\n")
    example_command_lines = [line for line in lines if line.strip().startswith("example:")]
    assert len(example_command_lines) == 0, "example command should not exist"

    # Check examples.md doesn't exist or is empty
    examples_md = result.project_dir / "docs" / "examples.md"
    if examples_md.exists():
        content = examples_md.read_text().strip()
        assert content == "", (
            f"docs/examples.md should be empty when examples are disabled, but contains: {content[:100]}"
        )

    # Check mkdocs.yml doesn't include examples in nav
    mkdocs_content = (result.project_dir / "mkdocs.yml").read_text()
    assert "Examples: examples.md" not in mkdocs_content

    # Check GitHub workflow doesn't include examples job
    tests_workflow = result.project_dir / ".github" / "workflows" / "tests.yml"
    workflow_content = tests_workflow.read_text()
    assert "run_examples" not in workflow_content


def test_github_actions_when_enabled(copie):
    """Test that GitHub Actions workflows are created when include_actions=True."""
    result = copie.copy(
        extra_answers={
            "include_actions": True,
        },
    )

    assert result.exit_code == 0

    # Check .github directory exists
    github_dir = result.project_dir / ".github"
    assert github_dir.is_dir(), ".github/ directory not created"

    # Check workflows directory exists
    workflows_dir = github_dir / "workflows"
    assert workflows_dir.is_dir(), ".github/workflows/ directory not created"

    # Check for required workflow files
    assert (workflows_dir / "tests.yml").is_file(), "tests.yml workflow not created"
    assert (workflows_dir / "publish-release.yml").is_file(), "publish-release.yml workflow not created"
    assert (workflows_dir / "changelog.yml").is_file(), "changelog.yml workflow not created"
    assert (workflows_dir / "pr-title.yml").is_file(), "pr-title.yml workflow not created"
    assert (workflows_dir / "nightly.yml").is_file(), "nightly.yml workflow not created"

    # Check for GitHub configuration files
    assert (github_dir / "dependabot.yml").is_file(), "dependabot.yml not created"
    assert (github_dir / "PULL_REQUEST_TEMPLATE.md").is_file(), "PR template not created"

    # Check ISSUE_TEMPLATE directory
    issue_template_dir = github_dir / "ISSUE_TEMPLATE"
    assert issue_template_dir.is_dir(), "ISSUE_TEMPLATE directory not created"
    assert (issue_template_dir / "bug_report.yml").is_file(), "bug_report.yml not created"
    assert (issue_template_dir / "feature_request.yml").is_file(), "feature_request.yml not created"
    assert (issue_template_dir / "config.yml").is_file(), "issue template config.yml not created"

    # Check workflow content uses uv
    tests_workflow_content = (workflows_dir / "tests.yml").read_text()
    assert "astral-sh/setup-uv" in tests_workflow_content, "uv not used in tests workflow"

    # Check git-cliff.toml exists (should be included with workflows)
    assert (result.project_dir / ".git-cliff.toml").is_file(), ".git-cliff.toml not created"


def test_github_actions_when_disabled(copie):
    """Test that GitHub Actions workflows are NOT created when include_actions=False."""
    result = copie.copy(
        extra_answers={
            "include_actions": False,
        },
    )

    assert result.exit_code == 0

    # .github directory may exist but workflows should not
    github_dir = result.project_dir / ".github"
    if github_dir.is_dir():
        # Check that workflows directory doesn't exist or is empty
        workflows_dir = github_dir / "workflows"
        if workflows_dir.exists():
            workflow_files = list(workflows_dir.glob("*.yml"))
            assert len(workflow_files) == 0, (
                f".github/workflows should be empty but contains: {[f.name for f in workflow_files]}"
            )

    # git-cliff.toml should not exist or be empty (only needed with workflows)
    git_cliff = result.project_dir / ".git-cliff.toml"
    if git_cliff.exists():
        content = git_cliff.read_text().strip()
        assert content == "", ".git-cliff.toml should be empty when GitHub Actions are disabled"
