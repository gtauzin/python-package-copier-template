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
