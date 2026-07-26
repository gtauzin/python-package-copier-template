"""Pytest configuration for template tests."""

from pathlib import Path

import pytest
from copier import run_copy


class CopierTestFixture:
    """Helper class for testing copier templates."""

    def __init__(self, template_dir: Path, tmp_path: Path):
        self.template_dir = template_dir
        self.tmp_path = tmp_path

    def copy(self, extra_answers: dict | None = None):
        """Copy the template with given answers."""
        project_dir = self.tmp_path / "test-project"

        # Default answers
        answers = {
            "project_name": "Test Project",
            "project_slug": "test-project",
            "package_name": "test_project",
            "description": "A test project",
            "author_name": "Test Author",
            "author_email": "test@example.com",
            "github_username": "testuser",
            "code_owner": "@testowner",
            "version": "0.1.0",
            "min_python_version": "3.11",
            "max_python_version": "3.14",
            "license": "MIT",
            "repo_visibility": "public",
            "include_actions": True,
            "include_examples": True,
            "include_codecov": True,
            "uv_version": "0.10.0",
            "renovate_preset": "",
        }

        # Override with extra answers
        if extra_answers:
            answers.update(extra_answers)

        # Run copier - use HEAD to get latest changes
        result = run_copy(
            str(self.template_dir),
            str(project_dir),
            data=answers,
            defaults=True,
            overwrite=True,
            unsafe=True,
            vcs_ref="HEAD",
        )

        return CopierResult(project_dir=project_dir, result=result)


class CopierResult:
    """Result of a copier template copy operation."""

    def __init__(self, project_dir: Path, result):
        self.project_dir = project_dir
        self.result = result
        self.exit_code = 0 if project_dir.exists() else 1
        self.exception = None


@pytest.fixture(scope="session", autouse=True)
def keep_uv_out_of_the_runner_venv():
    """Stop `uv` subprocesses from re-syncing the venv the tests run in.

    nox exports UV_PROJECT_ENVIRONMENT pointing at its session venv, and every
    subprocess inherits it, so `uv sync` inside a generated project retargets the
    runner's own venv instead of the project's: it installed test_project, marimo and
    pandas into it and re-resolved Markdown out from under the suite. A worker that
    imported markdown.extensions.toc during that swap died with ModuleNotFoundError.
    Unset, uv falls back to the project's own .venv, which is what these tests mean.
    """
    with pytest.MonkeyPatch.context() as mp:
        mp.delenv("UV_PROJECT_ENVIRONMENT", raising=False)
        yield


@pytest.fixture(scope="session")
def session_projects_dir(tmp_path_factory):
    """Session-scoped temp directory for generated projects.

    This directory persists for the entire test session and is shared
    across all tests using session-scoped project fixtures.
    """
    return tmp_path_factory.mktemp("session_projects")


@pytest.fixture(scope="session")
def copie_session_default(session_projects_dir):
    """Session-scoped: Generated project with DEFAULT values.

    This fixture generates a project once per test session with:
    - include_examples=True
    - include_actions=True
    - All default template values

    Use this for read-only tests that validate project structure and content.
    Multiple tests can share this fixture, reducing generation overhead.
    """
    template_dir = Path(__file__).parent.parent
    project_dir = session_projects_dir / "default-project"

    # Default answers
    answers = {
        "project_name": "Test Project",
        "project_slug": "test-project",
        "package_name": "test_project",
        "description": "A test project",
        "author_name": "Test Author",
        "author_email": "test@example.com",
        "github_username": "testuser",
        "version": "0.1.0",
        "min_python_version": "3.11",
        "max_python_version": "3.14",
        "license": "MIT",
        "repo_visibility": "public",
        "include_actions": True,
        "include_examples": True,
        "include_codecov": True,
        "uv_version": "0.10.0",
        "renovate_preset": "",
    }

    # Generate project once
    result = run_copy(
        str(template_dir),
        str(project_dir),
        data=answers,
        defaults=True,
        overwrite=True,
        unsafe=True,
        vcs_ref="HEAD",
    )

    return CopierResult(project_dir=project_dir, result=result)


@pytest.fixture(scope="session")
def copie_session_minimal(session_projects_dir):
    """Session-scoped: Generated project with MINIMAL values.

    This fixture generates a project once per test session with:
    - include_examples=False
    - include_actions=False
    - Minimal optional features

    Use this for read-only tests that validate minimal project structure.
    """
    template_dir = Path(__file__).parent.parent
    project_dir = session_projects_dir / "minimal-project"

    # Minimal answers
    answers = {
        "project_name": "Minimal Project",
        "project_slug": "minimal-project",
        "package_name": "minimal_project",
        "description": "A minimal test project",
        "author_name": "Test Author",
        "author_email": "test@example.com",
        "github_username": "testuser",
        "version": "0.1.0",
        "min_python_version": "3.11",
        "max_python_version": "3.14",
        "license": "MIT",
        "repo_visibility": "public",
        "include_actions": False,
        "include_examples": False,
        "uv_version": "0.10.0",
        "renovate_preset": "",
    }

    # Generate project once
    result = run_copy(
        str(template_dir),
        str(project_dir),
        data=answers,
        defaults=True,
        overwrite=True,
        unsafe=True,
        vcs_ref="HEAD",
    )

    return CopierResult(project_dir=project_dir, result=result)


@pytest.fixture(scope="session")
def copie_session_custom(session_projects_dir):
    """Session-scoped: Generated project with CUSTOM values.

    This fixture generates a project once per test session with:
    - Custom project/package names
    - Custom version (1.5.0)
    - Apache-2.0 license
    - Python 3.12+

    Use this for read-only tests that validate custom value propagation.
    """
    template_dir = Path(__file__).parent.parent
    project_dir = session_projects_dir / "custom-project"

    # Custom answers
    answers = {
        "project_name": "Custom Package",
        "project_slug": "custom-package",
        "package_name": "custom_package",
        "description": "A custom package for advanced testing scenarios",
        "author_name": "Dr. Jane Doe",
        "author_email": "jane.doe@research.org",
        "github_username": "research-lab",
        "version": "1.5.0",
        "min_python_version": "3.12",
        "max_python_version": "3.14",
        "license": "Apache-2.0",
        "repo_visibility": "public",
        "include_actions": True,
        "include_examples": True,
        "include_codecov": True,
        "uv_version": "0.10.0",
        "renovate_preset": "",
    }

    # Generate project once
    result = run_copy(
        str(template_dir),
        str(project_dir),
        data=answers,
        defaults=True,
        overwrite=True,
        unsafe=True,
        vcs_ref="HEAD",
    )

    return CopierResult(project_dir=project_dir, result=result)


@pytest.fixture
def copie(tmp_path):
    """Fixture that provides a copier test helper.

    This is a function-scoped fixture that generates a fresh project
    for each test. Use this when:
    - Tests need unique configurations (e.g., different licenses, versions)
    - Tests are parameterized with different option values
    - Tests modify generated files

    For read-only structure/content validation, prefer session-scoped fixtures:
    - copie_session_default
    - copie_session_minimal
    - copie_session_custom
    """
    template_dir = Path(__file__).parent.parent
    return CopierTestFixture(template_dir, tmp_path)


@pytest.fixture
def copie_custom_values(tmp_path):
    """Fixture that provides a copier helper with custom (non-default) values.

    Useful for testing that template variables propagate correctly
    when users provide their own values.
    """
    template_dir = Path(__file__).parent.parent
    fixture = CopierTestFixture(template_dir, tmp_path)

    # Pre-configured with custom values
    fixture.custom_answers = {
        "project_name": "Custom Package",
        "package_name": "custom_package",
        "project_slug": "custom-package",
        "version": "1.5.0",
        "description": "A custom package for advanced testing scenarios",
        "author_name": "Dr. Jane Doe",
        "author_email": "jane.doe@research.org",
        "github_username": "research-lab",
        "license": "Apache-2.0",
        "min_python_version": "3.12",
        "include_actions": True,
        "include_examples": True,
    }

    return fixture


@pytest.fixture
def copie_edge_cases(tmp_path):
    """Fixture that provides a copier helper with edge case values.

    Tests empty strings, unicode, and special characters to ensure
    robust template handling.
    """
    template_dir = Path(__file__).parent.parent
    fixture = CopierTestFixture(template_dir, tmp_path)

    # Pre-configured with edge case values
    fixture.edge_case_answers = {
        "project_name": "Test Project 🚀",
        "description": "",  # Empty description
        "author_name": "José García-López",  # Unicode
        "author_email": "test+alias@example.com",  # Plus sign
        "github_username": "",  # Empty GitHub username
        "license": "MIT",
        "min_python_version": "3.11",
        "include_actions": True,
        "include_examples": False,
    }

    return fixture


@pytest.fixture
def copie_minimal(tmp_path):
    """Fixture that provides minimal configuration (all optional features disabled).

    Useful for testing the minimal viable generated project.
    """
    template_dir = Path(__file__).parent.parent
    fixture = CopierTestFixture(template_dir, tmp_path)

    fixture.minimal_answers = {
        "project_name": "Minimal Project",
        "description": "",
        "author_name": "Test Author",
        "author_email": "test@example.com",
        "github_username": "",
        "license": "MIT",
        "min_python_version": "3.11",
        "include_actions": False,
        "include_examples": False,
    }

    return fixture


# Constants for test configuration
SUBPROCESS_TIMEOUT = 120  # Timeout for subprocess tests in seconds
INTEGRATION_TEST_MARKER = "integration"  # Marker for integration tests
SLOW_TEST_MARKER = "slow"  # Marker for slow tests
