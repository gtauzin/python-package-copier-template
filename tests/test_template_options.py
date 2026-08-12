"""Tests for template option combinations and integration scenarios."""

import subprocess

import pytest
import yaml
from _build_layout import BUILD_DIR


@pytest.mark.parametrize(
    "include_examples,include_actions",
    [
        (True, True),
        (True, False),
        (False, True),
        (False, False),
    ],
)
def test_option_combinations(copie, include_examples, include_actions):
    """Test all combinations of include_examples and include_actions."""
    result = copie.copy(
        extra_answers={
            "include_examples": include_examples,
            "include_actions": include_actions,
        },
    )

    assert result.exit_code == 0

    # Test examples-related files
    examples_dir = result.project_dir / "examples"
    if include_examples:
        assert examples_dir.is_dir(), "examples/ should exist when include_examples=True"
        assert (examples_dir / "hello.py").is_file(), "examples/hello.py should exist"
    else:
        assert not examples_dir.exists(), "examples/ should not exist when include_examples=False"

    # Test GitHub Actions workflows
    workflows_dir = result.project_dir / ".github" / "workflows"
    if include_actions:
        assert workflows_dir.is_dir(), ".github/workflows/ should exist when include_actions=True"
        assert (workflows_dir / "tests.yml").is_file(), "tests.yml should exist"
    else:
        assert not workflows_dir.exists(), ".github/workflows/ should not exist when include_actions=False"

    # Test build.py content (hooks.py was replaced by explicit build steps)
    build_file = result.project_dir / BUILD_DIR / "build.py"
    assert build_file.is_file(), "docs_build/build.py should always exist"
    assert not (result.project_dir / BUILD_DIR / "hooks.py").exists(), "hooks.py should be gone"
    build_content = build_file.read_text(encoding="utf-8")

    if include_examples:
        assert "def prebuild(" in build_content, "prebuild should exist when include_examples=True"
        assert "_notebooks" in build_content, "notebook export should be wired when include_examples=True"
    else:
        assert "def prebuild(" in build_content, "prebuild should always exist for API page generation"
        assert "_notebooks" not in build_content, "notebook export should not be wired when include_examples=False"

    # Test pyproject.toml dependencies
    pyproject_content = (result.project_dir / "pyproject.toml").read_text(encoding="utf-8")
    if include_examples:
        assert "marimo" in pyproject_content, "marimo should be in dependencies when include_examples=True"
        assert "plotly" in pyproject_content, "plotly should be in dependencies when include_examples=True"
    else:
        assert "marimo" not in pyproject_content, "marimo should not be in dependencies when include_examples=False"
        assert "plotly" not in pyproject_content, "plotly should not be in dependencies when include_examples=False"

    # Test noxfile sessions
    noxfile_content = (result.project_dir / "noxfile.py").read_text(encoding="utf-8")
    if include_examples:
        assert "def test_examples(session:" in noxfile_content, (
            "test_examples session should exist when include_examples=True"
        )
    else:
        assert "def test_examples(session:" not in noxfile_content, (
            "test_examples session should not exist when include_examples=False"
        )


@pytest.mark.parametrize(
    "license_type",
    ["Apache-2.0", "MIT", "BSD-3-Clause", "GPL-3.0", "Proprietary"],
)
def test_all_licenses(copie, license_type):
    """Test that all license types generate correctly."""
    result = copie.copy(
        extra_answers={
            "license": license_type,
        },
    )

    assert result.exit_code == 0

    license_file = result.project_dir / "LICENSE"
    assert license_file.is_file(), f"LICENSE file should exist for {license_type}"

    license_content = license_file.read_text(encoding="utf-8")

    # Verify license-specific content
    if license_type == "Apache-2.0":
        assert "Apache License" in license_content
        assert "Version 2.0" in license_content
    elif license_type == "MIT":
        assert "MIT License" in license_content
        assert "Permission is hereby granted" in license_content
    elif license_type == "BSD-3-Clause":
        assert "BSD 3-Clause License" in license_content or "Redistribution and use" in license_content
    elif license_type == "GPL-3.0":
        assert "GNU GENERAL PUBLIC LICENSE" in license_content
        assert "Version 3" in license_content
    elif license_type == "Proprietary":
        assert "Proprietary License" in license_content or "All Rights Reserved" in license_content

    # Verify pyproject.toml has correct license (uses table format)
    pyproject_content = (result.project_dir / "pyproject.toml").read_text(encoding="utf-8")
    assert f'license = {{ text = "{license_type}" }}' in pyproject_content

    # CITATION.cff validates its `license` against the SPDX list, and "Proprietary" is
    # not an SPDX identifier. The field is optional, so it is emitted only for the four
    # answers that are identifiers; emitting it for the fifth would ship a file that
    # fails schema validation in every tool that reads it.
    citation = yaml.safe_load((result.project_dir / "CITATION.cff").read_text(encoding="utf-8"))
    assert citation, f"CITATION.cff did not parse for {license_type}"
    if license_type == "Proprietary":
        assert "license" not in citation, (
            "CITATION.cff carries a non-SPDX license identifier, which fails schema validation"
        )
    else:
        assert citation["license"] == license_type, f"CITATION.cff states the wrong licence for {license_type}"


@pytest.mark.parametrize(
    "python_version",
    ["3.11", "3.12", "3.13", "3.14"],
)
def test_all_python_versions(copie, python_version):
    """Test that all Python version options work correctly."""
    result = copie.copy(
        extra_answers={
            "min_python_version": python_version,
        },
    )

    assert result.exit_code == 0

    # Check pyproject.toml
    pyproject_content = (result.project_dir / "pyproject.toml").read_text(encoding="utf-8")
    assert f'requires-python = ">={python_version}"' in pyproject_content

    # Check noxfile.py Python version matrix
    noxfile_content = (result.project_dir / "noxfile.py").read_text(encoding="utf-8")
    assert f'MIN_VERSION = "{python_version}"' in noxfile_content

    # Verify version is in the test matrix
    expected_versions = [v for v in ["3.11", "3.12", "3.13", "3.14"] if v >= python_version]
    for version in expected_versions:
        assert f'"{version}"' in noxfile_content, f"Python {version} should be in noxfile"


@pytest.mark.integration
def test_examples_disabled_docs_build_works(copie):
    """Test that docs can be built when examples are disabled."""
    result = copie.copy(
        extra_answers={
            "include_examples": False,
        },
    )

    assert result.exit_code == 0

    # Attempt to build docs
    docs_result = subprocess.run(
        ["uvx", "nox", "-s", "build_docs"],
        cwd=result.project_dir,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert docs_result.returncode == 0, (
        f"Docs build failed with include_examples=False:\nSTDOUT:\n{docs_result.stdout}\nSTDERR:\n{docs_result.stderr}"
    )


@pytest.mark.integration
def test_examples_enabled_full_integration(copie):
    """Test complete workflow when examples are enabled."""
    result = copie.copy(
        extra_answers={
            "include_examples": True,
        },
    )

    assert result.exit_code == 0

    # Test that example notebook exists
    examples_dir = result.project_dir / "examples"
    assert (examples_dir / "hello.py").is_file()

    # Test that docs can be built with examples
    docs_result = subprocess.run(
        ["uvx", "nox", "-s", "build_docs"],
        cwd=result.project_dir,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )

    assert docs_result.returncode == 0, (
        f"Docs build failed with include_examples=True:\nSTDOUT:\n{docs_result.stdout}\nSTDERR:\n{docs_result.stderr}"
    )


def test_readthedocs_config_consistency(copie):
    """Test that .readthedocs.yml configuration is consistent."""
    result = copie.copy(extra_answers={})
    assert result.exit_code == 0

    rtd_config = result.project_dir / ".readthedocs.yml"
    assert rtd_config.is_file()

    content = rtd_config.read_text(encoding="utf-8")

    # Should specify Python version
    assert "python:" in content

    # Should use uv for installation
    assert "uv sync" in content

    # The build runs Zensical via explicit commands: Read the Docs has no
    # zensical builder, so the former `mkdocs:` builder is gone.
    assert "commands:" in content
    assert "zensical build" in content
    assert "configuration: mkdocs.yml" not in content, "the mkdocs: builder cannot invoke Zensical"


def test_justfile_commands_comprehensive(copie):
    """Test that justfile includes all expected commands."""
    result = copie.copy(extra_answers={"include_examples": True})
    assert result.exit_code == 0

    justfile = result.project_dir / "justfile"
    assert justfile.is_file()

    content = justfile.read_text(encoding="utf-8")

    # Essential commands
    expected_commands = [
        "default:",
        "test:",
        "test-fast:",
        "test-slow:",
        "test-cov:",
        "test-docstrings:",
        "test-compat ",
        "fix:",  # single command for format, lint, and type check
        "build:",
        "serve:",
        "clean:",
        "all:",
    ]

    for cmd in expected_commands:
        assert cmd in content, f"Command '{cmd}' should be in justfile"


def test_changelog_initial_content(copie):
    """Test that CHANGELOG.md has proper initial content."""
    result = copie.copy(
        extra_answers={"project_name": "Test Project", "version": "0.1.0"},
    )
    assert result.exit_code == 0

    changelog = result.project_dir / "CHANGELOG.md"
    assert changelog.is_file()

    content = changelog.read_text(encoding="utf-8")

    # Should have changelog header
    assert "# Changelog" in content or "# CHANGELOG" in content

    # Should mention keeping a changelog format
    assert "keepachangelog.com" in content.lower() or "keep a changelog" in content.lower()


def test_git_cliff_config_content(copie):
    """Test that .git-cliff.toml has proper configuration."""
    result = copie.copy(extra_answers={})
    assert result.exit_code == 0

    git_cliff_config = result.project_dir / ".git-cliff.toml"
    assert git_cliff_config.is_file()

    content = git_cliff_config.read_text(encoding="utf-8")

    # Should have conventional commits configuration
    assert "conventional_commits" in content or "conventional" in content

    # Should have changelog sections
    assert "[changelog]" in content

    # Should have commit parsers
    assert "commit_parsers" in content or "[git]" in content
