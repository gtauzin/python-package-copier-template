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
            "version": "0.1.0",
            "min_python_version": "3.11",
            "license": "MIT",
            "include_actions": True,
            "include_examples": True,
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


@pytest.fixture
def copie(tmp_path):
    """Fixture that provides a copier test helper."""
    template_dir = Path(__file__).parent.parent
    return CopierTestFixture(template_dir, tmp_path)
