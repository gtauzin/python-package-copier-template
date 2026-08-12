"""Tests for the copier template."""

import contextlib
import json
import logging
import os
import posixpath
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from _build_layout import BUILD_DIR, TEMPLATES_DIR, mkdocstrings_templates, site_path


def test_template_creates_project(copie_session_default):
    """Test that the template creates a valid project."""
    expected_files = [
        ".gitignore",
        "README.md",
        "pyproject.toml",
        "noxfile.py",
        "mkdocs.yml",
        ".pre-commit-config.yaml",
        "CODE_OF_CONDUCT.md",
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

    result = copie_session_default

    assert result.exit_code == 0, result.exception
    assert result.exception is None
    assert result.project_dir.is_dir()

    for path in expected_files:
        assert (result.project_dir / path).is_file(), f"Missing file: {path}"

    for path in expected_dirs:
        assert (result.project_dir / path).is_dir(), f"Missing directory: {path}"

    # git-cliff config should be included with GitHub Actions
    assert (result.project_dir / ".git-cliff.toml").is_file()


def test_readthedocs_config_included(copie_session_default):
    """Test that ReadTheDocs config is always included."""
    result = copie_session_default

    assert result.exit_code == 0, result.exception
    assert result.exception is None
    assert (result.project_dir / ".readthedocs.yml").is_file()


def test_gitignore_includes_examples_when_enabled(copie):
    """Test that .gitignore includes examples section when include_examples is true."""
    result = copie.copy(extra_answers={"include_examples": True})

    gitignore = result.project_dir / ".gitignore"
    assert gitignore.is_file()

    content = gitignore.read_text(encoding="utf-8")

    # Should have documentation examples section
    assert "# Documentation examples" in content
    assert "docs/examples/*/" in content


def test_gitignore_excludes_examples_when_disabled(copie):
    """Test that .gitignore excludes examples section when include_examples is false."""
    result = copie.copy(extra_answers={"include_examples": False})

    gitignore = result.project_dir / ".gitignore"
    assert gitignore.is_file()

    content = gitignore.read_text(encoding="utf-8")

    # Should NOT have documentation examples section
    assert "# Documentation examples" not in content
    assert "docs/examples/*/" not in content


def test_gitignore_includes_worktrees(copie_session_default):
    """Test that .gitignore includes .worktrees/ entry."""
    result = copie_session_default

    content = (result.project_dir / ".gitignore").read_text(encoding="utf-8")

    assert "# Worktrees" in content
    assert ".worktrees/" in content


def test_gitignore_uses_project_name_for_version_file(copie):
    """Test that .gitignore uses project_name variable (not project_slug) for the version file path."""
    result = copie.copy(extra_answers={"package_name": "my_package", "project_slug": "my-project"})

    gitignore = result.project_dir / ".gitignore"
    assert gitignore.is_file()

    content = gitignore.read_text(encoding="utf-8")

    # Should use package_name in the version file path
    assert "src/my_package/_version.py" in content
    # Should NOT use project_slug
    assert "src/my-project/_version.py" not in content


def test_generated_project_structure(copie_session_default):
    """Test that the generated project has the correct structure."""
    result = copie_session_default

    # Check source files
    src_dir = result.project_dir / "src" / "test_project"
    assert (src_dir / "__init__.py").is_file()
    assert (src_dir / "hello.py").is_file()
    assert (src_dir / "py.typed").is_file()

    # Check test files
    tests_dir = result.project_dir / "tests"
    assert (tests_dir / "conftest.py").is_file()
    assert (tests_dir / "test_hello.py").is_file()

    # Check docs
    docs_dir = result.project_dir / "docs"
    assert (docs_dir / "index.md").is_file()
    assert (docs_dir / "pages" / "how-to" / "contribute.md").is_file()

    # Check GitHub workflows
    workflows_dir = result.project_dir / ".github" / "workflows"
    assert (workflows_dir / "tests.yml").is_file()
    assert (workflows_dir / "changelog.yml").is_file()
    assert (workflows_dir / "publish-release.yml").is_file()
    assert (workflows_dir / "nightly.yml").is_file()


def test_generated_pyproject_uses_correct_tools(copie_session_default):
    """Test that the generated pyproject.toml uses the correct tools."""
    result = copie_session_default

    pyproject_path = result.project_dir / "pyproject.toml"
    assert pyproject_path.is_file()

    content = pyproject_path.read_text(encoding="utf-8")

    # Check for required tools in dependency groups
    assert "ty" in content, "ty not found in pyproject.toml"
    assert "ruff" in content, "ruff not found in pyproject.toml"
    assert "pytest" in content, "pytest not found in pyproject.toml"
    assert "mkdocs" in content, "mkdocs not found in pyproject.toml"
    assert "prek" in content, "prek not found in pyproject.toml"
    # prek must be a pinned dependency, not fetched ad hoc: it supplies the `repo: builtin`
    # hooks' implementations, so an unpinned runner means unpinned hook code.
    assert "pre-commit-uv" not in content, "pre-commit-uv should have been replaced by prek"

    # Check for dependency groups structure
    assert "[dependency-groups]" in content, "dependency-groups not found in pyproject.toml"
    assert "tests" in content, "tests dependency group not found"
    assert "lint" in content, "lint dependency group not found"
    assert "docs" in content, "docs dependency group not found"
    assert "fix" in content, "fix dependency group not found"
    assert "examples" in content, "examples dependency group not found"
    assert "dev" in content, "dev dependency group not found"

    # nox should NOT be a dependency in pyproject.toml - it's installed globally via uvx
    # (note: .nox may appear in tool config exclude lists, which is fine)
    assert '"nox' not in content and "'nox" not in content, (
        "nox should not be a dependency in pyproject.toml (install globally with uvx)"
    )


def test_pyproject_has_interrogate_config(copie_session_default):
    """Test that pyproject.toml includes interrogate configuration."""
    result = copie_session_default

    pyproject_path = result.project_dir / "pyproject.toml"
    assert pyproject_path.is_file()

    content = pyproject_path.read_text(encoding="utf-8")

    # Should have interrogate configuration section
    assert "[tool.interrogate]" in content
    assert "ignore-init-method = true" in content
    assert "fail-under = 75" in content
    # docs_build joins the exclude: the build modules moved there, and they were
    # excluded from docstring coverage before (via "docs") -- the move keeps that.
    assert '"setup.py", "docs", "docs_build", "build", "tests", "*_version.py"' in content


def test_pyproject_ruff_ignores_docs_directory(copie):
    """Test that pyproject.toml configures ruff to ignore prints and unused args in docs/."""
    result = copie.copy()

    pyproject_path = result.project_dir / "pyproject.toml"
    assert pyproject_path.is_file()

    content = pyproject_path.read_text(encoding="utf-8")

    # Should have per-file-ignores covering both docs/ populations
    assert "[tool.ruff.lint.per-file-ignores]" in content
    # The build tooling lives in docs_build/ and every script there prints build
    # progress (T201) and may hold per-build cache globals (PLW0603). The mkdocs
    # event-signature hooks that once needed an unused-argument (ARG001) exemption
    # are gone -- the successor tooling implements no imposed signatures -- so the
    # glob carries only the exemptions the scripts still need.
    assert '"docs_build/*.py"' in content
    assert "T201" in content  # Print statement
    build_ignores = content.split('"docs_build/*.py"')[1].split("\n")[0]
    assert "T201" in build_ignores, "the build scripts lost their print exemption"
    assert "PLW0603" in build_ignores, "the build scripts lost their cache-global exemption"
    assert "ARG001" not in build_ignores, (
        "no build script needs an unused-argument exemption now that the hooks are gone"
    )
    # `docs/*.py` is the project-scripts glob, kept for scripts a project adds; it
    # must not carry the unused-argument exemption.
    docs_ignores = content.split('"docs/*.py"')[1].split("\n")[0]
    assert "T201" in docs_ignores, "a project's own docs/ scripts lost their print exemption"
    assert "ARG001" not in docs_ignores, "docs scripts must not get a blanket unused-argument exemption"

    # The glob must match a PROJECT-OWNED script, not just the ones the template
    # ships. v0.27.2 used "docs/_*.py", which silently dropped lint coverage for
    # yohou's docs/precache_datasets.py -- removing the exemption without removing
    # the lint. Assert the pattern, because the failure is a missing match and a
    # test that only checks the template's own files cannot see it.
    assert '"docs/*.py"' in content, (
        'the docs glob must be "docs/*.py", not "docs/_*.py" -- a project-owned '
        "script under docs/ would otherwise lose its print exemption"
    )
    assert '"docs/_*.py"' not in content, 'the narrow "docs/_*.py" glob was replaced by "docs/*.py"'


def test_generated_project_has_correct_license(copie):
    """Test that the generated project has the correct license."""
    result = copie.copy(
        extra_answers={
            "license": "MIT",
        },
    )

    license_path = result.project_dir / "LICENSE"
    assert license_path.is_file()

    content = license_path.read_text(encoding="utf-8")
    assert "MIT" in content


def test_noxfile_configuration(copie_session_default):
    """Test that noxfile is properly configured."""
    result = copie_session_default

    noxfile_path = result.project_dir / "noxfile.py"
    assert noxfile_path.is_file()

    content = noxfile_path.read_text(encoding="utf-8")

    # Check for uv backend
    assert 'default_venv_backend = "uv|virtualenv"' in content

    # Check for ty
    assert "ty" in content, "ty not found in noxfile.py"


def test_noxfile_test_coverage_uses_pytest_cov(copie_session_default):
    """Test that test_coverage session uses pytest-cov instead of manual coverage."""
    result = copie_session_default

    content = (result.project_dir / "noxfile.py").read_text(encoding="utf-8")

    # Should use pytest directly (pytest-cov handles coverage via addopts)
    assert "pytest-cov" in content or "pytest" in content

    # Should NOT use manual coverage commands
    assert 'session.env["COVERAGE_FILE"]' not in content
    assert 'session.env["COVERAGE_PROCESS_START"]' not in content
    assert '"coverage", "erase"' not in content
    assert '"coverage", "run"' not in content
    assert '"coverage", "html"' not in content
    assert '"coverage", "xml"' not in content


def test_precommit_configuration(copie_session_default):
    """Test that pre-commit config is properly set up."""
    result = copie_session_default

    precommit_path = result.project_dir / ".pre-commit-config.yaml"
    assert precommit_path.is_file()

    content = precommit_path.read_text(encoding="utf-8")

    # Check for ruff
    assert "ruff-pre-commit" in content or "ruff" in content

    # Check for ty
    assert "ty" in content, "ty not found in pre-commit config"

    # Check for commitizen
    assert "commitizen" in content, "commitizen not found in pre-commit config"


def test_precommit_declares_builtins_explicitly(copie_session_default):
    """Test that substituted hooks are declared as builtins, not against a rev that governs nothing.

    prek swaps its own Rust implementations in for pre-commit/pre-commit-hooks' hooks and
    ignores the `rev` field while doing so. Declaring them against that repo would leave a
    pin in the file that controls nothing -- the silent divergence the config rules out.
    """
    content = (copie_session_default.project_dir / ".pre-commit-config.yaml").read_text(encoding="utf-8")

    assert "repo: builtin" in content, "builtin hooks not declared explicitly"
    # Match the declaration, not the word: the config's comment names the repo in prose to
    # explain why it is not used, and a substring check cannot tell the two apart.
    assert "repo: https://github.com/pre-commit/pre-commit-hooks" not in content, (
        "hooks still declared against pre-commit-hooks, whose rev prek ignores"
    )
    for hook_id in (
        "trailing-whitespace",
        "end-of-file-fixer",
        "check-yaml",
        "check-added-large-files",
        "check-json",
        "check-toml",
        "check-merge-conflict",
        "mixed-line-ending",
    ):
        assert f"id: {hook_id}" in content, f"{hook_id} missing from the builtin block"

    # debug-statements is covered by ruff's T10, which also catches pdb.set_trace() calls
    # that debug-statements misses entirely.
    assert "debug-statements" not in content, "debug-statements is redundant with ruff T10"

    # commitizen has no builtin, so its rev is real and must survive.
    assert "rev: v4.3.0" in content, "commitizen's rev is genuine and must not be removed"


def test_precommit_installs_the_commit_msg_hook_type(copie_session_default):
    """Test that the commit-msg hook type is actually installed, not merely declared.

    `prek install` creates only the pre-commit hook unless the config names other types.
    Without this, commitizen's `stages: [commit-msg]` hook is configured but never wired
    into .git/hooks, so it silently never runs -- a gate that exists only on paper.
    """
    content = (copie_session_default.project_dir / ".pre-commit-config.yaml").read_text(encoding="utf-8")

    assert "stages: [commit-msg]" in content, "commitizen should run at commit-msg"
    assert "default_install_hook_types:" in content, (
        "commit-msg hook is declared but nothing installs it, so it never runs"
    )
    hook_types = content.split("default_install_hook_types:")[1].split("\n")[0]
    assert "commit-msg" in hook_types, f"commit-msg missing from install hook types: {hook_types}"
    assert "pre-commit" in hook_types, f"pre-commit missing from install hook types: {hook_types}"


def test_precommit_interrogate_checks_only_src(copie_session_default):
    """Test that interrogate pre-commit hook only checks src/ directory."""
    result = copie_session_default

    precommit_path = result.project_dir / ".pre-commit-config.yaml"
    assert precommit_path.is_file()

    content = precommit_path.read_text(encoding="utf-8")

    # Should have interrogate configured to check only src/
    assert "interrogate" in content
    assert "files: ^src/" in content
    assert r"exclude: .*_version\.py$" in content


def test_precommit_ty_uses_uv_run(copie_session_default):
    """Test that ty pre-commit hook uses uv run with proper configuration."""
    result = copie_session_default

    precommit_path = result.project_dir / ".pre-commit-config.yaml"
    assert precommit_path.is_file()

    content = precommit_path.read_text(encoding="utf-8")

    # Should have ty configured with uv run, pinned to uv.lock via --locked
    assert "id: ty" in content
    assert "entry: uv run --locked ty check src" in content
    assert "pass_filenames: false" in content


def test_precommit_whole_project_gates_run_at_pre_push(copie_session_default):
    """The refusing whole-project gates run at pre-push, not on every commit.

    ty, interrogate, and no-rst-citations do not autofix and score the whole project, so
    running them at pre-commit only refuses commits and fires on old code during a rebase.
    They move to the pre-push stage, and `default_install_hook_types` must name pre-push or
    the hook is declared but never wired into .git/hooks -- a gate that exists only on paper.
    """
    content = (copie_session_default.project_dir / ".pre-commit-config.yaml").read_text(encoding="utf-8")

    # Parse per-hook so a stray stages line elsewhere cannot satisfy the check for the
    # wrong hook: slice from each id to the next hook declaration (or end of file).
    for hook_id in ("interrogate", "no-rst-citations", "ty"):
        block = content.split(f"id: {hook_id}", 1)[1].split("- id:", 1)[0]
        assert "stages: [pre-push]" in block, f"{hook_id} should run at pre-push, not pre-commit"

    # The stage is actually installed, not merely declared.
    hook_types = content.split("default_install_hook_types:")[1].split("\n")[0]
    assert "pre-push" in hook_types, f"pre-push missing from install hook types: {hook_types}"


def test_noxfile_fix_runs_pre_push_stage(copie_session_default):
    """The fix session (run by the CI lint job) also runs the pre-push-stage gates.

    The gates moved off pre-commit, and a plain `prek run` only runs the pre-commit stage,
    so without running the pre-push stage here the CI lint job would silently stop type- and
    docstring-checking (a green check measuring nothing). This is the CI-side enforcement
    that holds even when a contributor never installed local hooks.
    """
    content = (copie_session_default.project_dir / "noxfile.py").read_text(encoding="utf-8")
    fix_body = content.split("def fix(", 1)[1].split("\ndef ", 1)[0]
    assert '"--stage"' in fix_body and '"pre-push"' in fix_body, (
        "the fix session must run the pre-push stage so CI covers the moved gates"
    )


def test_install_command_forces_hook_reinstall(copie_session_default):
    """The documented install command reinstalls hooks forcibly with `prek install -f`.

    `default_install_hook_types` only wires hooks at install time, so a clone that installed
    before pre-push was added needs a forced reinstall to pick up the new stage. Without -f,
    prek chains an old shim instead of overwriting it and the pre-push gate stays unwired.
    """
    justfile = (copie_session_default.project_dir / "justfile").read_text(encoding="utf-8")
    assert "prek install -f" in justfile, "install recipe must force-reinstall hooks (prek install -f)"


def test_generated_ci_declares_rollup_gate(copie_session_default):
    """The generated CI declares the always-running roll-up gate the ruleset requires.

    test-fast is a matrix and test-full is skipped on draft PRs, so neither has a stable
    check-run name a ruleset can require. `ci-passed` depends on every blocking job and runs
    with `if: always()`, giving the ruleset one stable required check that survives matrix
    and conditional changes. (safe_load also fails if the templated YAML is malformed.)
    """
    import yaml

    wf = copie_session_default.project_dir / ".github" / "workflows" / "tests.yml"
    data = yaml.safe_load(wf.read_text(encoding="utf-8"))

    assert "ci-passed" in data["jobs"], "roll-up gate job 'ci-passed' missing from CI"
    gate = data["jobs"]["ci-passed"]
    assert gate["name"] == "CI passed"
    # if: always() so the gate reports even when a dependency failed or was skipped.
    assert str(gate.get("if")).strip() == "always()", "ci-passed must run with if: always()"
    # It must depend on the blocking jobs so their failure fails the gate. test-compat ships
    # disabled (if: false); it is still a dependency so a project that enables compat pins is
    # gated automatically, and a skipped dependency does not fail the if: always() roll-up.
    for job in ("test-fast", "test-compat", "test-full", "lint", "test_docstrings", "check_docs"):
        assert job in gate["needs"], f"ci-passed must depend on {job}"


def test_precommit_linters_are_pinned_by_uv_lock(copie_session_default):
    """Test that version-sensitive linters resolve from uv.lock, not a pre-commit rev.

    uv.lock is the single source of truth for these tools, so each must run through
    `uv run --locked`. A pinned `rev:` here would let pre-commit drift from CI.
    """
    result = copie_session_default

    content = (result.project_dir / ".pre-commit-config.yaml").read_text(encoding="utf-8")

    for tool in ("interrogate", "ruff", "ruff format", "rumdl", "ty"):
        assert f"entry: uv run --locked {tool}" in content, f"{tool} does not resolve from uv.lock"

    # The upstream mirrors these hooks used to come from would reintroduce a second
    # version source alongside uv.lock.
    for mirror in ("ruff-pre-commit", "rumdl-pre-commit", "econchick/interrogate"):
        assert mirror not in content, f"{mirror} reintroduces a version source outside uv.lock"


def test_github_workflows(copie_session_default):
    """Test that GitHub workflows are properly configured."""
    result = copie_session_default

    tests_workflow = result.project_dir / ".github" / "workflows" / "tests.yml"
    assert tests_workflow.is_file()

    content = tests_workflow.read_text(encoding="utf-8")

    # Check for uv usage
    assert "astral-sh/setup-uv" in content

    # Check for ty
    assert "ty" in content, "ty not found in tests workflow"

    # Check for test_docstrings job
    assert "test_docstrings:" in content, "test_docstrings job not found in tests workflow"
    assert "nox -s test_docstrings" in content, "test_docstrings nox session not run in CI"

    # Check for test-compat job
    assert "test-compat:" in content, "test-compat job not found in tests workflow"
    assert "nox -s test_compat" in content, "test_compat nox session not run in CI"

    # Check PR title validation workflow
    pr_title_workflow = result.project_dir / ".github" / "workflows" / "pr-title.yml"
    assert pr_title_workflow.is_file(), "PR title validation workflow not found"

    pr_title_content = pr_title_workflow.read_text(encoding="utf-8")
    assert "amannn/action-semantic-pull-request" in pr_title_content
    assert "feat" in pr_title_content
    assert "fix" in pr_title_content
    assert "docs" in pr_title_content


def test_release_workflow(copie_session_default):
    """Test that release workflow includes changelog automation."""
    result = copie_session_default

    # Check changelog.yml workflow
    changelog_workflow = result.project_dir / ".github" / "workflows" / "changelog.yml"
    assert changelog_workflow.is_file()

    changelog_content = changelog_workflow.read_text(encoding="utf-8")

    # Check for git-cliff
    assert "git-cliff" in changelog_content, "git-cliff not found in changelog workflow"

    # Check for changelog job
    assert "changelog" in changelog_content.lower(), "changelog job not found in changelog workflow"

    # Check publish-release.yml workflow
    release_workflow = result.project_dir / ".github" / "workflows" / "publish-release.yml"
    assert release_workflow.is_file()

    release_content = release_workflow.read_text(encoding="utf-8")

    # Check for GitHub release creation
    assert "gh release create" in release_content or "github-release" in release_content.lower(), (
        "GitHub release creation not found"
    )


def test_commitizen_configuration(copie_session_default):
    """Test that commitizen is properly configured."""
    result = copie_session_default

    pyproject_path = result.project_dir / "pyproject.toml"
    assert pyproject_path.is_file()

    content = pyproject_path.read_text(encoding="utf-8")

    # Check for commitizen configuration
    assert "[tool.commitizen]" in content, "commitizen config not found in pyproject.toml"
    assert "cz_conventional_commits" in content, "conventional commits not configured"


def test_git_cliff_configuration(copie_session_default):
    """Test that git-cliff configuration exists."""
    result = copie_session_default

    cliff_config = result.project_dir / ".git-cliff.toml"
    assert cliff_config.is_file()

    content = cliff_config.read_text(encoding="utf-8")

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

    # Check noxfile has test_docstrings session with doctest flags
    noxfile_content = (result.project_dir / "noxfile.py").read_text(encoding="utf-8")
    assert "def test_docstrings(session:" in noxfile_content
    assert '"--doctest-modules"' in noxfile_content

    # Check justfile has test-docstrings command
    justfile_content = (result.project_dir / "justfile").read_text(encoding="utf-8")
    assert "test-docstrings:" in justfile_content
    assert "--doctest-modules" in justfile_content

    # Check hello.py has docstring examples
    hello_py = (result.project_dir / "src" / "test_project" / "hello.py").read_text(encoding="utf-8")
    assert "Examples" in hello_py
    assert ">>>" in hello_py


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
    notebook_content = hello_notebook.read_text(encoding="utf-8")
    assert "import marimo" in notebook_content
    assert "app = marimo.App" in notebook_content
    assert "plotly" in notebook_content
    assert "num_points" in notebook_content

    # Check marimo in dependencies and pytest marker for examples
    pyproject_content = (result.project_dir / "pyproject.toml").read_text(encoding="utf-8")
    assert "marimo" in pyproject_content
    assert "plotly" in pyproject_content
    assert "example: marks tests for example notebooks" in pyproject_content

    # Check noxfile has test_examples session that uses pytest
    noxfile_content = (result.project_dir / "noxfile.py").read_text(encoding="utf-8")
    assert "def test_examples(session:" in noxfile_content
    assert "pytest" in noxfile_content
    assert '"tests"' in noxfile_content
    assert '"-m"' in noxfile_content and '"example"' in noxfile_content
    assert '"-n"' in noxfile_content and '"auto"' in noxfile_content

    # Check test_examples.py is created and uses pytest parametrize
    test_examples_file = result.project_dir / "tests" / "test_examples.py"
    assert test_examples_file.is_file(), "tests/test_examples.py not created"
    test_examples_content = test_examples_file.read_text(encoding="utf-8")
    assert "pytest.mark.parametrize" in test_examples_content
    assert "pytest.mark.example" in test_examples_content
    assert "EXAMPLES_DIR.glob" in test_examples_content
    assert "subprocess.run" in test_examples_content
    assert '["python", str(notebook_file)]' in test_examples_content
    assert "https://docs.marimo.io/getting_started/quickstart/#run-as-scripts" in test_examples_content
    # The failure message must use a real newline escape (single backslash). A doubled
    # backslash in the .jinja source renders as a literal two-character \n, printing the
    # diagnostic on one line with a visible \n instead of breaking it.
    assert r"failed with:\nSTDOUT" in test_examples_content, "assert message lost its newline escape"
    assert r"failed with:\\nSTDOUT" not in test_examples_content, (
        "assert message double-escapes the newline; use a single backslash in the .jinja source"
    )
    # The bounded-run guards from v0.27.0 must survive here too.
    assert "stdin=subprocess.DEVNULL" in test_examples_content
    assert "timeout=" in test_examples_content

    # Check docs/examples/ directory exists for exports
    docs_examples_dir = result.project_dir / "docs" / "examples"
    assert docs_examples_dir.is_dir(), "docs/examples/ directory not created"

    # Check justfile has example command and test-examples command
    justfile_content = (result.project_dir / "justfile").read_text(encoding="utf-8")
    assert "example file=" in justfile_content
    assert "marimo edit" in justfile_content
    assert "test-examples:" in justfile_content
    assert "pytest tests" in justfile_content
    assert "-m example" in justfile_content
    assert "-n auto" in justfile_content

    # Check examples.md exists and uses gallery placeholder
    examples_md = result.project_dir / "docs" / "pages" / "examples" / "index.md"
    assert examples_md.is_file(), "docs/pages/examples/index.md not created"
    examples_content = examples_md.read_text(encoding="utf-8")
    assert "<!-- GALLERY -->" in examples_content
    assert "## Running Examples Locally" in examples_content

    # Check mkdocs.yml includes examples in nav and has exclude_docs
    mkdocs_content = (result.project_dir / "mkdocs.yml").read_text(encoding="utf-8")
    assert "pages/examples/index.md" in mkdocs_content
    # Check for exclude_docs with CLAUDE.md files
    assert "exclude_docs:" in mkdocs_content
    assert "examples/**/CLAUDE.md" in mkdocs_content

    # Check GitHub workflow includes examples job
    tests_workflow = result.project_dir / ".github" / "workflows" / "tests.yml"
    workflow_content = tests_workflow.read_text(encoding="utf-8")
    assert "examples:" in workflow_content
    assert "nox -s test_examples" in workflow_content

    # Check README mentions examples (in "Where can I learn more?" section)
    readme_content = (result.project_dir / "README.md").read_text(encoding="utf-8")
    assert "Interactive Examples:" in readme_content or "examples/" in readme_content
    assert "marimo edit examples/hello.py" in readme_content

    # Check CONTRIBUTING mentions adding examples with new pytest approach
    contributing_content = (result.project_dir / "docs" / "pages" / "how-to" / "contribute.md").read_text(
        encoding="utf-8"
    )
    assert "### Adding Examples" in contributing_content
    assert "test_examples" in contributing_content or "test-examples" in contributing_content


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
    pyproject_content = (result.project_dir / "pyproject.toml").read_text(encoding="utf-8")
    # examples group should not exist or be empty
    assert (
        "examples = [" not in pyproject_content
        or "examples = []" in pyproject_content
        or "examples = [\n]" in pyproject_content
    )
    # marimo should not be in dependencies
    assert "marimo" not in pyproject_content
    assert "plotly" not in pyproject_content

    # Check noxfile doesn't have test_examples session
    noxfile_content = (result.project_dir / "noxfile.py").read_text(encoding="utf-8")
    assert "def test_examples(session:" not in noxfile_content

    # The example test itself must not exist at all. A previous template shipped two
    # near-duplicate .jinja sources for it -- one filename-gated, one not -- and the
    # ungated one rendered a stray 1-byte tests/test_examples.py here, invisible because
    # an empty file breaks nothing.
    assert not (result.project_dir / "tests" / "test_examples.py").exists(), (
        "tests/test_examples.py should not exist when include_examples=False"
    )

    # Check justfile doesn't have example command
    justfile_content = (result.project_dir / "justfile").read_text(encoding="utf-8")
    # Should not have the example command, but might have other content
    lines = justfile_content.split("\n")
    example_command_lines = [line for line in lines if line.strip().startswith("example:")]
    assert len(example_command_lines) == 0, "example command should not exist"

    # Check examples.md doesn't exist or is empty
    examples_md = result.project_dir / "docs" / "pages" / "examples" / "index.md"
    if examples_md.exists():
        content = examples_md.read_text(encoding="utf-8").strip()
        assert content == "", (
            f"docs/pages/examples/index.md should not exist when examples are disabled, but contains: {content[:100]}"
        )

    # Check mkdocs.yml doesn't include examples in nav
    mkdocs_content = (result.project_dir / "mkdocs.yml").read_text(encoding="utf-8")
    assert "pages/examples/index.md" not in mkdocs_content

    # Check GitHub workflow doesn't include examples job
    tests_workflow = result.project_dir / ".github" / "workflows" / "tests.yml"
    workflow_content = tests_workflow.read_text(encoding="utf-8")
    assert "test_examples" not in workflow_content


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

    # Check for GitHub configuration files. Renovate replaces Dependabot, so the
    # config lives at .github/renovate.json and dependabot.yml is gone --
    # two bots would open duplicate PRs for the same update.
    assert (result.project_dir / ".github" / "renovate.json").is_file(), ".github/renovate.json not created"
    assert not (result.project_dir / "renovate.json").exists(), (
        "a root renovate.json survives beside the .github/ copy; Renovate would read only one"
    )
    assert not (github_dir / "dependabot.yml").exists(), (
        "dependabot.yml should not be generated (replaced by renovate.json)"
    )
    assert (github_dir / "PULL_REQUEST_TEMPLATE.md").is_file(), "PR template not created"

    # Check ISSUE_TEMPLATE directory
    issue_template_dir = github_dir / "ISSUE_TEMPLATE"
    assert issue_template_dir.is_dir(), "ISSUE_TEMPLATE directory not created"
    assert (issue_template_dir / "bug_report.yml").is_file(), "bug_report.yml not created"
    assert (issue_template_dir / "feature_request.yml").is_file(), "feature_request.yml not created"
    assert (issue_template_dir / "config.yml").is_file(), "issue template config.yml not created"

    # Check workflow content uses uv
    tests_workflow_content = (workflows_dir / "tests.yml").read_text(encoding="utf-8")
    assert "astral-sh/setup-uv" in tests_workflow_content, "uv not used in tests workflow"

    # Check git-cliff.toml exists (should be included with workflows)
    assert (result.project_dir / ".git-cliff.toml").is_file(), ".git-cliff.toml not created"


def test_renovate_config_self_contained_by_default(copie):
    """With no preset, renovate.json is a full self-contained, valid config.

    An outside consumer of the template has one repo and no fleet preset to extend;
    Renovate errors on a preset it cannot read, so the default must carry its own rules.
    """
    result = copie.copy()

    renovate = result.project_dir / ".github" / "renovate.json"
    assert renovate.is_file(), ".github/renovate.json not created"

    config = json.loads(renovate.read_text(encoding="utf-8"))
    assert "packageRules" in config, "self-contained config is missing its own packageRules"
    assert not any("renovate-config" in extend for extend in config.get("extends", [])), (
        "the default config should not extend an external fleet preset"
    )


def test_renovate_config_extends_preset_when_set(copie):
    """With renovate_preset set, renovate.json is a thin stub that extends it.

    A fleet repo subscribes to one shared preset so policy lives in a single place
    instead of a copy drifting in every repo. The stub carries no inline policy.
    """
    result = copie.copy(extra_answers={"renovate_preset": "stateful-y/renovate-config"})

    renovate = result.project_dir / ".github" / "renovate.json"
    assert renovate.is_file(), ".github/renovate.json not created"

    config = json.loads(renovate.read_text(encoding="utf-8"))
    assert config.get("extends") == ["github>stateful-y/renovate-config"], (
        f"preset stub should extend the named preset, got {config.get('extends')!r}"
    )
    assert "packageRules" not in config, "a preset subscription should not inline packageRules"


def test_renovate_automerge_label_is_the_only_automerge_signal(copie_session_default):
    """The `automerge` label sits on exactly the rules that set `automerge: true`.

    renovate-automerge.yml approves a bot pull request only when it carries this label,
    so the label is the authorization boundary and not a cosmetic tag. The two halves
    fail in opposite directions and both fail quietly: a rule with `automerge: true` and
    no label produces a pull request Renovate wants merged that nothing ever approves,
    and a rule with the label but no `automerge: true` pre-approves an update nobody
    chose to automate.
    """
    config = json.loads((copie_session_default.project_dir / ".github" / "renovate.json").read_text(encoding="utf-8"))
    rules = config["packageRules"]

    labelled = {i for i, rule in enumerate(rules) if "automerge" in rule.get("addLabels", [])}
    automerged = {i for i, rule in enumerate(rules) if rule.get("automerge") is True}

    assert automerged, "no rule enables automerge, so every dependency update needs a human merge"
    assert labelled == automerged, (
        f"rules setting automerge: {sorted(automerged)}, rules adding the label: {sorted(labelled)}. "
        "The two must be the same set, or the approve-then-merge chain breaks with no error."
    )


def test_renovate_automerge_scope_excludes_majors_and_runtime_dependencies(copie_session_default):
    """Nothing automerges a major, and the grouped runtime dependency PR never does.

    A major can change an action's inputs or a library's API, and the `pep621` group is a
    single pull request mixing runtime and dev dependencies, so there is no safe half of
    it to merge unattended.
    """
    config = json.loads((copie_session_default.project_dir / ".github" / "renovate.json").read_text(encoding="utf-8"))

    for rule in config["packageRules"]:
        if rule.get("automerge") is not True:
            continue
        update_types = rule.get("matchUpdateTypes")
        assert update_types, f"automerge rule with no matchUpdateTypes matches majors too: {rule!r}"
        assert "major" not in update_types, f"automerge rule accepts majors: {rule!r}"
        assert "pep621" not in rule.get("matchManagers", []), (
            f"automerge rule covers the grouped runtime dependency PR: {rule!r}"
        )


def test_renovate_automerge_workflow_does_not_hardcode_a_bot_login(copie_session_default):
    """The automerge guard keys on the label, never on a bot account name.

    The account that opens the pull request is named after the GitHub App's slug, which
    differs per installation: a self-hosted App is `<app-slug>[bot]` while the hosted
    Mend app is `renovate[bot]`. A guard comparing against either literal is valid YAML
    that evaluates false forever, so the workflow runs, reports success, and approves
    nothing.
    """
    workflow = copie_session_default.project_dir / ".github" / "workflows" / "renovate-automerge.yml"
    assert workflow.is_file(), "renovate-automerge.yml not generated"
    text = workflow.read_text(encoding="utf-8")

    guard = text.split("runs-on:")[0]
    assert "[bot]'" not in guard and '[bot]"' not in guard, (
        "the automerge guard compares against a literal bot login, which differs per "
        "GitHub App installation and would make the guard silently always false"
    )
    assert "contains(github.event.pull_request.labels.*.name, 'automerge')" in guard, (
        "the automerge guard does not require the `automerge` label, so it would approve "
        "every bot pull request including majors"
    )
    assert "pull_request_target" not in text, (
        "pull_request_target grants write access to code from forks; Renovate branches are "
        "in-repo, so the plain pull_request trigger is both sufficient and safe"
    )


def test_workflows_pin_uv_nox_and_git_cliff(copie_session_default):
    """uv, nox and git-cliff are pinned to exact versions, not floating "latest".

    These three decide what runs in CI, so a floating install breaks the local == CI
    guarantee and cannot be bumped by a bot the way a pinned version can. Each pin also
    carries a `# renovate:` annotation so the custom manager in renovate.json updates it.
    """
    workflows = sorted((copie_session_default.project_dir / ".github" / "workflows").glob("*.yml"))
    assert workflows, "no workflows generated"
    joined = "\n".join(wf.read_text(encoding="utf-8") for wf in workflows)

    assert re.search(r"uv tool install nox==\d[\w.]*", joined), "nox is not pinned to an exact version"
    assert "uv tool install nox\n" not in joined, "a floating `uv tool install nox` remains"
    assert re.search(r"tool: git-cliff@\d[\w.]*", joined), "git-cliff is not pinned to an exact version"

    # The release path's own tools. `cyclonedx-bom` floated until it broke every
    # generated project's release; `twine` is the same invocation shape in the same job.
    assert re.search(r"uvx --from cyclonedx-bom==\d[\w.]*", joined), "cyclonedx-bom is not pinned to an exact version"
    assert re.search(r"uvx twine==\d[\w.]*", joined), "twine is not pinned to an exact version"

    # `--outfile` was a deprecated alias that cyclonedx-bom 7.0 removed, so the step
    # began exiting 2 with no change in any consuming repo. `--output-file` is accepted
    # by 6.x and 7.x alike, which makes it correct independently of the pin above.
    assert "--output-file " in joined, "the SBOM step does not use the supported --output-file flag"
    assert "--outfile" not in joined, "the SBOM step still passes --outfile, removed in cyclonedx-bom 7.x"

    for dep in ("astral-sh/uv", "nox", "orhun/git-cliff", "cyclonedx-bom", "twine"):
        assert f"depName={dep}" in joined, f"missing renovate annotation for {dep}, so it cannot be bumped"

    # EVERY setup-uv version pin must carry the annotation, not just one. A single
    # un-annotated step (e.g. commit-message.yml was missed once) is a pin Renovate
    # silently never bumps.
    for wf in workflows:
        lines = wf.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if line.strip().startswith("version:") and "astral-sh/setup-uv" in "\n".join(lines[max(0, i - 4) : i]):
                prev = lines[i - 1].strip() if i > 0 else ""
                assert prev.startswith("# renovate:"), (
                    f"{wf.name} line {i + 1}: a setup-uv version pin has no `# renovate:` annotation, "
                    "so Renovate cannot bump it"
                )


def test_renovate_preset_persisted_in_copier_answers(copie):
    """A chosen renovate_preset must round-trip through .copier-answers.yml.

    That file is an explicit allowlist of variables. A variable missing from it is not
    persisted, so the next `copier update` falls back to the question default and
    silently reverts the rendered renovate.json (stub -> self-contained). This guards
    the preset choice against being lost on the very next update.
    """
    result = copie.copy(extra_answers={"renovate_preset": "stateful-y/renovate-config"})

    answers = (result.project_dir / ".copier-answers.yml").read_text(encoding="utf-8")
    assert "renovate_preset:" in answers and "stateful-y/renovate-config" in answers, (
        "renovate_preset is not persisted in .copier-answers.yml; a future copier update "
        "would revert renovate.json to the self-contained config"
    )


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
        content = git_cliff.read_text(encoding="utf-8").strip()
        assert content == "", ".git-cliff.toml should be empty when GitHub Actions are disabled"


def test_markdown_docs_script_configuration(copie):
    """Test that hooks are properly configured for site preparation."""
    result = copie.copy(
        extra_answers={
            "include_examples": True,
        },
    )

    assert result.exit_code == 0

    # The explicit pre/post-build steps replaced the mkdocs build hooks; they live
    # in docs_build/build.py now, and hooks.py is gone.
    build_file = result.project_dir / BUILD_DIR / "build.py"
    assert build_file.is_file(), "docs_build/build.py not created"
    assert not (result.project_dir / BUILD_DIR / "hooks.py").exists(), "hooks.py should be gone; build.py replaced it"

    # Verify build.py has both build steps
    build_content = build_file.read_text(encoding="utf-8")
    assert "def prebuild(" in build_content, "prebuild step not found"
    assert "def postbuild(" in build_content, "postbuild step not found"

    # The work itself lives in the build-step modules; build.py only delegates.
    # Assert against the module that owns each behaviour, so this test keeps failing
    # if a step disappears rather than passing because build.py happens to name it.
    assert "_notebooks.export" in build_content, "prebuild doesn't delegate the notebook export"
    assert "_markdown_export.export" in build_content, "postbuild doesn't delegate the markdown export"

    notebooks_content = (result.project_dir / BUILD_DIR / "_notebooks.py").read_text(encoding="utf-8")
    assert "marimo" in notebooks_content.lower(), "_notebooks.py doesn't handle marimo export"
    assert "index.html" in notebooks_content, "_notebooks.py doesn't write the exported page"

    export_content = (result.project_dir / BUILD_DIR / "_markdown_export.py").read_text(encoding="utf-8")
    assert "shutil.copy2" in export_content, "_markdown_export.py doesn't copy files"
    assert "markdown" in export_content.lower(), "_markdown_export.py doesn't handle markdown files"

    # Verify mkdocs.yml wires the marker extension. The `hooks:` key is gone --
    # the successor engine does not execute it, so markers resolve through a
    # markdown extension registered in markdown_extensions instead.
    mkdocs_config = _mkdocs_config(result.project_dir)
    assert "hooks" not in mkdocs_config, "the hooks: key should be gone; the successor engine does not run it"
    extensions = [e for e in mkdocs_config["markdown_extensions"] if isinstance(e, str)]
    assert "docs_build._markers" in extensions, "mkdocs.yml doesn't register the marker extension"
    assert "docs_build._glossary" in extensions, "mkdocs.yml doesn't register the glossary extension"

    # Scripts directory may exist for other utilities
    # export_marimo_examples.py and prepare_site.py are no longer needed (replaced by build.py)


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.skip(reason="Marimo HTML export feature not fully implemented in examples.md template")
def test_marimo_notebook_export_to_html(copie):
    """Test that marimo notebooks are properly exported to standalone HTML."""
    import subprocess

    result = copie.copy(
        extra_answers={
            "include_examples": True,
        },
    )

    assert result.exit_code == 0

    # Verify docs/examples directory exists
    docs_examples_dir = result.project_dir / "docs" / "examples"
    assert docs_examples_dir.is_dir(), "docs/examples/ directory not created"

    # Run mkdocs build which triggers hooks to export notebooks
    export_result = subprocess.run(
        ["uvx", "nox", "-s", "build_docs"],
        cwd=result.project_dir,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert export_result.returncode == 0, (
        f"export_examples failed:\nSTDOUT:\n{export_result.stdout}\n\nSTDERR:\n{export_result.stderr}"
    )

    # Verify HTML file was created
    hello_html = docs_examples_dir / "hello" / "index.html"
    assert hello_html.is_file(), (
        f"hello/index.html not created. docs/examples structure: {list(docs_examples_dir.rglob('*'))}"
    )

    # Verify HTML content
    html_content = hello_html.read_text(encoding="utf-8")
    assert len(html_content) > 1000, "HTML file is suspiciously small"

    # Check for marimo WASM runtime (key indicator of HTML-WASM export)
    assert "marimo" in html_content.lower(), "HTML doesn't contain marimo references"
    assert "wasm" in html_content.lower() or "pyodide" in html_content.lower(), (
        "HTML doesn't contain WASM/Pyodide runtime indicators"
    )

    # Verify the HTML is standalone (not just a stub)
    assert "<html" in html_content.lower(), "HTML doesn't have html tag"
    assert "<script" in html_content.lower(), "HTML doesn't have script tags"

    # Verify HTML file has reasonable size (marimo HTML exports are typically 20KB+)
    html_size_kb = len(html_content) / 1024
    assert html_size_kb > 10, f"HTML file is only {html_size_kb:.1f}KB, suspiciously small"


@pytest.mark.integration
@pytest.mark.slow
def test_markdown_docs_created_and_clean(copie):
    """Test that markdown files are created during build and are clean (no HTML tags)."""
    import subprocess

    result = copie.copy(
        extra_answers={
            "include_examples": True,
        },
    )

    assert result.exit_code == 0

    # Build the docs which should create markdown copies
    build_result = subprocess.run(
        ["uvx", "nox", "-s", "build_docs"],
        cwd=result.project_dir,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert build_result.returncode == 0, (
        f"build_docs failed:\nSTDOUT:\n{build_result.stdout}\n\nSTDERR:\n{build_result.stderr}"
    )

    # Verify site directory exists
    site_dir = site_path(result.project_dir)
    assert site_dir.is_dir(), "site/ directory not created by build_docs"

    # Find all markdown files in site/
    md_files = list(site_dir.rglob("*.md"))
    assert len(md_files) > 0, f"No markdown files found in site/. Site structure: {list(site_dir.iterdir())}"

    # Verify key markdown files exist
    expected_md_files = ["index.md", "getting-started.md", "concepts.md"]
    found_names = {f.name for f in md_files}
    for expected in expected_md_files:
        assert expected in found_names, f"{expected} not found in site/. Found: {found_names}"

    # Verify markdown files contain content and are clean (no HTML tags)
    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8")
        assert len(content) > 0, f"{md_file} is empty"

        # Should not contain raw HTML tags from mkdocs-material
        # Exception: index.md can contain <div class="grid cards"> for Material CTA cards
        html_tags_to_check = ["<article", "<div class=", "<nav class=", "<header class="]
        for tag in html_tags_to_check:
            # Allow <div class=> in index.md for Material grid cards feature
            if tag == "<div class=" and md_file.name == "index.md":
                continue
            assert tag not in content, f"{md_file.name} contains HTML tag: {tag}"

        # Should contain markdown formatting
        # At least one of these markdown elements should be present
        has_markdown = any(marker in content for marker in ["# ", "## ", "- ", "* ", "[", "```", "**", "__"])
        assert has_markdown, f"{md_file.name} doesn't appear to contain markdown formatting"


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.skip(reason="Marimo HTML export feature not fully implemented in examples.md template")
def test_three_tier_documentation_system(copie):
    """Test that all three documentation tiers work together."""
    import subprocess

    result = copie.copy(
        extra_answers={
            "include_examples": True,
        },
    )

    assert result.exit_code == 0

    # Tier 1: Verify embedded marimo setup in examples.md
    examples_md = result.project_dir / "docs" / "pages" / "examples" / "index.md"
    examples_content = examples_md.read_text(encoding="utf-8")
    # Check for marimo-embed directive with inline code
    has_marimo = "/// marimo-embed" in examples_content and "@app.cell" in examples_content
    assert has_marimo, "Embedded marimo notebook not found in examples.md"

    # Tier 2: Build docs which triggers hooks to export standalone HTML
    export_result = subprocess.run(
        ["uvx", "nox", "-s", "build_docs"],
        cwd=result.project_dir,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert export_result.returncode == 0, (
        f"build_docs failed:\nSTDOUT:\n{export_result.stdout}\n\nSTDERR:\n{export_result.stderr}"
    )
    standalone_html = result.project_dir / "docs" / "examples" / "hello" / "index.html"
    assert standalone_html.is_file(), "Standalone HTML not created (Tier 2)"

    # Verify examples.md links to standalone HTML
    assert "Standalone HTML Notebooks" in examples_content, "No standalone section in examples.md"
    assert "../examples/hello/" in examples_content, "No link to standalone HTML in examples.md"

    # Verify mkdocs excludes standalone HTML from processing
    mkdocs_yml = result.project_dir / "mkdocs.yml"
    mkdocs_content = mkdocs_yml.read_text(encoding="utf-8")
    assert "exclude_docs:" in mkdocs_content, "mkdocs.yml doesn't have exclude_docs"
    assert "examples/**/index.html" in mkdocs_content, "mkdocs.yml doesn't exclude standalone HTML files"
    assert "examples/**/CLAUDE.md" in mkdocs_content, "mkdocs.yml doesn't exclude CLAUDE.md files"

    # Tier 3: Verify markdown copies were created
    markdown_copy = site_path(result.project_dir) / "index.md"
    assert markdown_copy.is_file(), "Markdown copy not created (Tier 3)"

    # Verify all three tiers are present
    assert examples_md.is_file(), "Tier 1 (embedded) missing"
    assert standalone_html.is_file(), "Tier 2 (standalone HTML) missing"
    assert markdown_copy.is_file(), "Tier 3 (markdown copies) missing"


@pytest.mark.integration
@pytest.mark.slow
def test_generated_package_can_be_installed(copie):
    """Smoke test: verify the generated package can be installed with uv sync.

    This test validates that:
    - pyproject.toml is valid
    - All dependencies can be resolved
    - The package can be installed in a virtual environment
    """
    import subprocess

    result = copie.copy(extra_answers={"include_examples": True})
    assert result.exit_code == 0

    # Run uv sync to install the package and all dependencies
    sync_result = subprocess.run(
        ["uv", "sync", "--all-groups"],
        cwd=result.project_dir,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert sync_result.returncode == 0, (
        f"uv sync failed:\nSTDOUT:\n{sync_result.stdout}\n\nSTDERR:\n{sync_result.stderr}"
    )

    # Verify the package can be imported
    import_result = subprocess.run(
        ["uv", "run", "python", "-c", "import test_project; print(test_project.__version__)"],
        cwd=result.project_dir,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert import_result.returncode == 0, (
        f"Package import failed:\nSTDOUT:\n{import_result.stdout}\n\nSTDERR:\n{import_result.stderr}"
    )


@pytest.mark.integration
@pytest.mark.slow
def test_generated_project_nox_sessions(copie_session_default):
    """Consolidated smoke test: run all nox sessions on a generated project.

    This comprehensive test validates that all development workflows work:
    - test_coverage: Tests run and coverage is generated
    - lint: Code quality checks pass (ruff, ty)
    - test_docstrings: Doctests pass
    - test_examples: Example notebooks execute successfully
    - build_docs: Documentation builds without errors

    Using session-scoped fixture to avoid regenerating project multiple times.
    This test replaces individual session tests for better performance.
    """
    import subprocess

    result = copie_session_default
    assert result.exit_code == 0

    # Define all nox sessions to test with timeouts
    sessions_to_test = [
        ("test_coverage", 180, "Tests and coverage generation"),
        ("lint", 120, "Code quality checks (ruff + ty)"),
        ("test_docstrings", 120, "Docstring tests"),
        ("test_examples", 120, "Example notebook execution"),
        ("build_docs", 180, "Documentation build"),
    ]

    # Run each session and collect results
    for session_name, timeout, description in sessions_to_test:
        session_result = subprocess.run(
            ["uvx", "nox", "-s", session_name],
            cwd=result.project_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

        assert session_result.returncode == 0, (
            f"Session '{session_name}' ({description}) failed:\n"
            f"STDOUT:\n{session_result.stdout}\n\n"
            f"STDERR:\n{session_result.stderr}"
        )

    # Verify expected outputs exist
    assert (site_path(result.project_dir) / "index.html").is_file(), "Docs site not generated"
    # Under `.artifacts/`, not the project root: the coverage paths are configured in
    # pyproject.toml so no report lands beside the source. Asserting the old root paths
    # here would fail the moment they moved, which is the point -- but asserting only
    # "somewhere" would pass even if a report reappeared at the root.
    artifacts = result.project_dir / ".artifacts"
    assert (artifacts / ".coverage").exists() or (artifacts / "coverage.xml").exists(), (
        "Coverage file not generated under .artifacts/"
    )

    strays = [
        name
        for name in ("site", "htmlcov", "coverage.xml", ".coverage", ".nox", ".pytest_cache", ".ruff_cache")
        if (result.project_dir / name).exists()
    ]
    assert not strays, f"real nox sessions dropped output at the project root: {strays}"


@pytest.mark.integration
@pytest.mark.slow
def test_generated_source_files_are_valid_python(copie):
    """Smoke test: validate that all generated Python files are syntactically correct.

    This uses Python's ast module to parse all generated .py files.
    """
    import ast

    result = copie.copy(extra_answers={"include_examples": True})
    assert result.exit_code == 0

    # Find all Python files the template renders, excluding build output and
    # environments. `.artifacts/` holds the nox environments now, so without it this
    # walk parses every third-party package a session installed.
    python_files = []
    for py_file in result.project_dir.rglob("*.py"):
        parts = set(py_file.relative_to(result.project_dir).parts)
        if parts & {".artifacts", ".venv", "site", "__pycache__", ".nox"}:
            continue
        python_files.append(py_file)

    assert len(python_files) > 0, "No Python files found in generated project"

    # Try to parse each Python file
    for py_file in python_files:
        try:
            content = py_file.read_text(encoding="utf-8")
            ast.parse(content)
        except SyntaxError as e:
            pytest.fail(f"Syntax error in {py_file.relative_to(result.project_dir)}: {e}")


@pytest.mark.integration
def test_copier_answers_file_generated(copie):
    """Test that .copier-answers.yml is generated for template updates.

    This file is critical for running 'copier update' in the future.
    """
    result = copie.copy(extra_answers={"project_name": "Test Project"})
    assert result.exit_code == 0

    copier_answers = result.project_dir / ".copier-answers.yml"
    assert copier_answers.is_file(), ".copier-answers.yml not generated"

    # Verify it contains copier metadata (answers may not be included by default)
    content = copier_answers.read_text(encoding="utf-8")
    assert "_commit:" in content or "_src_path:" in content  # copier metadata


def test_copier_answers_stores_all_user_inputs(copie):
    """Test that .copier-answers.yml stores all user answers for template updates.

    This is essential for 'copier update' to work correctly.
    """
    custom_answers = {
        "project_name": "My Test Package",
        "package_name": "my_test_pkg",
        "project_slug": "my-test-package",
        "description": "A custom test description",
        "author_name": "Jane Developer",
        "author_email": "jane@example.com",
        "github_username": "janedev",
        "min_python_version": "3.12",
        "max_python_version": "3.13",
        "license": "Apache-2.0",
        "include_actions": False,
        "include_examples": False,
    }

    result = copie.copy(extra_answers=custom_answers)
    assert result.exit_code == 0

    copier_answers = result.project_dir / ".copier-answers.yml"
    assert copier_answers.is_file()

    content = copier_answers.read_text(encoding="utf-8")

    # Verify copier metadata is present
    assert "_commit:" in content, "Missing _commit in .copier-answers.yml"
    assert "_src_path:" in content, "Missing _src_path in .copier-answers.yml"
    assert "gh:stateful-y/python-package-copier" in content

    # Verify all user answers are stored
    assert "author_email: jane@example.com" in content
    assert "author_name: Jane Developer" in content
    assert "description: A custom test description" in content
    assert "github_username: janedev" in content
    assert "include_actions: false" in content or "include_actions: False" in content
    assert "include_examples: false" in content or "include_examples: False" in content
    assert "license: Apache-2.0" in content
    assert "max_python_version: '3.13'" in content or "max_python_version: 3.13" in content
    assert "min_python_version: '3.12'" in content or "min_python_version: 3.12" in content
    assert "package_name: my_test_pkg" in content
    assert "project_name: My Test Package" in content
    assert "project_slug: my-test-package" in content
    # uv_version is deliberately NOT recorded. It used to be an answer, which meant
    # every repo stored the version a second time in a file Renovate cannot see; once
    # Renovate advanced the real pin, the answers file asserted a uv nothing ran, and
    # any file the template later delivered rendered from the stale value. uv is now a
    # literal in the template's workflows, maintained like nox and git-cliff, so there
    # is no second copy to go stale and nothing to record here.
    assert "uv_version" not in content, "uv_version is a template literal now and must not be recorded as an answer"


def test_max_python_version_in_classifiers(copie):
    """Test that pyproject.toml classifiers include all Python versions from min to max."""
    result = copie.copy(
        extra_answers={
            "min_python_version": "3.11",
            "max_python_version": "3.13",
        },
    )
    assert result.exit_code == 0

    pyproject_path = result.project_dir / "pyproject.toml"
    content = pyproject_path.read_text(encoding="utf-8")

    # Should include 3.11, 3.12, 3.13
    assert '"Programming Language :: Python :: 3.11"' in content
    assert '"Programming Language :: Python :: 3.12"' in content
    assert '"Programming Language :: Python :: 3.13"' in content
    # Should NOT include 3.14
    assert '"Programming Language :: Python :: 3.14"' not in content


def test_max_python_version_single_version(copie):
    """Test that when min equals max, only one version classifier is included."""
    result = copie.copy(
        extra_answers={
            "min_python_version": "3.12",
            "max_python_version": "3.12",
        },
    )
    assert result.exit_code == 0

    pyproject_path = result.project_dir / "pyproject.toml"
    content = pyproject_path.read_text(encoding="utf-8")

    # Should only include 3.12
    assert '"Programming Language :: Python :: 3.12"' in content
    # Should NOT include others
    assert '"Programming Language :: Python :: 3.11"' not in content
    assert '"Programming Language :: Python :: 3.13"' not in content
    assert '"Programming Language :: Python :: 3.14"' not in content


def test_max_python_version_in_noxfile(copie):
    """Test that noxfile uses max_python_version to limit Python versions."""
    result = copie.copy(
        extra_answers={
            "min_python_version": "3.11",
            "max_python_version": "3.12",
        },
    )
    assert result.exit_code == 0

    noxfile_path = result.project_dir / "noxfile.py"
    content = noxfile_path.read_text(encoding="utf-8")

    # Should have both MIN_VERSION and MAX_VERSION constants
    assert 'MIN_VERSION = "3.11"' in content
    assert 'MAX_VERSION = "3.12"' in content
    # Should filter versions with both min and max
    assert "v >= MIN_VERSION and v <= MAX_VERSION" in content


def test_max_python_version_in_github_workflows(copie):
    """Test that GitHub workflow matrix uses max_python_version."""
    result = copie.copy(
        extra_answers={
            "min_python_version": "3.12",
            "max_python_version": "3.13",
            "include_actions": True,
        },
    )
    assert result.exit_code == 0

    tests_workflow = result.project_dir / ".github" / "workflows" / "tests.yml"
    content = tests_workflow.read_text(encoding="utf-8")

    # Should include 3.12 and 3.13 in matrix
    assert '"3.12"' in content
    assert '"3.13"' in content
    # Should NOT include 3.11 or 3.14
    assert '"3.11"' not in content
    assert '"3.14"' not in content


def test_max_python_version_full_range(copie):
    """Test max_python_version with full range 3.11-3.14."""
    result = copie.copy(
        extra_answers={
            "min_python_version": "3.11",
            "max_python_version": "3.14",
        },
    )
    assert result.exit_code == 0

    # Check pyproject.toml classifiers
    pyproject_path = result.project_dir / "pyproject.toml"
    pyproject_content = pyproject_path.read_text(encoding="utf-8")
    assert '"Programming Language :: Python :: 3.11"' in pyproject_content
    assert '"Programming Language :: Python :: 3.12"' in pyproject_content
    assert '"Programming Language :: Python :: 3.13"' in pyproject_content
    assert '"Programming Language :: Python :: 3.14"' in pyproject_content

    # Check noxfile
    noxfile_path = result.project_dir / "noxfile.py"
    noxfile_content = noxfile_path.read_text(encoding="utf-8")
    assert 'MIN_VERSION = "3.11"' in noxfile_content
    assert 'MAX_VERSION = "3.14"' in noxfile_content

    # Check GitHub workflow
    tests_workflow = result.project_dir / ".github" / "workflows" / "tests.yml"
    workflow_content = tests_workflow.read_text(encoding="utf-8")
    assert '"3.11"' in workflow_content
    assert '"3.12"' in workflow_content
    assert '"3.13"' in workflow_content
    assert '"3.14"' in workflow_content


def test_max_python_version_requires_python_unchanged(copie):
    """Test that max_python_version doesn't affect requires-python (only min matters)."""
    result = copie.copy(
        extra_answers={
            "min_python_version": "3.12",
            "max_python_version": "3.13",
        },
    )
    assert result.exit_code == 0

    pyproject_path = result.project_dir / "pyproject.toml"
    content = pyproject_path.read_text(encoding="utf-8")

    # requires-python should only use min_python_version
    assert 'requires-python = ">=3.12"' in content
    # Should NOT mention max version in requires-python
    assert "<=3.13" not in content


def test_max_python_version_validation_fails_when_less_than_min(copie):
    """Test that copier validation fails when max_python_version < min_python_version."""
    import pytest

    with pytest.raises(ValueError, match="Validation error.*max_python_version.*Maximum Python version must be"):
        copie.copy(
            extra_answers={
                "min_python_version": "3.13",
                "max_python_version": "3.11",  # Invalid: less than min
            },
        )


def test_max_python_version_validation_passes_when_equal_to_min(copie):
    """Test that validation passes when max_python_version equals min_python_version."""
    result = copie.copy(
        extra_answers={
            "min_python_version": "3.12",
            "max_python_version": "3.12",  # Valid: equal to min
        },
    )

    # Should succeed
    assert result.exit_code == 0
    assert result.exception is None


@pytest.mark.integration
@pytest.mark.slow
def test_example_tests_run_successfully_with_pytest(copie):
    """Test that generated example tests run successfully using pytest directly."""
    import subprocess

    result = copie.copy(
        extra_answers={
            "include_examples": True,
        },
    )

    assert result.exit_code == 0

    # Install dependencies in the generated project
    install_result = subprocess.run(
        ["uv", "sync", "--group", "tests", "--group", "examples"],
        cwd=result.project_dir,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert install_result.returncode == 0, (
        f"uv sync failed:\nSTDOUT:\n{install_result.stdout}\n\nSTDERR:\n{install_result.stderr}"
    )

    # Run the example tests using pytest directly (disable coverage for this test)
    test_result = subprocess.run(
        ["uv", "run", "pytest", "tests/test_examples.py", "-m", "example", "-v", "--no-cov"],
        cwd=result.project_dir,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert test_result.returncode == 0, (
        f"pytest test_examples.py failed:\nSTDOUT:\n{test_result.stdout}\n\nSTDERR:\n{test_result.stderr}"
    )

    # Verify test output shows the notebook was tested
    assert "test_notebook_runs_without_error[" in test_result.stdout
    assert "notebook_file" in test_result.stdout  # pytest parametrize creates notebook_file0, etc.
    assert "passed" in test_result.stdout.lower()


@pytest.mark.integration
@pytest.mark.slow
def test_example_tests_run_successfully_with_nox(copie):
    """Test that generated example tests run successfully using nox test_examples session."""
    import subprocess

    result = copie.copy(
        extra_answers={
            "include_examples": True,
        },
    )

    assert result.exit_code == 0

    # Run the test_examples nox session
    nox_result = subprocess.run(
        ["uvx", "nox", "-s", "test_examples"],
        cwd=result.project_dir,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert nox_result.returncode == 0, (
        f"nox test_examples failed:\nSTDOUT:\n{nox_result.stdout}\n\nSTDERR:\n{nox_result.stderr}"
    )

    # Verify nox output shows tests ran
    output = nox_result.stdout + nox_result.stderr
    assert "test_examples" in output
    assert "passed" in output.lower() or "1 passed" in output


@pytest.mark.integration
@pytest.mark.slow
def test_generated_project_all_tests_pass(copie):
    """Test that all tests in a generated project pass, including examples."""
    import subprocess

    result = copie.copy(
        extra_answers={
            "include_examples": True,
        },
    )

    assert result.exit_code == 0

    # Install dependencies
    install_result = subprocess.run(
        ["uv", "sync", "--group", "tests", "--group", "examples"],
        cwd=result.project_dir,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert install_result.returncode == 0, (
        f"uv sync failed:\nSTDOUT:\n{install_result.stdout}\n\nSTDERR:\n{install_result.stderr}"
    )

    # Run all tests (including example tests) - disable coverage
    test_result = subprocess.run(
        ["uv", "run", "pytest", "tests/", "-v", "--no-cov"],
        cwd=result.project_dir,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert test_result.returncode == 0, (
        f"pytest failed:\nSTDOUT:\n{test_result.stdout}\n\nSTDERR:\n{test_result.stderr}"
    )

    # Verify both regular tests and example tests ran
    assert "test_hello.py" in test_result.stdout
    assert "test_examples.py" in test_result.stdout
    assert "notebook_file" in test_result.stdout  # parametrized test name
    assert "passed" in test_result.stdout.lower()


def test_code_of_conduct_content(copie):
    """Test that CODE_OF_CONDUCT.md is generated with correct email."""
    custom_email = "test@example.com"
    result = copie.copy(extra_answers={"author_email": custom_email})

    assert result.exit_code == 0
    assert result.exception is None

    coc_path = result.project_dir / "CODE_OF_CONDUCT.md"
    assert coc_path.is_file()

    content = coc_path.read_text(encoding="utf-8")
    assert f"contacting the project team at {custom_email}" in content
    assert "gtauzin@stateful-y.io" not in content


def test_update_from_template_skill_generated(copie_session_default):
    """Test that the update-from-template skill is included in generated projects."""
    result = copie_session_default

    skill_dir = result.project_dir / ".github" / "skills" / "update-from-template"
    assert skill_dir.is_dir(), "Missing .github/skills/update-from-template/"

    skill_md = skill_dir / "SKILL.md"
    assert skill_md.is_file(), "Missing SKILL.md"

    content = skill_md.read_text(encoding="utf-8")
    assert "name: update-from-template" in content
    assert "copier update" in content

    # Check reference files
    refs_dir = skill_dir / "references"
    assert refs_dir.is_dir(), "Missing references/"
    assert (refs_dir / "file-classification.md").is_file(), "Missing file-classification.md"
    assert (refs_dir / "conflict-resolution.md").is_file(), "Missing conflict-resolution.md"


def test_claude_skills_generated(copie_session_default):
    """Test that Claude Code skills are included in generated projects."""
    result = copie_session_default

    skills_dir = result.project_dir / ".claude" / "skills"
    assert skills_dir.is_dir(), "Missing .claude/skills/"

    # Mirrors .github/skills so both assistants offer the same skills.
    github_skills = {p.name for p in (result.project_dir / ".github" / "skills").iterdir()}
    claude_skills = {p.name for p in skills_dir.iterdir()}
    assert claude_skills == github_skills, f"Skill sets diverged: {claude_skills ^ github_skills}"

    github_skills_dir = result.project_dir / ".github" / "skills"
    for name in claude_skills:
        claude_skill = skills_dir / name / "SKILL.md"
        github_skill = github_skills_dir / name / "SKILL.md"
        assert claude_skill.is_file(), f"Missing {name}/SKILL.md"
        # The two copies are hand-mirrored; a divergence ships inconsistent
        # behavior to the two assistants. Assert byte-identity, not just presence.
        assert claude_skill.read_text(encoding="utf-8") == github_skill.read_text(encoding="utf-8"), (
            f"{name}/SKILL.md differs between .claude/skills and .github/skills"
        )


def test_claude_skills_not_gitignored(copie_session_default):
    """Test that generated projects track .claude/skills/ but ignore personal config.

    ".claude/" would exclude the directory outright and git never descends into an
    excluded directory, so the "!.claude/skills/" negation would silently not apply.
    """
    result = copie_session_default

    gitignore = (result.project_dir / ".gitignore").read_text(encoding="utf-8")
    assert ".claude/*" in gitignore, "Must use '.claude/*' so the negation is reachable"
    assert "!.claude/skills/" in gitignore, "Missing negation to track shipped skills"
    assert not re.search(r"^\.claude/$", gitignore, re.MULTILINE), (
        "'.claude/' excludes the directory and makes '!.claude/skills/' unreachable"
    )


# The build steps the docs tooling imports as siblings. They are plain top-level
# module names, so `sys.modules` caches them globally and a second project would
# silently reuse the first project's copies -- see _load_markers.
_BUILD_STEP_MODULES = ("_api_pages", "_notebooks", "_markdown_export")


def _load_markers(project_dir, unique_suffix):
    """Import a generated docs_build/_markers.py under a unique module name.

    The module name must be unique per project: importing two differently
    generated marker modules under one name makes ``sys.modules`` return the
    first, so the second variant is never actually exercised and the test passes
    while asserting nothing.

    The same trap is wider than it looks. ``_markers.py`` puts its own directory
    on ``sys.path`` and imports ``_api_pages`` and the shared ``_git_ref`` helper
    as plain top-level names, which ``sys.modules`` caches globally -- so the
    *second* project loaded in a session would get the first project's build
    steps, pointed at the first project's source tree, while its own markers
    module looked correctly isolated. Purging those names before each load is
    what keeps the isolation real; ``sys.path.insert(0, ...)`` inside
    ``_markers.py`` then resolves them against this project.

    Reach the build steps through the returned module (``markers._api_pages``),
    not by importing them directly -- that is the copy bound to this project.
    Reset caches through the returned module (``markers.reset_caches()``) so the
    reset lands on the very caches the marker builders read.
    """
    import importlib.util

    for name in (*_BUILD_STEP_MODULES, "_git_ref", "_markers"):
        sys.modules.pop(name, None)

    spec = importlib.util.spec_from_file_location(
        f"generated_markers_{unique_suffix}", project_dir / BUILD_DIR / "_markers.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_build(project_dir, unique_suffix):
    """Import a generated docs_build/build.py under a unique module name.

    ``build.py`` hosts the explicit pre/post-build steps (``prebuild`` /
    ``postbuild``) that replaced the mkdocs ``on_pre_build`` / ``on_post_build``
    hooks, and imports ``_api_pages``, ``_markdown_export`` and (with examples)
    ``_notebooks`` as plain top-level names. Same isolation trap as
    ``_load_markers``: purge the build steps before each load, or a second
    project binds the first project's steps. Reach the steps through the returned
    module (``build._notebooks`` / ``build._markdown_export`` / ``build._api_pages``).
    """
    import importlib.util

    for name in (*_BUILD_STEP_MODULES, "_git_ref"):
        sys.modules.pop(name, None)

    spec = importlib.util.spec_from_file_location(
        f"generated_build_{unique_suffix}", project_dir / BUILD_DIR / "build.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_git_ref(project_dir, unique_suffix):
    """Import a generated docs_build/_git_ref.py under a unique module name.

    ``_git_ref.py`` is the single definition of "which commit is this build",
    shared by the marker and source-link extensions. It imports no build steps,
    but a unique module name per load matches the isolation discipline the other
    loaders use and keeps its module cache (``_CACHE``) from bleeding between
    projects.
    """
    import importlib.util

    for name in (*_BUILD_STEP_MODULES, "_git_ref"):
        sys.modules.pop(name, None)

    spec = importlib.util.spec_from_file_location(
        f"generated_git_ref_{unique_suffix}", project_dir / BUILD_DIR / "_git_ref.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_glossary(project_dir, unique_suffix):
    """Import a generated docs_build/_glossary.py under a unique module name.

    The glossary extension imports ``_current_page`` from ``_markers`` as a plain
    top-level name, which pulls in ``_markers``, ``_git_ref`` and the build steps
    -- all cached globally by ``sys.modules``. Purge them (``_markers`` included)
    before each load, or a second project's glossary binds the first project's
    modules and reads the wrong glossary file. The linker keeps no cache, so
    nothing else needs resetting between calls.
    """
    import importlib.util

    for name in (*_BUILD_STEP_MODULES, "_git_ref", "_markers"):
        sys.modules.pop(name, None)

    spec = importlib.util.spec_from_file_location(
        f"generated_glossary_{unique_suffix}", project_dir / BUILD_DIR / "_glossary.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _reset_hook_caches(markers):
    """Clear every per-build cache the docs tooling reaches, across all modules.

    Tests used to do ``markers._SUBMODULE_CACHE = None``. After the build steps
    were split out that assignment still *succeeds* -- it simply creates a new,
    unread attribute on the markers module -- while the real cache in
    ``_api_pages`` stays populated and leaks into the next test. Calling the
    production reset is the only version that cannot drift from what a build
    actually does.
    """
    markers.reset_caches()


def _write_reexport_package(project_dir, package_name):
    """Lay down a package whose public API is exposed entirely by re-export."""
    pkg = project_dir / "src" / package_name
    sub = pkg / "shapes"
    sub.mkdir(parents=True, exist_ok=True)
    (sub / "_impl.py").write_text(
        '"""Private implementation module."""\n\n\n'
        'class Circle:\n    """A round shape."""\n\n\n'
        'class Square:\n    """A boxy shape."""\n\n\n'
        'def area(shape):\n    """Compute an area."""\n    return 0\n',
        encoding="utf-8",
    )
    (sub / "__init__.py").write_text(
        '"""Shapes."""\n\n'
        "from pathlib import Path\n"
        f"from {package_name}.shapes._impl import Circle, area\n"
        "from ._impl import Square as Box\n\n"
        "MAX_SIDES = 4\n\n"
        '__all__ = ["Box", "Circle", "MAX_SIDES", "area"]\n',
        encoding="utf-8",
    )

    # A package with NO __all__: here the package-root guard in
    # _resolve_import_from is what must reject `from pathlib import Path`. The
    # __all__-bearing package above cannot exercise it -- the filter rejects
    # Path first, so the guard is never consulted.
    noall = pkg / "noall"
    noall.mkdir(parents=True, exist_ok=True)
    (noall / "_impl.py").write_text('"""Impl."""\n\n\nclass Gadget:\n    """A gadget."""\n', encoding="utf-8")
    (noall / "__init__.py").write_text(
        '"""No dunder all."""\n\nfrom pathlib import Path\nfrom ._impl import Gadget\n',
        encoding="utf-8",
    )

    # A package exposing an optional extra, guarding its re-exports in a try block.
    optional = pkg / "optional"
    optional.mkdir(parents=True, exist_ok=True)
    (optional / "_impl.py").write_text(
        '"""Optional implementation."""\n\n\nclass Widget:\n    """An optional widget."""\n',
        encoding="utf-8",
    )
    (optional / "__init__.py").write_text(
        '"""Optional feature."""\n\n'
        "try:\n"
        f"    from {package_name}.optional._impl import Widget\n"
        "except ImportError as err:  # pragma: no cover\n"
        '    raise ImportError("install extras") from err\n\n'
        '__all__ = ["Widget"]\n',
        encoding="utf-8",
    )
    return pkg


def test_reexported_symbols_resolve(copie_session_minimal):
    """Re-exported symbols resolve, and the API page members table populates."""
    project_dir = copie_session_minimal.project_dir
    _write_reexport_package(project_dir, "minimal_project")
    markers = _load_markers(project_dir, "reexport")

    members = markers._get_public_members(project_dir, "shapes")
    names = {e["name"] for e in members["classes"] + members["functions"]}

    # Re-exported classes and functions are found, despite the __init__ declaring none.
    assert "Circle" in names, "re-exported class not resolved"
    assert "area" in names, "re-exported function not resolved"
    # Aliased re-export resolves under the exposed name, not the declared one.
    assert "Box" in names, "aliased re-export not resolved under its exposed name"
    assert "Square" not in names, "aliased re-export leaked its declared name"
    # __all__ filters, it does not authorise: a constant has no page, so it must not resolve.
    assert "MAX_SIDES" not in names, "__all__-listed constant resolved but has no page"
    # An import that leaves the package is not part of this package's API.
    assert "Path" not in names, "incidental third-party import resolved"

    # Classes and functions are bucketed correctly, with descriptions from the declaring module.
    assert {e["name"] for e in members["classes"]} == {"Circle", "Box"}
    assert {e["name"] for e in members["functions"]} == {"area"}
    assert next(e for e in members["classes"] if e["name"] == "Circle")["doc"] == "A round shape."


def test_reexports_guarded_by_try_resolve(copie_session_minimal):
    """Re-exports guarded by a try block (the optional-extra idiom) still resolve.

    ``ast.iter_child_nodes`` sees only the ``Try`` node, so a top-level-only
    scan silently renders an empty API page for these packages.
    """
    project_dir = copie_session_minimal.project_dir
    _write_reexport_package(project_dir, "minimal_project")
    markers = _load_markers(project_dir, "tryblock")

    members = markers._get_public_members(project_dir, "optional")
    names = {e["name"] for e in members["classes"] + members["functions"]}

    assert "Widget" in names, "re-export inside a try block was not resolved"
    assert next(e for e in members["classes"] if e["name"] == "Widget")["doc"] == "An optional widget."


def test_api_name_lookup_without_importing_package(copie_session_minimal):
    """The lookup is built by static analysis, never by importing the package."""
    import sys

    project_dir = copie_session_minimal.project_dir
    _write_reexport_package(project_dir, "minimal_project")
    markers = _load_markers(project_dir, "noimport")
    _reset_hook_caches(markers)

    lookup = markers._api_pages._get_api_name_lookup(project_dir)

    assert lookup.get("Circle") == "minimal_project.shapes.Circle", (
        f"re-exported symbol not in lookup: {sorted(lookup)}"
    )
    assert "minimal_project" not in sys.modules, "the markers module imported the generated package"


def test_api_name_lookup_every_name_has_a_page(copie_session_minimal):
    """Interlock: every resolvable name has a generated page to link to."""
    project_dir = copie_session_minimal.project_dir
    _write_reexport_package(project_dir, "minimal_project")
    markers = _load_markers(project_dir, "interlock")
    _reset_hook_caches(markers)

    markers._api_pages._generate_api_pages(project_dir)
    generated = {p.stem for p in (project_dir / "docs" / "pages" / "api" / "generated").glob("*.md")}
    lookup = markers._api_pages._get_api_name_lookup(project_dir)

    # Guard against a vacuous pass: the re-exported symbols must actually be under test.
    assert "Circle" in lookup, f"re-export package not picked up; lookup={sorted(lookup)}"
    missing = sorted(q for q in lookup.values() if q not in generated)
    assert not missing, f"lookup resolves names with no generated page: {missing}"


def test_api_name_lookup_available_without_examples(copie_session_minimal):
    """The lookup is not gated behind include_examples."""
    build = copie_session_minimal.project_dir / BUILD_DIR
    api_pages_source = (build / "_api_pages.py").read_text(encoding="utf-8")
    markers_source = (build / "_markers.py").read_text(encoding="utf-8")
    assert "def _get_api_name_lookup" in api_pages_source, "lookup missing when examples are disabled"
    assert "_API_NAME_LOOKUP_CACHE" in api_pages_source, "lookup cache missing when examples are disabled"
    assert "def _get_notebook_api_usage" not in markers_source, "gallery code leaked into a no-examples project"
    assert not (build / "_notebooks.py").exists(), "the notebook export module leaked into a no-examples project"


def test_api_name_lookup_shared_with_notebook_usage(copie_session_default):
    """The gallery consumes the shared lookup instead of building its own map."""
    markers_source = (copie_session_default.project_dir / BUILD_DIR / "_markers.py").read_text(encoding="utf-8")
    api_pages_source = (copie_session_default.project_dir / BUILD_DIR / "_api_pages.py").read_text(encoding="utf-8")
    # Declared once, in the module that owns discovery; imported by name here so
    # the gallery and the generator cannot disagree about what a symbol is called.
    assert "def _get_api_name_lookup" in api_pages_source
    assert "def _get_api_name_lookup" not in markers_source, "the lookup was redeclared instead of imported"
    assert "_get_api_name_lookup," in markers_source, "_markers.py does not import the shared lookup"
    assert "name_to_qualified = _get_api_name_lookup(project_root)" in markers_source, (
        "_get_notebook_api_usage must consume the shared lookup, not derive a second map"
    )


class _FakeFile:
    def __init__(self, src_path, dest_path, abs_src_path=None):
        self.src_path = src_path
        self.dest_path = dest_path
        # mkdocs' File exposes the on-disk source; the subpage index reads each
        # sibling's own H1 and summary out of it.
        self.abs_src_path = abs_src_path


class _FakePage:
    """The subset of mkdocs' Page the marker Preprocessor and its tests touch."""

    def __init__(self, src_path, dest_path):
        self.file = _FakeFile(src_path, dest_path)
        self.meta = {}
        self.toc = []


def _generated_page(package_name, class_name):
    src = f"pages/api/generated/{package_name}.models.{class_name}.md"
    return _FakePage(src, src.replace(".md", "/index.html"))


def _write_models_module(project_dir, package_name):
    """A module with sibling classes for See Also entries to point at."""
    (project_dir / "src" / package_name / "models.py").write_text(
        '"""Models."""\n\n\nclass Alpha:\n    """Alpha."""\n\n\nclass Beta:\n    """Beta."""\n\n\nclass Gamma:\n    """Gamma."""\n',
        encoding="utf-8",
    )


def _write_glossary(project_dir, extra=""):
    """A glossary page in the shape the linker reads: def-list terms with anchors.

    This writes into ``copie_session_minimal``, a session-scoped project shared
    across tests, so it must leave the file satisfying the same "no trailing
    blank line" invariant the rendered template obeys -- otherwise
    ``test_no_rendered_file_ends_in_a_blank_line`` fails whenever it happens to
    run after this on the same xdist worker. The final ``rstrip`` guarantees
    exactly one trailing newline whether or not ``extra`` is passed.
    """
    page = project_dir / "docs" / "pages" / "explanation" / "glossary.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    body = (
        "# Glossary\n\n"
        "## Core\n\n"
        "Memory buffer { #memory-buffer .autolink }\n"
        ":   The store of recent rows.\n\n"
        "Forecasting horizon { #forecasting-horizon .autolink }\n"
        ":   How far ahead to predict.\n\n"
        # Defined but NOT opted in: a short common word that would over-link.
        "Step { #step }\n"
        ":   One timestep.\n\n" + extra
    )
    page.write_text(body.rstrip("\n") + "\n", encoding="utf-8")
    return page


def _glossary_page(src="pages/explanation/concepts.md"):
    return _FakePage(src, src.replace(".md", "/index.html"))


def test_glossary_terms_link_on_other_pages(copie_session_minimal):
    """A term marked .autolink links to the glossary, once, from prose only.

    The glossary page is the single source of truth: a second list of terms in
    the build tooling would drift from the definitions it points at.
    """
    project_dir = copie_session_minimal.project_dir
    _write_glossary(project_dir)
    glossary = _load_glossary(project_dir, "glossary_link")

    md = "The memory buffer holds rows. A second memory buffer mention.\n\nThe forecasting horizon matters."
    out = "\n".join(glossary._linkify(md.split("\n"), _glossary_page()))

    assert "[memory buffer](glossary.md#memory-buffer)" in out, "term was not linked"
    assert "[forecasting horizon](glossary.md#forecasting-horizon)" in out
    # First occurrence only -- linking every mention is noise, not navigation.
    assert out.count("glossary.md#memory-buffer") == 1, "linked more than the first occurrence"


def test_glossary_skips_terms_not_opted_in(copie_session_minimal):
    """A defined term without .autolink is never linked.

    Defining a word and advertising it everywhere are separate decisions. A
    glossary legitimately defines short common words ("step"), and linking those
    wherever prose happens to use them produces noise.
    """
    project_dir = copie_session_minimal.project_dir
    _write_glossary(project_dir)
    glossary = _load_glossary(project_dir, "glossary_optin")

    out = "\n".join(glossary._linkify(["Each step is a step."], _glossary_page()))

    assert "#step" not in out, "a term that did not opt in was linked"
    assert "Each step is a step." in out, "text was altered"


def test_glossary_never_links_inside_code_or_headings(copie_session_minimal):
    """Code is not prose, and a link inside a heading or another link is broken markup."""
    project_dir = copie_session_minimal.project_dir
    _write_glossary(project_dir)
    glossary = _load_glossary(project_dir, "glossary_skip")

    md = (
        "## The memory buffer heading\n"
        "\n"
        "An inline `memory buffer` code span.\n"
        "\n"
        "See [the memory buffer docs](x).\n"
        "\n"
        "A real memory buffer in prose.\n"
    )
    out = "\n".join(glossary._linkify(md.split("\n"), _glossary_page()))

    assert "## The memory buffer heading" in out, "linked inside a heading"
    assert "`memory buffer`" in out, "linked inside an inline code span"
    assert "[the memory buffer docs](x)" in out, "nested a link inside an existing link"
    assert "[memory buffer](glossary.md#memory-buffer)" in out, "prose occurrence was not linked"


def test_glossary_never_links_inside_an_autodoc_directive(copie_session_minimal):
    """A `:::` mkdocstrings directive is a machine identifier, never prose.

    The glossary linker runs as a Preprocessor, *before* mkdocstrings collects the
    `:::` autodoc blocks on the generated API pages. A project whose module name
    matches an .autolink term -- e.g. a `stationarity` module and a `Stationarity`
    term -- would see `::: pkg.stationarity.ASinhTransformer` rewritten into
    `::: pkg.[stationarity](...).ASinhTransformer`, which mkdocstrings cannot
    collect, failing the strict build. yohou (the only repo with both a matching
    module and term) hit exactly this; the directive line must pass through
    untouched, and because it is skipped rather than linked, the first-occurrence
    link correctly falls on the following prose instead.
    """
    project_dir = copie_session_minimal.project_dir
    # A term whose slug collides with a module path segment in the `:::` below.
    _write_glossary(
        project_dir,
        extra="Stationarity { #stationarity .autolink }\n:   A stable statistical regime.\n",
    )
    glossary = _load_glossary(project_dir, "glossary_autodoc")

    md = (
        "::: pkg.stationarity.ASinhTransformer\n"
        "    options:\n"
        "      show_root_heading: true\n"
        "\n"
        "Stationarity is a real concept mentioned in this prose.\n"
    )
    lines = glossary._linkify(md.split("\n"), _glossary_page())
    out = "\n".join(lines)

    assert lines[0] == "::: pkg.stationarity.ASinhTransformer", (
        f"the autodoc directive was corrupted -- mkdocstrings cannot collect it: {lines[0]!r}"
    )
    # The fix is scoped to the directive: prose still links, and the skipped
    # directive means first-occurrence lands here rather than being consumed above.
    assert "[Stationarity](glossary.md#stationarity)" in out, "prose occurrence was not linked"


def test_glossary_page_does_not_link_itself(copie_session_minimal):
    """The glossary must not turn its own definitions into links to themselves."""
    project_dir = copie_session_minimal.project_dir
    _write_glossary(project_dir)
    glossary = _load_glossary(project_dir, "glossary_self")

    page = _glossary_page("pages/explanation/glossary.md")
    out = "\n".join(glossary._linkify(["A memory buffer is defined here."], page))

    assert out == "A memory buffer is defined here.", "the glossary linked its own terms"


def test_glossary_absent_is_not_an_error(copie_session_minimal):
    """Most projects ship no glossary; the feature must simply do nothing."""
    project_dir = copie_session_minimal.project_dir
    glossary_file = project_dir / "docs" / "pages" / "explanation" / "glossary.md"
    if glossary_file.exists():
        glossary_file.unlink()
    glossary = _load_glossary(project_dir, "glossary_absent")

    lines = ["A memory buffer here."]
    assert glossary._linkify(lines, _glossary_page()) == lines


def test_glossary_skips_fenced_code_blocks(copie_session_minimal):
    """A term inside a fenced code block is code, not prose, and is not linked.

    The first prototype skipped fences and this pins it: a fenced example that
    happens to name a glossary term is exactly where an accidental link is worst,
    and the term must still link in the prose that follows the fence.
    """
    project_dir = copie_session_minimal.project_dir
    _write_glossary(project_dir)
    glossary = _load_glossary(project_dir, "glossary_fence")

    md = "```python\nmemory buffer = 1\n```\n\nThen a real memory buffer in prose.\n"
    out = "\n".join(glossary._linkify(md.split("\n"), _glossary_page()))

    assert "```python\nmemory buffer = 1\n```" in out, "linked a term inside a fenced code block"
    assert "[memory buffer](glossary.md#memory-buffer)" in out, "the prose occurrence after the fence was not linked"
    assert out.count("glossary.md#memory-buffer") == 1, "linked something other than the single prose occurrence"


def test_glossary_state_does_not_leak_between_pages(copie_session_minimal):
    """First-occurrence state is per page: a term linked on A still links on B.

    The `linked` set is page-global but only within a page. Sharing it across
    pages would link a term once for the whole site, leaving every later page's
    first mention bare -- the failure a Postprocessor could not avoid and the
    reason this is a Preprocessor.
    """
    project_dir = copie_session_minimal.project_dir
    _write_glossary(project_dir)
    glossary = _load_glossary(project_dir, "glossary_leak")

    first = "\n".join(glossary._linkify(["The memory buffer on page one."], _glossary_page("pages/explanation/a.md")))
    second = "\n".join(glossary._linkify(["The memory buffer on page two."], _glossary_page("pages/explanation/b.md")))

    assert "glossary.md#memory-buffer" in first, "the term did not link on the first page"
    assert "glossary.md#memory-buffer" in second, "state leaked across pages: the term stopped linking on a later page"


def _write_notebook(project_dir, stem, gallery_body, imports=""):
    nb = project_dir / "examples" / f"{stem}.py"
    nb.parent.mkdir(parents=True, exist_ok=True)
    nb.write_text(f"import marimo\n\n{imports}\n__gallery__ = {{{gallery_body}}}\n", encoding="utf-8")
    return nb


def test_notebook_export_is_cached_by_source_hash(copie_session_default):
    """An unchanged notebook is not re-exported; an edited one is.

    Exporting means executing the notebook, which dominates the docs build, so
    this is the difference between a fast rebuild and a slow one under
    `mkdocs serve`.
    """
    project_dir = copie_session_default.project_dir
    build = _load_build(project_dir, "nbcache")

    notebook = project_dir / "examples" / "cache_probe.py"
    notebook.parent.mkdir(parents=True, exist_ok=True)
    notebook.write_text("x = 1\n", encoding="utf-8")
    output_dir = project_dir / "docs" / "examples" / "cache_probe"
    output_dir.mkdir(parents=True, exist_ok=True)

    digest = build._notebooks._notebook_content_hash(notebook)

    # Nothing exported yet.
    assert not build._notebooks._is_cached(output_dir, digest), "claimed a cache hit with no exported page"

    # A hash with no rendered page must not count: the export may have died
    # before writing the html, and reusing that ships a missing page.
    (output_dir / build._notebooks._SOURCE_HASH_FILE).write_text(digest, encoding="utf-8")
    assert not build._notebooks._is_cached(output_dir, digest), "claimed a cache hit with no index.html"

    (output_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    assert build._notebooks._is_cached(output_dir, digest), "did not reuse an unchanged export"

    # Editing the notebook must invalidate it, or the site serves a stale render.
    notebook.write_text("x = 2\n", encoding="utf-8")
    assert not build._notebooks._is_cached(output_dir, build._notebooks._notebook_content_hash(notebook)), (
        "reused the export of an edited notebook"
    )


def test_notebook_cache_is_absent_without_examples(copie_session_minimal):
    """The caching code ships only where notebooks do.

    The notebook-content hashing lives in `_notebooks.py`, which a no-examples
    project does not ship at all -- so no build module carries it. Scanning every
    build script (not just one file) keeps this honest against wherever the code
    might reappear.
    """
    build = copie_session_minimal.project_dir / BUILD_DIR
    sources = "\n".join(p.read_text(encoding="utf-8") for p in sorted(build.glob("*.py")))
    assert "_notebook_content_hash" not in sources, "notebook caching leaked into a no-examples project"
    assert "import hashlib" not in sources, "hashlib imported with nothing to hash"


def _reset_gallery_caches(markers):
    # markers.reset_caches() nulls every gallery cache and resets _api_pages, so
    # this is the whole reset -- no need to null each cache by name here.
    markers.reset_caches()


def test_declared_api_references_override_imports(copie_session_default):
    """A declared api_references list wins over what the notebook imports."""
    project_dir = copie_session_default.project_dir
    _write_models_module(project_dir, "test_project")
    _write_notebook(
        project_dir,
        "declared_nb",
        '"title": "Declared", "description": "d", "category": "tutorial", "api_references": ["Beta"]',
        imports="from test_project.models import Alpha, Gamma\n",
    )
    markers = _load_markers(project_dir, "egl_declared")
    _reset_gallery_caches(markers)

    usage = markers._get_notebook_api_usage(project_dir)
    stems = {q: {i["stem"] for i in items} for q, items in usage.items()}

    assert "declared_nb" in stems.get("test_project.models.Beta", set()), "declared reference not used"
    assert "declared_nb" not in stems.get("test_project.models.Alpha", set()), "import won over declaration"
    assert "declared_nb" not in stems.get("test_project.models.Gamma", set()), "import won over declaration"


def test_absent_api_references_falls_back_to_imports(copie_session_default):
    """A notebook declaring nothing still gets cross-referenced.

    This is the day-one path: a fresh project has no metadata, and the feature
    must be visible before anyone opts in.
    """
    project_dir = copie_session_default.project_dir
    _write_models_module(project_dir, "test_project")
    _write_notebook(
        project_dir,
        "fallback_nb",
        '"title": "Fallback", "description": "d", "category": "tutorial"',
        imports="from test_project.models import Alpha\n",
    )
    markers = _load_markers(project_dir, "egl_fallback")
    _reset_gallery_caches(markers)

    usage = markers._get_notebook_api_usage(project_dir)
    stems = {i["stem"] for i in usage.get("test_project.models.Alpha", [])}

    assert "fallback_nb" in stems, "notebook without api_references was not inferred from imports"


def test_empty_api_references_means_no_pages(copie_session_default):
    """An empty list is a statement ('nowhere'), not an omission ('infer')."""
    project_dir = copie_session_default.project_dir
    _write_models_module(project_dir, "test_project")
    _write_notebook(
        project_dir,
        "optout_nb",
        '"title": "Optout", "description": "d", "category": "tutorial", "api_references": []',
        imports="from test_project.models import Alpha\n",
    )
    markers = _load_markers(project_dir, "egl_empty")
    _reset_gallery_caches(markers)

    usage = markers._get_notebook_api_usage(project_dir)
    appearances = {q for q, items in usage.items() if any(i["stem"] == "optout_nb" for i in items)}

    assert not appearances, f"api_references: [] still produced cards on {appearances}"


def test_unresolvable_api_reference_is_ignored(copie_session_default):
    """A declared name that resolves to nothing is dropped, not fatal."""
    project_dir = copie_session_default.project_dir
    _write_models_module(project_dir, "test_project")
    _write_notebook(
        project_dir,
        "bogus_nb",
        '"title": "Bogus", "description": "d", "category": "tutorial", "api_references": ["NotAThing", "Beta"]',
    )
    markers = _load_markers(project_dir, "egl_bogus")
    _reset_gallery_caches(markers)

    usage = markers._get_notebook_api_usage(project_dir)

    assert not [q for q in usage if "NotAThing" in q], "unresolvable name produced an entry"
    assert any(i["stem"] == "bogus_nb" for i in usage.get("test_project.models.Beta", [])), "valid name was dropped too"


def test_api_example_cards_are_capped(copie_session_default):
    """The card list is bounded, with the remainder reachable via the gallery."""
    project_dir = copie_session_default.project_dir
    # A symbol only this test references: the session project is shared, so
    # reusing one would let another test's notebooks into the card list.
    (project_dir / "src" / "test_project" / "capped.py").write_text(
        '"""Capped."""\n\n\nclass Capstone:\n    """Capstone."""\n', encoding="utf-8"
    )
    notebook_count = 9
    for i in range(notebook_count):
        _write_notebook(
            project_dir,
            f"capped_{i:02d}",
            f'"title": "Capped {i:02d}", "description": "d", "category": "tutorial", "api_references": ["Capstone"]',
        )
    markers = _load_markers(project_dir, "egl_cap")
    _reset_gallery_caches(markers)

    html = markers._build_api_examples_html(project_dir, "test_project.capped.Capstone")

    assert notebook_count > markers._API_EXAMPLES_CAP, "test does not actually exceed the cap"
    assert html.count("**Capped") == markers._API_EXAMPLES_CAP, "card list was not capped"
    assert "See all" in html and "in the gallery" in html, "no overflow link past the cap"
    # Stable order: same input, same cards, so builds are reproducible. The
    # caches must be cleared between calls -- re-reading a warm cache returns
    # the same object and the assertion cannot fail.
    _reset_gallery_caches(markers)
    assert markers._build_api_examples_html(project_dir, "test_project.capped.Capstone") == html


def test_api_example_cards_under_cap_have_no_gallery_link(copie_session_default):
    """Below the cap, nothing is hidden, so no overflow link is shown."""
    project_dir = copie_session_default.project_dir
    _write_models_module(project_dir, "test_project")
    _write_notebook(
        project_dir,
        "solo_nb",
        '"title": "Solo", "description": "d", "category": "tutorial", "api_references": ["Gamma"]',
    )
    markers = _load_markers(project_dir, "egl_undercap")
    _reset_gallery_caches(markers)

    html = markers._build_api_examples_html(project_dir, "test_project.models.Gamma")

    assert "**Solo**" in html
    assert "See all" not in html, "overflow link shown when nothing was hidden"


def test_companion_path_variants_match_same_page(copie_session_default):
    """companion is hand-written, so authored spellings must all match."""
    markers = _load_markers(copie_session_default.project_dir, "egl_norm")
    variants = [
        "/pages/how-to/x/",
        "pages/how-to/x",
        "pages/how-to/x.md",
        "/pages/how-to/x",
    ]
    normalized = {markers._normalize_companion_path(v) for v in variants}
    assert len(normalized) == 1, f"companion path variants did not normalize together: {normalized}"


def test_companion_placeholder_renders_nothing_when_unmatched(copie_session_default):
    """A page with the placeholder and no companion notebooks renders empty."""
    project_dir = copie_session_default.project_dir
    markers = _load_markers(project_dir, "egl_nocompanion")
    _reset_gallery_caches(markers)

    html = markers._build_companion_cards_html(project_dir, "pages/how-to/nobody-references-me.md")

    assert html == "", "unmatched placeholder produced output"


def test_companion_cache_is_registered_by_name(copie_session_default):
    """The companion cache must carry the _CACHE suffix.

    The per-build reset's registration test discovers caches by that suffix, so
    a cache named otherwise (the natural `_COMPANION_INDEX`) is invisible to it
    and the stale-read bug returns silently.
    """
    markers_source = (copie_session_default.project_dir / BUILD_DIR / "_markers.py").read_text(encoding="utf-8")
    assert "_COMPANION_INDEX_CACHE" in markers_source, "companion cache does not follow the *_CACHE convention"


def test_gallery_features_absent_without_examples(copie_session_minimal):
    """The whole feature is gated behind include_examples."""
    markers_source = (copie_session_minimal.project_dir / BUILD_DIR / "_markers.py").read_text(encoding="utf-8")
    for symbol in ("_COMPANION_INDEX_CACHE", "_API_EXAMPLES_CAP", "_build_companion_cards_html"):
        assert symbol not in markers_source, f"{symbol} leaked into a project generated without examples"


def _mkdocs_config(project_dir):
    import yaml

    class _Loader(yaml.SafeLoader):
        pass

    _Loader.add_multi_constructor("tag:yaml.org,2002:python/name:", lambda loader, suffix, node: suffix)
    _Loader.add_constructor("!ENV", lambda loader, node: None)
    return yaml.load((project_dir / "mkdocs.yml").read_text(encoding="utf-8"), Loader=_Loader)


def test_snippets_resolve_docs_and_repo_root(copie_session_default):
    """base_path must reach the repo root as well as docs/.

    Narrowing this to [docs] breaks any project that includes a file from the
    repo root or src/ -- which real projects do.
    """
    config = _mkdocs_config(copie_session_default.project_dir)
    snippets = next(x["pymdownx.snippets"] for x in config["markdown_extensions"] if "pymdownx.snippets" in str(x))

    assert snippets["base_path"] == ["docs", "."], "base_path must search docs first, then the repo root"
    assert snippets["check_paths"] is True, "a missing include must fail the build, not vanish"


@pytest.mark.parametrize("include_examples", [True, False])
def test_docs_markers_and_glossary_extensions_are_registered(copie, include_examples):
    """The marker and glossary Preprocessors must appear in `markdown_extensions`.

    They resolve the `<!-- API_TABLE -->` / `<!-- SUBPAGES -->` / gallery markers
    and the glossary links. Loaded by module name at config time; if the
    registration line is dropped, the extension never loads and every marker ships
    as a blank HTML comment -- the fleet's dominant bug shape, invisible to a green
    `--strict` build. Both variants, because the extensions are examples-independent
    and must load in either -- including the no-examples one that has no gallery.
    """
    result = copie.copy(extra_answers={"include_examples": include_examples})
    names = [e for e in _mkdocs_config(result.project_dir)["markdown_extensions"] if isinstance(e, str)]

    assert "docs_build._markers" in names, (
        "the marker Preprocessor is not registered; markers would ship as blank space"
    )
    assert "docs_build._glossary" in names, "the glossary Preprocessor is not registered; glossary links would vanish"


def test_markers_strip_examples_placeholder_without_examples(copie_session_minimal):
    """In a no-examples project, an `<!-- EXAMPLES_FOR -->` marker is stripped, not shipped.

    GALLERY / EXAMPLES_FOR / COMPANION are gated out of the no-examples
    `_markers.py`; its else-branch removes any stray `EXAMPLES_FOR` so it does not
    reach the page as blank space. This is the variant that once hid a gated
    import behind an ungated caller, so the gated `_inject` path gets its own test.
    """
    project_dir = copie_session_minimal.project_dir
    markers = _load_markers(project_dir, "min_examples_for")

    page = _FakePage("pages/reference/api.md", "pages/reference/api/index.html")
    out = markers._inject("# API\n\n<!-- EXAMPLES_FOR:foo.Bar -->\n", page, config={})

    assert "EXAMPLES_FOR" not in out, "the examples marker was not stripped in a no-examples project"
    assert "foo.Bar" not in out, "the stripped marker left its argument behind"
    assert "# API" in out, "unrelated content was altered"


def test_changelog_include_resolves(copie_session_default):
    """The changelog page must actually render the changelog.

    A green build is not evidence here: without check_paths the include is
    dropped silently and the page renders as a heading with nothing under it.
    """
    import markdown

    project_dir = copie_session_default.project_dir
    page = project_dir / "docs" / "pages" / "reference" / "changelog.md"
    assert page.is_file(), "changelog page not generated"

    md = markdown.Markdown(
        extensions=["pymdownx.snippets"],
        extension_configs={"pymdownx.snippets": {"base_path": ["docs", "."], "check_paths": True}},
    )
    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        rendered = md.convert(page.read_text(encoding="utf-8"))
    finally:
        os.chdir(cwd)

    # Assert on text only the root CHANGELOG.md supplies. "Changelog" alone is a
    # word a page with no include at all would provide for free, so it cannot
    # fail for the defect this guards.
    assert "Keep a Changelog" in rendered, "root CHANGELOG.md content did not render -- the include resolved to nothing"
    assert "Semantic Versioning" in rendered, "changelog body missing"
    assert rendered.count("<h1") == 1, "changelog page renders a duplicate <h1> (own heading plus the include's)"


def test_python_inventory_configured(copie_session_default):
    """Signatures reference stdlib types, so that inventory earns its place."""
    config = _mkdocs_config(copie_session_default.project_dir)
    handler = next(p["mkdocstrings"] for p in config["plugins"] if isinstance(p, dict) and "mkdocstrings" in p)
    inventories = handler["handlers"]["python"]["inventories"]

    assert any("docs.python.org" in str(i) for i in inventories), "Python inventory not configured"


def test_quadrant_index_pages_exist_and_lead_nav(copie_session_default):
    """navigation.indexes is on, so each quadrant needs a landing page first."""
    project_dir = copie_session_default.project_dir
    config = _mkdocs_config(project_dir)

    for quadrant in ("tutorials", "how-to", "reference", "explanation"):
        assert (project_dir / "docs" / "pages" / quadrant / "index.md").is_file(), f"{quadrant}/index.md missing"

    sections = {k: v for entry in config["nav"] if isinstance(entry, dict) for k, v in entry.items()}
    for label, quadrant in (
        ("Tutorials", "tutorials"),
        ("How-to Guides", "how-to"),
        ("Reference", "reference"),
        ("Explanation", "explanation"),
    ):
        assert sections[label][0] == f"pages/{quadrant}/index.md", f"{label} nav must start with its index page"


def test_quadrant_indexes_are_local_owned(copie_session_default):
    """The template's skeleton must never overwrite a project's own landing page.

    Four of the seven repos generated from this template already maintain
    hand-written index pages; an update that replaces them is a regression
    shipped as an upgrade.
    """
    classification = (
        copie_session_default.project_dir
        / ".github"
        / "skills"
        / "update-from-template"
        / "references"
        / "file-classification.md"
    )
    if not classification.is_file():
        pytest.skip("update-from-template skill not shipped to generated projects")
    text = classification.read_text(encoding="utf-8")
    # Slice to the section end, not EOF: running to EOF would let a path
    # listed in a LATER section satisfy this assertion.
    start = text.index("## Tier 3")
    nxt = text.find("\n## ", start + 1)
    tier3 = text[start : nxt if nxt > 0 else len(text)]

    for quadrant in ("tutorials", "how-to", "reference", "explanation"):
        assert f"docs/pages/{quadrant}/index.md" in tier3, f"{quadrant}/index.md not listed as local-owned"


def _is_ignored(project_dir, path):
    """Whether git would ignore `path`, judged by the generated .gitignore itself."""
    result = subprocess.run(
        ["git", "check-ignore", "-q", path],
        cwd=project_dir,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def _git_init(project_dir):
    """A throwaway repo, so `git check-ignore` has a worktree to answer against."""
    subprocess.run(["git", "init", "-q"], cwd=project_dir, capture_output=True, check=True)


def test_only_the_claude_skills_copy_is_tracked(copie):
    """.claude/skills is the tracked source of truth; the Copilot mirror is not.

    The two copies are byte-identical by design, so tracking both doubles every
    skill edit and its review. Judged with `git check-ignore` against the
    generated .gitignore rather than by reading it: the rule that matters is the
    one git actually applies, and this file's negation (`.claude/*` then
    `!.claude/skills/`) is exactly the kind that looks right and silently is not.
    """
    project_dir = copie.copy().project_dir
    _git_init(project_dir)

    assert not _is_ignored(project_dir, ".claude/skills/update-from-template/SKILL.md"), (
        ".claude/skills must be tracked -- it is the source of truth for the skills"
    )
    assert _is_ignored(project_dir, ".github/skills/update-from-template/SKILL.md"), (
        ".github/skills is a byte-identical mirror of .claude/skills and must not be tracked"
    )


def test_openspec_skills_are_never_tracked(copie):
    """openspec rewrites its own skills; they are tool state, not project content.

    The `!.claude/skills/` negation would otherwise pull them in, so this needs
    its own rule -- and needs testing, because the interaction between a
    negation and a later ignore is where this silently goes wrong.
    """
    project_dir = copie.copy().project_dir
    _git_init(project_dir)

    assert _is_ignored(project_dir, ".claude/skills/openspec-propose/SKILL.md"), (
        "an openspec skill under .claude/skills must stay untracked"
    )
    assert _is_ignored(project_dir, ".github/skills/openspec-review/SKILL.md"), (
        "an openspec skill under .github/skills must stay untracked"
    )
    # The rule must not swallow the skills the template does ship.
    assert not _is_ignored(project_dir, ".claude/skills/diataxis-howto-writer/SKILL.md"), (
        "the openspec rule is too broad -- it is hiding a template-shipped skill"
    )


def test_contribute_guide_carries_no_other_projects_domain(copie_session_default):
    """The notebook examples must not name another project's API.

    Every generated project gets this page. Examples written around one
    package's domain read as nonsense in the rest of the fleet -- a kedro plugin
    told to document `OptunaSearchCV` -- and quietly invite copying the wrong
    thing.
    """
    contribute = (copie_session_default.project_dir / "docs" / "pages" / "how-to" / "contribute.md").read_text(
        encoding="utf-8"
    )
    for foreign in ("OptunaSearchCV", "Optuna", "Hyperparameter Search", "sklearn_optuna"):
        assert foreign not in contribute, f"the contribute guide hardcodes another project's domain: {foreign!r}"


def test_project_branding_survives_a_second_template_run(tmp_path):
    """A project's own logo is not overwritten by a later template run.

    The behavioural half of the guarantee that
    test_branding_is_documented_as_local_owned only documents. That test asserts
    a skill reference lists these files under Tier 3 and passed from v0.19.1
    onward -- while copier went on silently overwriting real projects' logos,
    because Tier 3 is a convention for whoever resolves an update and copier
    never reaches a resolution step for a binary. It cannot merge one, so it
    overwrites: no conflict, no .rej, no output, just the project's wordmark
    replaced by the template's under the project's own name. Only
    `_skip_if_exists` stops it, so only re-running the template can prove it.
    """
    from copier import run_copy

    answers = {
        "project_name": "Brand",
        "project_slug": "brand",
        "package_name": "brand",
        "description": "d",
        "author_name": "A",
        "author_email": "a@b.c",
        "github_username": "u",
        "version": "0.1.0",
        "min_python_version": "3.11",
        "max_python_version": "3.14",
        "license": "MIT",
        "include_actions": True,
        "include_examples": True,
    }
    template_dir = str(Path(__file__).parent.parent)
    project = tmp_path / "brand-project"
    run_copy(template_dir, str(project), data=answers, defaults=True, overwrite=True, unsafe=True, vcs_ref="HEAD")

    assets = project / "docs" / "assets"
    own = {
        "logo.png": b"THIS-PROJECT-OWN-LOGO",
        "logo_dark.png": b"THIS-PROJECT-OWN-LOGO-DARK",
        "logo_light.png": b"THIS-PROJECT-OWN-LOGO-LIGHT",
        "favicon.png": b"THIS-PROJECT-OWN-FAVICON",
    }
    for name, content in own.items():
        assert assets.joinpath(name).is_file(), f"the template must seed {name} so a new project renders something"
        assets.joinpath(name).write_bytes(content)

    run_copy(template_dir, str(project), data=answers, defaults=True, overwrite=True, unsafe=True, vcs_ref="HEAD")

    for name, content in own.items():
        assert assets.joinpath(name).read_bytes() == content, (
            f"the template overwrote the project's {name}; its branding is silently gone"
        )

    # The org mark is the template's own and stays template-managed -- skipping
    # it would strand every project on the mark it was generated with.
    assert (assets / "made_by_stateful-y.png").is_file()


def test_branding_is_documented_as_local_owned(copie_session_default):
    """The update skill classifies branding as Tier 3, so a human resolver keeps it.

    Documentation only. The behaviour is pinned by
    test_project_branding_survives_a_second_template_run -- this test passed
    throughout the period when updates were still eating logos.
    """
    classification = (
        copie_session_default.project_dir
        / ".github"
        / "skills"
        / "update-from-template"
        / "references"
        / "file-classification.md"
    )
    if not classification.is_file():
        pytest.skip("update-from-template skill not shipped to generated projects")
    text = classification.read_text(encoding="utf-8")
    t3_start = text.index("## Tier 3")
    t3_end = text.find("\n## ", t3_start + 1)
    tier3 = text[t3_start : t3_end if t3_end > 0 else len(text)]
    t1_start = text.index("## Tier 1")
    t1_end = text.find("\n## ", t1_start + 1)
    tier1 = text[t1_start:t1_end]

    for asset in ("favicon.png", "logo.png", "logo_dark.png", "logo_light.png"):
        assert f"docs/assets/{asset}" in tier3, f"{asset} is not local-owned; a template update would overwrite it"
        assert f"docs/assets/{asset}" not in tier1, f"{asset} is still Tier 1 (template-managed)"
    # The template's own mark is genuinely template-managed.
    assert "docs/assets/made_by_stateful-y.png" in tier1, "the made-by mark should stay template-managed"


def _cache_modules(markers_module):
    """The markers module and every build step it loads.

    The build steps are reached through the markers module rather than imported
    directly, so these are the instances bound to *this* generated project.
    """
    modules = [markers_module]
    modules += [m for m in (getattr(markers_module, n, None) for n in _BUILD_STEP_MODULES) if m is not None]
    return modules


def _cache_names(markers_module):
    """Every ``*_CACHE`` global across every module the markers load, as (module, name).

    Scanning only ``_markers`` was correct until the build steps were split out.
    Two of the caches now live in ``_api_pages``, and a scan of ``_markers`` alone
    would keep passing while quietly covering less -- the guarantee is "every
    ``*_CACHE`` global is cleared", not "every one that stayed behind".
    """
    return [
        (module, name)
        for module in _cache_modules(markers_module)
        for name in vars(module)
        if name.endswith("_CACHE") and not name.startswith("__")
    ]


@pytest.mark.parametrize(
    ("fixture_name", "expects_gallery"),
    [("copie_session_default", True), ("copie_session_minimal", False)],
)
def test_on_config_resets_every_cache(request, fixture_name, expects_gallery):
    """Sentinel round-trip: populate every cache, reset, assert all cleared.

    Deliberately not a presence check on the source. Asserting that the cache
    names appear in reset_caches's body passes even against an empty function, so
    it would verify nothing. Each variant is loaded under a unique module name:
    importing both under one name makes sys.modules return the first, and the
    second variant is never actually exercised.
    """
    project_dir = request.getfixturevalue(fixture_name).project_dir
    markers = _load_markers(project_dir, f"reset_{fixture_name}")

    found = _cache_names(markers)
    assert found, "no *_CACHE globals discovered"
    flat = {name for _, name in found}
    assert ("_GALLERY_CACHE" in flat) is expects_gallery, (
        f"gallery cache presence should follow include_examples; found {sorted(flat)}"
    )
    # The discovery caches moved to _api_pages with the functions that own them.
    # Naming them explicitly is what stops this test from silently narrowing to
    # "whatever stayed in _markers.py" if the scan is ever reduced to one module.
    assert {"_SURFACE_CACHE", "_API_NAME_LOOKUP_CACHE"} <= flat, (
        f"the API discovery caches are not being scanned; found {sorted(flat)}"
    )

    sentinel = object()
    for module, name in found:
        setattr(module, name, sentinel)

    markers.reset_caches()

    still_set = [f"{module.__name__}.{name}" for module, name in found if getattr(module, name) is sentinel]
    assert not still_set, f"reset_caches did not clear: {still_set}"


def test_reset_caches_returns_none(copie_session_default):
    """The reset is a plain procedure now, not a hook: it clears caches, returns None.

    ``on_config`` returned the config to satisfy the mkdocs hook contract;
    ``reset_caches`` has no config to hand back and no hook contract to meet, so
    it simply returns None.
    """
    markers = _load_markers(copie_session_default.project_dir, "reset_returns")
    assert markers.reset_caches() is None


def test_reset_is_a_function_not_a_fire_once_hook(copie_session_default):
    """The cache reset must be re-runnable per build, not a fire-once startup hook.

    ``on_startup`` ran once per ``mkdocs`` invocation, so a reset there never fired
    again on a rebuild -- the bug this change exists to fix. The reset is now an
    explicit ``reset_caches()`` the build steps and serve.py call on every rebuild;
    there is no on_config/on_startup hook left to regress into.
    """
    source = (copie_session_default.project_dir / BUILD_DIR / "_markers.py").read_text(encoding="utf-8")
    assert "def reset_caches(" in source, "no per-build reset"
    assert "def on_startup(" not in source, "on_startup fires once per invocation, not per build"
    assert "def on_config(" not in source, "the mkdocs hooks are gone; the reset is a plain function"


def _module_imports(path):
    """Top-level module names imported by a Python file, via AST."""
    import ast as _ast

    tree = _ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, _ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


@pytest.mark.parametrize(
    ("fixture_name", "expects_notebooks"),
    [("copie_session_default", True), ("copie_session_minimal", False)],
)
def test_build_steps_import_no_mkdocs(request, fixture_name, expects_notebooks):
    """The extracted build steps must not depend on the site generator.

    They are already independent in fact -- ``on_pre_build`` ignored its ``config``
    argument and ``on_post_build`` used it for two directory strings. Stating it as
    an enforced rule is what stops the next edit from re-coupling them, and it is
    the property that makes them runnable and testable without a docs build.

    Checked on the import graph rather than by grepping for the word: two
    docstrings legitimately describe mkdocs-material HTML as their input format,
    and a substring guard fails on both.
    """
    build = request.getfixturevalue(fixture_name).project_dir / BUILD_DIR
    steps = ["_api_pages.py", "_markdown_export.py"] + (["_notebooks.py"] if expects_notebooks else [])
    for step in steps:
        path = build / step
        assert path.is_file(), f"{step} was not generated"
        assert "mkdocs" not in _module_imports(path), f"{step} imports mkdocs"


def test_notebooks_module_absent_without_examples(copie_session_minimal):
    """A project without examples gets no notebook export module, and no dangling call."""
    build = copie_session_minimal.project_dir / BUILD_DIR
    assert not (build / "_notebooks.py").exists(), "the notebook export module shipped without examples"
    build_source = (build / "build.py").read_text(encoding="utf-8")
    assert "_notebooks" not in build_source, "build.py references a module this project does not have"


def test_hooks_delegate_rather_than_implement(copie_session_default):
    """The build steps stay adapters; the work stays in the modules that own it.

    ``build.py`` must survive -- ``mkdocs.yml`` watches ``src`` so that adding a
    class appears without restarting ``mkdocs serve``, and that only works because
    ``prebuild`` regenerates on every rebuild. What must not come back is the
    logic: this fails if generation, export or conversion creeps into build.py.
    """
    source = (copie_session_default.project_dir / BUILD_DIR / "build.py").read_text(encoding="utf-8")
    assert "_api_pages.generate(" in source, "prebuild does not delegate API generation"
    assert "_notebooks.export(" in source, "prebuild does not delegate the notebook export"
    assert "_markdown_export.export(" in source, "postbuild does not delegate the markdown export"
    for moved in ("def _generate_api_pages", "def _html_to_markdown", "def _notebook_content_hash"):
        assert moved not in source, f"{moved} came back into build.py"


def test_api_pages_generate_runs_without_a_docs_build(copie_session_default, tmp_path):
    """``_api_pages.generate`` writes the API pages on its own.

    The point of the split: this needs no theme, no server and no markdown, so it
    should not cost a site build to exercise. Runs against a copy so the fixture
    project's own generated pages are not disturbed.
    """
    project = tmp_path / "proj"
    shutil.copytree(copie_session_default.project_dir, project, dirs_exist_ok=True)
    api_dir = project / "docs" / "pages" / "api"
    if api_dir.exists():
        shutil.rmtree(api_dir)

    build = _load_build(project, "steps_generate")
    build._api_pages.generate(project)

    assert (api_dir / "hello.md").is_file(), "no submodule page was generated"
    generated = {p.name for p in (api_dir / "generated").glob("*.md")}
    # Membership, not equality: the session fixture is shared, and earlier tests
    # add modules to it. Asserting an exact set makes this fail on test ordering
    # rather than on anything about the generator.
    assert {"test_project.hello.Greeter.md", "test_project.hello.hello.md"} <= generated, sorted(generated)
    body = (api_dir / "generated" / "test_project.hello.Greeter.md").read_text(encoding="utf-8")
    assert "::: test_project.hello.Greeter" in body, "the member page does not point mkdocstrings at the symbol"
    assert "template: api-page.html" in body, "the member page lost its template declaration"


def test_markdown_export_runs_against_a_prebuilt_site(copie_session_default, tmp_path):
    """``_markdown_export.export`` works on any site directory, not just its own.

    Taking the directories as arguments is what makes this reachable from a
    fixture; deriving them from ``__file__`` would tie the step to the tree it
    happens to sit in.
    """
    docs_dir = tmp_path / "docs"
    site_dir = tmp_path / "site"
    (docs_dir / "pages").mkdir(parents=True)
    site_dir.mkdir()
    (docs_dir / "index.md").write_text("# Home\n\nBody text.\n", encoding="utf-8")
    (docs_dir / "pages" / "guide.md").write_text("# Guide\n\nStep one.\n", encoding="utf-8")
    # A built page: the exporter should prefer the rendered article over the source.
    (site_dir / "pages" / "guide").mkdir(parents=True)
    (site_dir / "pages" / "guide" / "index.html").write_text(
        '<html><body><article class="md-content__inner md-typeset">'
        "<h1>Guide</h1><p>Rendered step one.</p></article></body></html>",
        encoding="utf-8",
    )

    build = _load_build(copie_session_default.project_dir, "steps_mdexport")
    build._markdown_export.export(site_dir, docs_dir)

    rendered = (site_dir / "pages" / "guide.md").read_text(encoding="utf-8")
    assert "Rendered step one." in rendered, "the built HTML was not converted"
    fallback = (site_dir / "index.md").read_text(encoding="utf-8")
    assert "Body text." in fallback, "a page with no built HTML was not copied as source"


def _toc_hrefs(html):
    """Same-page hrefs listed in the rendered table of contents.

    Parsed with nav nesting tracked, not sliced out of the raw HTML: every
    heading also carries a permalink anchor with the identical href, so a naive
    substring search finds `#greet-parameters` on any page that *has* that
    heading, whether or not the ToC lists it -- which is exactly the distinction
    this is used to assert.
    """
    from html.parser import HTMLParser

    class _Nav(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.depth = 0
            self.hrefs = set()

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if tag == "nav" and "md-nav--secondary" in (a.get("class") or ""):
                self.depth += 1
            elif tag == "nav" and self.depth:
                self.depth += 1
            if self.depth and tag == "a" and (a.get("href") or "").startswith("#"):
                self.hrefs.add(a["href"])

        def handle_endtag(self, tag):
            if tag == "nav" and self.depth:
                self.depth -= 1

    p = _Nav()
    p.feed(html)
    p.close()
    return p.hrefs


def test_hooks_do_not_touch_the_table_of_contents(copie_session_default):
    """The marker extension builds no table-of-contents entries and imports no ToC machinery.

    mkdocstrings registers every heading a template emits, so `page.toc` needs no
    help. The docs tooling used to rebuild it by hand with `AnchorLink` objects,
    purely because a regex invented those headings *after* the `toc` extension had
    run. That part was measured to have no path onto any other renderer, and it is
    gone -- what stayed (the module_toc sidebar) writes only `page.meta`.
    """
    source = (copie_session_default.project_dir / BUILD_DIR / "_markers.py").read_text(encoding="utf-8")
    assert "mkdocs.structure.toc" not in source, "the marker extension imports ToC machinery again"
    assert "AnchorLink" not in source, "the marker extension constructs ToC entries again"
    assert "page.toc" not in source, "the marker extension mutates page.toc again"


@pytest.mark.parametrize("fixture_name", ["copie_session_default", "copie_session_minimal"])
def test_mkdocstrings_template_overrides_ship(request, fixture_name):
    """The overrides ship, and are wired where mkdocstrings actually reads them.

    `custom_templates` is a PLUGIN-level key. Putting it under
    `handlers.python.options` fails the build outright with
    `PythonOptions.__init__() got an unexpected keyword argument`, so asserting
    the key exists somewhere in the file would pass on a broken config.
    """
    import yaml

    project_dir = request.getfixturevalue(fixture_name).project_dir
    templates = mkdocstrings_templates(project_dir)
    for rel in ("docstring.html.jinja", "class.html.jinja", "function.html.jinja", "docstring/admonition.html.jinja"):
        assert (templates / rel).is_file(), f"missing override: {rel}"

    raw = (project_dir / "mkdocs.yml").read_text(encoding="utf-8")
    # `!!python/name:` is registered, not banned: `pymdownx.emoji` needs a
    # callable index and YAML has no other way to name one. A bare SafeLoader
    # raises ConstructorError on it, which is a parser problem, not a config
    # problem -- every other reader of this file registers the same handler.
    _loader = type("L", (yaml.SafeLoader,), {})
    _loader.add_multi_constructor("tag:yaml.org,2002:python/name:", lambda _l, suffix, _n: suffix)
    _loader.add_constructor("!ENV", lambda _l, _n: None)
    config = yaml.load(raw, Loader=_loader)
    plugin = next(p["mkdocstrings"] for p in config["plugins"] if isinstance(p, dict) and "mkdocstrings" in p)
    assert plugin.get("custom_templates") == TEMPLATES_DIR, (
        "custom_templates must sit at plugin level, not under handlers.python.options"
    )
    assert "custom_templates" not in plugin["handlers"]["python"].get("options", {}), (
        "custom_templates under options fails the build"
    )


@pytest.mark.parametrize("fixture_name", ["copie_session_default", "copie_session_minimal"])
def test_no_rendered_file_ends_in_a_blank_line(request, fixture_name):
    """Every generated text file ends in exactly one newline.

    This is a lint rule the template imposes on generated projects and then
    broke itself, in both directions. v0.28.0 shipped four `.jinja.jinja`
    overrides whose bodies are wrapped in `{% raw %}...{% endraw %}`; with
    copier's `keep_trailing_newline` the newline after `{% endraw %}` was emitted
    on top of the body's own, so every rendered override ended in a blank line.
    v0.29.0 then shipped the opposite: `mkdocs.yml` ended with a `{#- ... -#}`
    comment whose leading dash stripped the final newline, so the rendered file
    had NO trailing newline. Both fail the generated project's
    `end-of-file-fixer`; seven repos go CI-red on the same commit either way.

    It shipped through a green suite because every check looked at the SOURCE
    file, which is correctly one newline -- the defect exists only after
    rendering. So this test asserts on the rendered tree, and asserts it for
    every text file rather than the few that happened to be wrong: the next
    instance will not be in the same place.
    """
    project_dir = request.getfixturevalue(fixture_name).project_dir
    suffixes = {".py", ".md", ".yml", ".yaml", ".toml", ".css", ".js", ".jinja", ".cfg", ".txt", ".html"}
    # Only what the template renders. A fixture that has been built or synced
    # carries `.venv/` and the built site, and third-party packages ship files ending
    # in a blank line -- 29 of them in one measurement, which would bury the four
    # that matter. Scoping this keeps a failure readable and about our own files.
    #
    # `.artifacts` covers the built site, the coverage HTML and the nox environments,
    # which now live under it rather than at the project root. That move is why this
    # entry exists: with the envdir inside the tree, a session that had already run
    # put third-party `site-packages` in this walk's path, and the test failed on
    # whichever job happened to build first.
    ignored = {".git", ".venv", ".artifacts", "site", "__pycache__", ".nox", "node_modules"}
    offenders = []
    missing_newline = []
    for path in project_dir.rglob("*"):
        if not path.is_file() or path.suffix not in suffixes:
            continue
        rel = path.relative_to(project_dir)
        if ignored & set(rel.parts):
            continue
        # Skip build-time output under docs/: the generated API pages
        # (`"\n\n".join(sections)`, legitimately blank-line-terminated) and marimo's
        # exported example apps (`docs/examples/<name>/index.html`, an HTML file with
        # no trailing newline). Both are gitignored in the generated project
        # (`docs/pages/api/`, `docs/examples/*/`), so its own `end-of-file-fixer`
        # never sees them; including them would make this test depend on whether an
        # earlier test happened to run a docs build or notebook export in the shared
        # session fixture.
        posix = rel.as_posix()
        if posix.startswith("docs/pages/api/") or posix.startswith("docs/examples/"):
            continue
        data = path.read_bytes()
        if data.endswith(b"\n\n"):
            offenders.append(rel.as_posix())
        elif data and not data.endswith(b"\n"):
            missing_newline.append(rel.as_posix())
    offenders.sort()
    missing_newline.sort()
    assert not offenders, f"rendered files ending in a blank line: {offenders}"
    assert not missing_newline, f"rendered files with no trailing newline: {missing_newline}"


@pytest.mark.parametrize("fixture_name", ["copie_session_default", "copie_session_minimal"])
def test_every_rendered_yaml_file_parses(request, fixture_name):
    """Every generated .yml/.yaml file is syntactically valid YAML.

    v0.29.0 shipped a `.readthedocs.yml` whose `build.jobs` list items began with
    a quoted scalar carrying trailing content (`- "${VENV}/bin/python" build.py
    prebuild`), which is invalid YAML. It passed the whole suite because every
    check read the `.jinja` SOURCE; nothing parsed the RENDERED file. The
    generated project's `check-yaml` hook and Read the Docs both rejected it, so
    the fan-out went CI-red and RTD-red across the fleet at once. This parses the
    rendered tree so the next malformed YAML is caught here, not downstream.
    """
    import yaml

    # mkdocs.yml legitimately uses `!!python/name:` and `!ENV`; register both so a
    # valid file is not misread as a parse failure -- the same handlers every real
    # reader of that file installs. A syntax error still raises.
    loader = type("L", (yaml.SafeLoader,), {})
    loader.add_multi_constructor("tag:yaml.org,2002:python/name:", lambda _l, suffix, _n: suffix)
    loader.add_constructor("!ENV", lambda _l, _n: None)

    project_dir = request.getfixturevalue(fixture_name).project_dir
    ignored = {".git", ".venv", "site", "__pycache__", ".nox", "node_modules"}
    errors = {}
    checked = 0
    for path in project_dir.rglob("*"):
        if not path.is_file() or path.suffix not in {".yml", ".yaml"}:
            continue
        rel = path.relative_to(project_dir)
        if ignored & set(rel.parts):
            continue
        checked += 1
        try:
            yaml.load(path.read_text(encoding="utf-8"), Loader=loader)
        except yaml.YAMLError as exc:
            errors[rel.as_posix()] = str(exc).splitlines()[0]
    # A selector that matches nothing is a silent pass; this fleet's dominant bug
    # shape. `.readthedocs.yml` and `mkdocs.yml` alone guarantee a non-zero count.
    assert checked >= 2, f"expected to parse several rendered YAML files, checked {checked}"
    assert not errors, f"rendered YAML files that do not parse: {errors}"


@pytest.mark.slow
@pytest.mark.parametrize("include_examples", [True, False])
def test_section_headings_reach_the_table_of_contents(copie, include_examples, tmp_path):
    """Docstring section headings appear in a built page's ToC.

    This is the claim the whole change rests on: that a heading emitted from a
    mkdocstrings template is registered for the table of contents automatically,
    so nothing needs to rebuild `page.toc`. Asserted from a real build rather
    than trusted -- and paired with a control, because "the sidebar contains
    #parameters" would also pass if the sidebar simply contained everything.
    """
    project_dir = copie.copy(extra_answers={"include_examples": include_examples}).project_dir
    env = dict(os.environ, UV_PROJECT_ENVIRONMENT=str(project_dir / ".venv"), MKDOCS_SKIP_NOTEBOOKS="1")
    sync = ["uv", "sync", "--no-default-groups", "--group", "docs"]
    if (project_dir / "examples").exists():
        sync += ["--group", "examples"]
    assert subprocess.run(sync, cwd=project_dir, env=env, capture_output=True, check=False).returncode == 0
    # Generate the API pages before the build. mkdocs no longer does this itself:
    # the on_pre_build hook that generated them is gone, replaced by an explicit
    # `build.py prebuild` step. MKDOCS_SKIP_NOTEBOOKS (in env) skips the slow
    # notebook export while still generating the pages this test reads.
    prebuild = subprocess.run(
        ["uv", "run", "--no-sync", "python", "docs_build/build.py", "prebuild"],
        cwd=project_dir,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert prebuild.returncode == 0, prebuild.stderr[-2000:]
    build = subprocess.run(
        ["uv", "run", "--no-sync", "mkdocs", "build", "--clean", "--strict"],
        cwd=project_dir,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert build.returncode == 0, build.stderr[-2000:]

    page = site_path(project_dir) / "pages" / "api" / "generated" / "test_project.hello.Greeter" / "index.html"
    html = page.read_text(encoding="utf-8")
    toc = _toc_hrefs(html)
    assert toc, "no table of contents was parsed -- the assertions below would be vacuous"

    # Section ids are qualified by the object's path, so two `:::` on one page do
    # not collide -- see the dispatcher override. The class's own sections carry
    # its path; a member's carry the member's.
    cls = "test_project.hello.Greeter"
    for section in ("parameters", "see-also", "source-code", "methods"):
        anchor = f"#{cls}-{section}"
        assert anchor in toc, f"{anchor} is missing from the rendered table of contents ({sorted(toc)})"
    # Control: a heading that exists on the page but is deeper than toc_depth
    # must NOT be listed. Without this the assertions above would also pass on a
    # sidebar that simply listed every heading.
    assert f'id="{cls}.greet-parameters"' in html, "the method-level anchor should still exist on the page"
    assert f"#{cls}.greet-parameters" not in toc, (
        "method-level sections must stay out of the ToC (toc_depth), or a class page's sidebar becomes a wall"
    )

    # The dispatcher emits each section's heading; the shipped section template's
    # own `<p><span class="doc-section-title">` title would duplicate it, and the
    # five section-template overrides strip it. Assert the heading is present and
    # the shipped title is gone -- for every mapped section, not just one.
    for label in ("Parameters", "Returns", "Examples"):
        assert f'<span class="doc-section-heading">{label}</span>' in html, f"{label} heading missing"
        assert f'<span class="doc-section-title">{label}:</span>' not in html, (
            f"the shipped {label} title was not stripped; the page shows it twice"
        )


def test_no_phantom_cache_without_examples(copie_session_minimal):
    """The reset must not name caches a project does not define.

    `global X; X = None` creates the binding rather than raising, so an
    ungated reset silently grows module attributes nothing reads -- and the
    discovery test would then dutifully confirm they are cleared.
    """
    markers = _load_markers(copie_session_minimal.project_dir, "reset_phantom")
    markers.reset_caches()

    for gallery_cache in ("_GALLERY_CACHE", "_COMPANION_INDEX_CACHE", "_NOTEBOOK_API_USAGE_CACHE"):
        assert not hasattr(markers, gallery_cache), f"{gallery_cache} phantom-created in a no-examples project"


def test_shipped_skill_mirrors_are_byte_identical(copie_session_default):
    """The two shipped skill trees must not drift.

    .github/skills and .claude/skills are hand-maintained duplicates: Copilot
    reads one, Claude Code reads the other. Comparing directory names only
    (the previous check) passes while their contents diverge, so an edit to one
    copy ships a stale other -- and inside a generated project it is the
    .claude copy that Claude Code actually loads.
    """
    project_dir = copie_session_default.project_dir
    gh, cl = project_dir / ".github" / "skills", project_dir / ".claude" / "skills"
    if not (gh.is_dir() and cl.is_dir()):
        pytest.skip("skills not shipped to generated projects")

    gh_files = {p.relative_to(gh): p for p in gh.rglob("*") if p.is_file()}
    cl_files = {p.relative_to(cl): p for p in cl.rglob("*") if p.is_file()}

    assert set(gh_files) == set(cl_files), "shipped skill trees have different files"
    drifted = [str(rel) for rel, p in gh_files.items() if p.read_bytes() != cl_files[rel].read_bytes()]
    assert not drifted, f"shipped skill copies have drifted: {drifted}"


def test_reexported_members_render_in_the_api_page_table(copie_session_minimal):
    """The change's observable fix: the members TABLE is non-empty.

    Asserting that _get_public_members returns entries is not this. A lookup can
    resolve every symbol while the rendered page stays empty -- the per-member
    detail pages are written from a separate code path, so the interlock test
    passes too. This asserts the rendered markdown a reader actually sees, and
    fails if _build_members_tables stops emitting rows.
    """
    project_dir = copie_session_minimal.project_dir
    _write_reexport_package(project_dir, "minimal_project")
    markers = _load_markers(project_dir, "table_render")
    _reset_hook_caches(markers)

    markers._api_pages._generate_api_pages(project_dir)
    page = (project_dir / "docs" / "pages" / "api" / "shapes.md").read_text(encoding="utf-8")

    assert "### Classes" in page, "members table missing its Classes heading"
    assert "Circle" in page, "re-exported class absent from the rendered members table"
    assert "A round shape." in page, "row is missing the description lifted from the declaring module"
    assert "generated/minimal_project.shapes.Circle.md" in page, "row does not link to the member page"


def test_api_name_lookup_prefers_the_published_path(copie_session_minimal):
    """One symbol reachable by two paths resolves to the one users write."""
    project_dir = copie_session_minimal.project_dir
    (project_dir / "src" / "minimal_project" / "naive.py").write_text(
        '"""Naive."""\n\n\nclass SeasonalNaive:\n    """Repeat last season."""\n', encoding="utf-8"
    )
    pub = project_dir / "src" / "minimal_project" / "point"
    pub.mkdir(parents=True, exist_ok=True)
    (pub / "__init__.py").write_text(
        '"""Point."""\n\nfrom minimal_project.naive import SeasonalNaive\n\n__all__ = ["SeasonalNaive"]\n',
        encoding="utf-8",
    )
    markers = _load_markers(project_dir, "prefer_public")
    _reset_hook_caches(markers)

    lookup = markers._api_pages._get_api_name_lookup(project_dir)

    assert lookup.get("SeasonalNaive") == "minimal_project.point.SeasonalNaive", (
        f"published path not preferred; got {lookup.get('SeasonalNaive')!r}"
    )


def test_api_name_lookup_refuses_a_genuine_collision(copie_session_minimal):
    """Two different symbols sharing a short name resolve to nothing.

    A wrong link is worse than no link, so an ambiguous name degrades to plain
    text rather than pointing at whichever module happened to be scanned last.
    """
    project_dir = copie_session_minimal.project_dir
    for mod in ("dup_a", "dup_b"):
        (project_dir / "src" / "minimal_project" / f"{mod}.py").write_text(
            f'"""{mod}."""\n\n\nclass Duplicated:\n    """From {mod}."""\n', encoding="utf-8"
        )
    markers = _load_markers(project_dir, "collision")
    _reset_hook_caches(markers)

    lookup = markers._api_pages._get_api_name_lookup(project_dir)

    assert "Duplicated" not in lookup, (
        f"an ambiguous short name resolved to {lookup.get('Duplicated')!r} instead of being refused"
    )


def test_gallery_overflow_link_targets_the_real_gallery_page(copie_session_default):
    """The overflow link resolves to wherever the gallery page actually is.

    The gallery page is local-owned, so a project may move it; a hardcoded path
    404s silently. It is located by the <!-- GALLERY --> placeholder instead.

    Resolution mirrors use_directory_urls, under which `/a/b/` is served by
    EITHER `a/b.md` OR `a/b/index.md`. This test knew only the first form, so it
    passed while the url for an index page was `/a/b/index/` -- agreeing with the
    bug rather than catching it. Both forms are checked now.
    """
    project_dir = copie_session_default.project_dir
    markers = _load_markers(project_dir, "gallery_url")
    markers._GALLERY_PAGE_CACHE = None

    url = markers._get_gallery_page_url(project_dir)

    assert url, "gallery page not found by its GALLERY placeholder"
    docs = project_dir / "docs"
    stem = url.strip("/")
    candidates = [docs / f"{stem}.md", docs / stem / "index.md"]
    served = next((p for p in candidates if p.is_file()), None)
    assert served is not None, (
        f"overflow link {url} points at a page that does not exist "
        f"(tried {[str(p.relative_to(docs)) for p in candidates]})"
    )
    assert "<!-- GALLERY -->" in served.read_text(encoding="utf-8"), "located page is not the gallery"


def test_docs_engine_watches_only_its_own_source_dir(copie_session_default):
    """The engine watches `docs/` only; the supervisor owns `src/`.

    This inverts an earlier rule that required `src` in `watch`. Live API
    regeneration now comes from `docs_build/serve.py`, which watches `src/` and
    regenerates the pages under `docs/pages/api/` -- and the engine, watching
    `docs`, rebuilds. The engine must NOT watch `src`: doing so fires a second,
    stale rebuild before regeneration finishes, and the successor engine cannot
    watch paths outside the project folder at all, so an engine that watched
    `src` was never the portable answer.
    """
    config = _mkdocs_config(copie_session_default.project_dir)
    watched = config["watch"]
    assert watched == ["docs"], f"engine should watch only docs/; the supervisor owns src/: {watched}"
    # The supervisor is what watches src -- assert it exists and does so.
    serve = (copie_session_default.project_dir / BUILD_DIR / "serve.py").read_text(encoding="utf-8")
    assert "observer.schedule(handler, str(SRC)" in serve, "serve.py does not watch src/"
    assert "SRC = PROJECT_ROOT" in serve and '"src"' in serve, "serve.py's SRC is not the package source dir"


def test_config_file_does_not_watch_itself(copie_session_default):
    """`mkdocs.yml` must not appear in its own `watch:` list.

    It buys nothing: `mkdocs serve` watches the active config unconditionally
    (`mkdocs/commands/serve.py` calls `server.watch(config.config_file_path)`
    independently of this key), so listing it is redundant under MkDocs.

    It is actively destructive under Zensical, the successor engine: a config
    file naming itself here makes the build emit ZERO html, silently, at exit 0,
    and `--strict` does not change that. Measured against Zensical 0.0.51, with
    no open upstream issue tracking it. The template shipped this line, so every
    generated project would have published an empty site from a green build.

    A comment in `mkdocs.yml` cannot stop the line coming back. This can.
    """
    config = _mkdocs_config(copie_session_default.project_dir)
    watched = config.get("watch") or []
    assert "mkdocs.yml" not in watched, (
        f"mkdocs.yml watches itself, which builds an empty site at exit 0 under Zensical: {watched}"
    )


def test_companion_card_renders_with_resolved_links(copie_session_default):
    """The primary companion path: a card with working links, end to end.

    The cards are emitted as markdown so the [View]/[Open in marimo] rewrites
    below them resolve the URLs. Emitting resolved HTML instead would bypass
    those rewrites and ship literal placeholders -- which is why this asserts
    the rendered hrefs, not just that a card appeared.
    """
    project_dir = copie_session_default.project_dir
    _write_notebook(
        project_dir,
        "companion_nb",
        '"title": "Companion NB", "description": "Demo.", "category": "how-to",'
        ' "companion": "pages/how-to/configure.md"',
    )
    markers = _load_markers(project_dir, "companion_render")
    _reset_gallery_caches(markers)

    page = _FakePage("pages/how-to/configure.md", "pages/how-to/configure/index.html")
    config = {"repo_url": "https://github.com/s/p"}
    out = markers._inject("<!-- COMPANION_NOTEBOOKS -->", page, config=config)

    assert "COMPANION_NOTEBOOKS" not in out, "placeholder was not consumed"
    assert "## Try it interactively" in out, "heading not emitted with the cards"
    assert "Companion NB" in out, "companion card did not render"
    # pages/how-to/configure.md is three deep, so the rewrite prefixes ../../../
    assert "](../../../examples/companion_nb/" in out, f"View link not resolved to a relative path: {out[:200]}"
    assert "marimo.app" in out, "Open-in-marimo link not resolved to a playground URL"
    assert "](/examples/" not in out, "an unresolved absolute example path survived"


def test_changelog_page_has_a_populated_toc(copie_session_default):
    """The changelog is the page that most needs a ToC.

    Material's ToC partial takes first.children when the first heading is level
    1, so a page with two h1s renders an empty ToC -- silently, on the one page
    with a heading per release.
    """
    import markdown

    project_dir = copie_session_default.project_dir
    page = project_dir / "docs" / "pages" / "reference" / "changelog.md"
    md = markdown.Markdown(
        extensions=["pymdownx.snippets", "toc"],
        extension_configs={"pymdownx.snippets": {"base_path": ["docs", "."], "check_paths": True}},
    )
    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        md.convert(page.read_text(encoding="utf-8"))
    finally:
        os.chdir(cwd)

    tokens = md.toc_tokens
    assert tokens, "changelog page produced no table of contents"
    assert len([t for t in tokens if t["level"] == 1]) == 1, "more than one level-1 heading collapses Material's ToC"


def test_reexported_symbols_appear_in_the_api_index(copie_session_minimal):
    """The searchable API index lists re-exported symbols too.

    The index, the package pages and the name lookup must all be fed by the
    same member scan. Feeding the index from a scan that cannot see re-exports
    leaves it blind to exactly the symbols this resolution exists to surface:
    their pages exist and the lookup resolves them, while the index shows
    nothing.
    """
    project_dir = copie_session_minimal.project_dir
    _write_reexport_package(project_dir, "minimal_project")
    markers = _load_markers(project_dir, "api_index")
    _reset_hook_caches(markers)

    prefix = markers._site_root_prefix(_FakePage("pages/reference/api.md", "pages/reference/api/index.html"))
    html = markers._build_api_table_html(project_dir, prefix)

    assert "Circle" in html, "re-exported class absent from the searchable API index"
    assert "area" in html, "re-exported function absent from the searchable API index"

    # From pages/reference/api/, three levels reach the site root, then down to
    # pages/api/. Get this wrong and the table still renders fully populated
    # while every link 404s -- mkdocs does not validate hook-injected raw HTML.
    assert '<a href="../../../pages/api/generated/minimal_project.shapes.Circle/">' in html, (
        "symbol link does not resolve from pages/reference/api/ to the generated page"
    )
    assert '<a href="../../../pages/api/shapes/">' in html, (
        "module link does not resolve from pages/reference/api/ to the submodule page"
    )


@pytest.mark.parametrize(
    ("src_path", "dest_path", "prefix"),
    [
        ("pages/reference/api.md", "pages/reference/api/index.html", "../../../"),
        ("pages/api/index.md", "pages/api/index.html", "../../"),
    ],
)
def test_api_index_links_resolve_wherever_the_index_lives(copie_session_minimal, src_path, dest_path, prefix):
    """The API table's links work from any page the index is placed on.

    The template seeds the index at pages/reference/api.md, but a project may
    move it -- yohou keeps it at pages/api/index.md, one level shallower. A
    hardcoded `../../` is right for the seeded location and silently 404s every
    one of the other's links: the table renders fully populated, and mkdocs
    cannot catch it because it does not validate raw HTML injected by a hook.

    So the prefix is derived from the page, and this checks both layouts by
    resolving each href against the page's own URL -- the arithmetic is the
    whole point, and asserting on a literal string would just restate it.
    """
    project_dir = copie_session_minimal.project_dir
    _write_reexport_package(project_dir, "minimal_project")
    markers = _load_markers(project_dir, f"api_index_{src_path.count('/')}_{len(prefix)}")
    _reset_hook_caches(markers)

    page = _FakePage(src_path, dest_path)
    assert markers._site_root_prefix(page) == prefix

    html = markers._build_api_table_html(project_dir, markers._site_root_prefix(page))
    hrefs = re.findall(r'<a href="([^"]+)"', html)
    assert hrefs, "the API table emitted no links at all"

    page_dir = posixpath.dirname(dest_path)
    for href in hrefs:
        resolved = posixpath.normpath(posixpath.join(page_dir, href))
        assert resolved.startswith("pages/api/"), (
            f"from {dest_path}, href {href!r} resolves to {resolved!r} -- outside pages/api/, so it 404s"
        )


@pytest.mark.parametrize(
    ("src_path", "dest_path", "template_name"),
    [
        ("pages/reference/api.md", "pages/reference/api/index.html", "api-index.html"),
        ("pages/api/index.md", "pages/api/index.html", "api-index.html"),
        ("pages/api/shapes.md", "pages/api/shapes/index.html", "api-submodule.html"),
    ],
)
def test_module_toc_is_built_and_resolves_wherever_the_page_lives(
    copie_session_minimal, src_path, dest_path, template_name
):
    """Any page declaring an API template gets a module TOC whose links resolve.

    Two failures this pins, both silent. The TOC used to be keyed on the
    hardcoded path `pages/reference/api.md`, so a project that moved its index --
    yohou keeps it at pages/api/index.md -- got no module_toc at all and rendered
    an empty sidebar with nothing erroring. And its urls hardcoded that same
    page's depth, so they 404'd from anywhere else.

    Keying on the declared template is the fix: a page says what it is, rather
    than being recognised by where it sits.
    """
    project_dir = copie_session_minimal.project_dir
    _write_reexport_package(project_dir, "minimal_project")
    markers = _load_markers(project_dir, f"mtoc_{template_name}_{src_path.count('/')}")
    markers._api_pages._SURFACE_CACHE = None

    # The submodule pages the TOC points at are generated, not committed.
    markers._api_pages._generate_api_pages(project_dir)

    page = _FakePage(src_path, dest_path)
    page.meta["template"] = template_name
    # _set_module_toc reads the project root from _markers.py's own location and
    # returns None, writing the sidebar onto page.meta directly.
    markers._set_module_toc(page)

    toc = page.meta.get("module_toc")
    assert toc, f"a page declaring {template_name} got no module_toc"

    page_dir = posixpath.dirname(dest_path)
    for entry in toc:
        resolved = posixpath.normpath(posixpath.join(page_dir, entry["url"]))
        assert resolved.startswith("pages/api/"), (
            f"from {dest_path}, TOC url {entry['url']!r} resolves to {resolved!r} -- it 404s"
        )
        assert (project_dir / "docs" / f"{resolved}.md").exists() or (project_dir / "docs" / resolved).exists(), (
            f"TOC url {entry['url']!r} points at a page that does not exist"
        )


def _write_dependency_shim(project_dir, package_name):
    """A plain module whose public API is re-exported from outside the package.

    Uses stdlib modules as the "dependency": they are outside the generated
    package exactly as a third-party one is, and they are always installed, so
    the test does not depend on the resolver finding some optional extra.
    """
    pkg = project_dir / "src" / package_name
    (pkg / "shim.py").write_text(
        '"""Convenience re-exports."""\n\n'
        "from dataclasses import dataclass\n"
        "from fractions import Fraction\n\n"
        '__all__ = ["Fraction", "dataclass"]\n',
        encoding="utf-8",
    )
    (pkg / "helpers.py").write_text(
        '"""Helpers."""\n\n\nclass Helper:\n    """A helper."""\n',
        encoding="utf-8",
    )
    # A plain module with no __all__ importing a sibling for its own use. The
    # import is IN-package, so it resolves -- nothing but the missing __all__
    # keeps it out of the API. An out-of-package import would not test this:
    # the external resolver already refuses to run without __all__.
    (pkg / "internal.py").write_text(
        '"""Uses a helper; exports nothing."""\n\n'
        "from .helpers import Helper\n\n\n"
        "def ratio():\n"
        '    """Build a helper."""\n'
        "    return Helper()\n",
        encoding="utf-8",
    )
    return pkg


def test_dependency_reexports_stay_in_the_api(copie_session_minimal):
    """A name re-exported from a dependency and named in __all__ is public API.

    A convenience shim (``from otherpkg import Widget`` under this package's
    ``__all__``) declares nothing itself and its source lives outside the
    package, so resolution that only follows in-package imports drops the name
    entirely: gone from the index, and no page. Measured on a real project, that
    silently removed three of its four public symbols and rendered its module
    page as a bare docstring.

    The kind and docstring must come from the declaring module rather than being
    guessed, so a class stays a class and carries its real summary.
    """
    project_dir = copie_session_minimal.project_dir
    _write_dependency_shim(project_dir, "minimal_project")
    markers = _load_markers(project_dir, "depshim")
    _reset_hook_caches(markers)

    members = markers._get_public_members(project_dir, "shim")

    assert {e["name"] for e in members["classes"]} == {"Fraction"}, "a re-exported dependency class was dropped"
    assert {e["name"] for e in members["functions"]} == {"dataclass"}, "a re-exported dependency function was dropped"
    fraction = next(e for e in members["classes"] if e["name"] == "Fraction")
    assert fraction["doc"], "the docstring was not read from the declaring module"
    assert fraction["reexported"] is True


def test_plain_module_imports_are_not_api_without_dunder_all(copie_session_minimal):
    """Without __all__, a plain module's imports stay private.

    Re-export resolution is not limited to __init__.py, because a plain module
    can be a shim. That generality is what makes this necessary: in an ordinary
    module an import is a private detail (imported to be *used*), and treating it
    as API would publish every helper a module happens to import.

    The import here is in-package on purpose. It resolves, so only the absent
    __all__ stands between it and the API -- an out-of-package import would pass
    this test without exercising anything, since the external resolver already
    refuses to run without __all__.
    """
    project_dir = copie_session_minimal.project_dir
    _write_dependency_shim(project_dir, "minimal_project")
    markers = _load_markers(project_dir, "depshim_internal")
    _reset_hook_caches(markers)

    members = markers._get_public_members(project_dir, "internal")
    names = {e["name"] for e in members["classes"] + members["functions"]}

    assert "ratio" in names, "the module's own function is missing"
    assert "Helper" not in names, "a sibling imported for internal use leaked into the API without __all__"


def test_third_party_import_rejected_without_dunder_all(copie_session_minimal):
    """Without __all__, the package-root guard is what excludes stdlib imports.

    The __all__-bearing fixture cannot show this: the filter rejects Path before
    the guard is consulted. This exercises the guard itself.
    """
    project_dir = copie_session_minimal.project_dir
    _write_reexport_package(project_dir, "minimal_project")
    markers = _load_markers(project_dir, "noall")

    members = markers._get_public_members(project_dir, "noall")
    names = {e["name"] for e in members["classes"] + members["functions"]}

    assert "Gadget" in names, "first-party re-export not resolved without __all__"
    assert "Path" not in names, "a stdlib import was resolved as package API"


def test_discovery_imports_nothing(copie_session_minimal, tmp_path):
    """A module whose body raises on import is still discovered.

    Discovery is static, so a project's own dependencies may be absent when the
    docs build runs -- which is the whole reason the previous implementation's
    ``_resolve_external_module`` was a hazard: it called ``find_spec``, which
    imports the parent package to locate a symbol.

    The module below raises at import time. If anything in the discovery path
    imports it, this test errors rather than fails, which is the signal wanted.
    """
    project_dir = copie_session_minimal.project_dir
    pkg = project_dir / "src" / "minimal_project"
    (pkg / "explodes.py").write_text(
        '"""Explodes on import."""\n\nraise RuntimeError("importing this module is a bug")\n\n\n'
        'class Survivor:\n    """Found by static analysis regardless."""\n',
        encoding="utf-8",
    )
    try:
        markers = _load_markers(project_dir, "noimport")
        members = markers._get_public_members(project_dir, "explodes")
        names = {e["name"] for e in members["classes"] + members["functions"]}
        assert "Survivor" in names, "a class in an unimportable module was not discovered"
    finally:
        (pkg / "explodes.py").unlink()


def test_unresolvable_reexport_warns_rather_than_vanishing(copie_session_minimal, caplog):
    """An unresolvable re-export is reported, not silently dropped.

    The previous implementation returned None for anything it could not reach
    and the symbol disappeared from the index with no error -- a green build and
    a missing page, this fleet's signature failure. Griffe distinguishes
    "resolved" from "unresolvable", and that distinction is only worth having if
    something says so.

    ``nox -s check_docs`` builds with warnings fatal, so this warning is a CI
    failure there while an ordinary ``mkdocs serve`` keeps working.
    """
    import logging

    project_dir = copie_session_minimal.project_dir
    pkg = project_dir / "src" / "minimal_project"
    shim = pkg / "ghost.py"
    shim.write_text(
        '"""Re-exports something that cannot be resolved."""\n\n'
        "from definitely_not_installed_pkg import Ghost\n\n"
        '__all__ = ["Ghost"]\n',
        encoding="utf-8",
    )
    try:
        markers = _load_markers(project_dir, "ghost")
        with caplog.at_level(logging.WARNING, logger="mkdocs.hooks"):
            members = markers._get_public_members(project_dir, "ghost")
        names = {e["name"] for e in members["classes"] + members["functions"]}
        assert "Ghost" not in names, "an unresolvable symbol was published as if it had a page"
        assert any("Ghost" in r.getMessage() for r in caplog.records), (
            "the symbol vanished silently, which is the behaviour this replaced; "
            f"warnings seen: {[r.getMessage() for r in caplog.records]}"
        )
    finally:
        shim.unlink()


def test_companion_placeholder_renders_no_dangling_heading(copie_session_default):
    """A page with no matching notebooks renders nothing -- not a bare heading.

    The heading is emitted with the cards rather than written into the page, so
    removing a notebook's companion cannot leave an empty section behind.
    """
    project_dir = copie_session_default.project_dir
    markers = _load_markers(project_dir, "companion_empty")
    _reset_gallery_caches(markers)

    page = _FakePage("pages/how-to/troubleshooting.md", "pages/how-to/troubleshooting/index.html")
    out = markers._inject("<!-- COMPANION_NOTEBOOKS -->", page, config={"repo_url": "https://github.com/s/p"})

    assert out.strip() == "", f"an unmatched placeholder left content behind: {out!r}"


_CLASSIFICATION_PATTERNS = (
    "src/",
    "tests/",
    "examples/",
    "docs/examples/",
    ".github/skills/",
    ".claude/skills/",
    # mkdocstrings template overrides. A whole tree rather than a line per file:
    # its shape follows mkdocstrings' own template layout, so it changes when
    # that does, and a per-file list would go stale on every handler bump. Lives
    # under docs_build/ (outside docs_dir) so the successor engine cannot publish
    # it, since that engine ignores exclude_docs.
    f"{TEMPLATES_DIR}/",
)


def _unclassified_files(project_dir, package_name):
    """Generated files that the update classification does not cover."""
    classification = (
        project_dir / ".github" / "skills" / "update-from-template" / "references" / "file-classification.md"
    ).read_text(encoding="utf-8")
    missing = []
    for path in sorted(project_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(project_dir).as_posix()
        if rel.startswith(".git/"):
            continue
        # Pattern entries (src/<package_name>/**, tests/**, ...) cover whole
        # trees; requiring a line per file there would be unmaintainable in the
        # opposite direction.
        if rel.startswith(_CLASSIFICATION_PATTERNS) or rel.startswith(f"src/{package_name}/"):
            continue
        if rel not in classification:
            missing.append(rel)
    return missing


@pytest.mark.parametrize("include_examples", [True, False])
def test_every_generated_file_is_classified(copie, include_examples):
    """Every file the template ships has an update tier.

    The classification tells whoever resolves an update conflict whether the
    template's version or the project's wins. A file with no tier gives them no
    rule at the moment they most need one -- and the list is maintained by hand,
    so nothing notices a new file arriving without an entry. That is how two
    shipped pages went unclassified, one of which a real update wanted to strip
    212 lines from.

    Generates a fresh project rather than reusing a session fixture: this asks
    what the TEMPLATE ships, and a shared fixture accumulates build artifacts
    (.nox, __pycache__, generated API pages) from whichever tests ran first.

    Both include_examples values run: a file behind that gate ships in only one
    variant.
    """
    result = copie.copy(extra_answers={"include_examples": include_examples})
    project_dir = result.project_dir
    missing = _unclassified_files(project_dir, "test_project")

    assert not missing, (
        f"these generated files have no update tier, so a conflict on them has no resolution rule: {missing}"
    )


@pytest.mark.parametrize("include_examples", [True, False])
def test_generated_project_is_ruff_format_clean(copie, include_examples):
    """A freshly generated project passes ``ruff format --check``.

    The template's Python is authored in ``.jinja`` files, which ruff does not
    recognise as Python and never formats in this repo. So unformatted code can
    ship, and because the generated ``pyproject.toml`` enables preview-style
    formatting, a generated project's first ``pre-commit run`` reformats
    template-owned files (``docs_build/_markers.py`` chief among them) and reds its CI on
    arrival -- the fix then drifts the file from the template, guaranteeing a
    conflict at the next update. This checks the emitted code, not the code the
    template happens to be.

    Both include_examples values run: the gallery code ships in only one variant,
    so a formatting slip behind that gate is invisible to the other.

    Runs ruff via the project's own config (discovered from its pyproject.toml),
    so the check matches what the project would run.
    """
    ruff = shutil.which("ruff")
    if ruff is None:
        pytest.skip("ruff is not installed in the test environment")

    result = copie.copy(extra_answers={"include_examples": include_examples})
    project_dir = result.project_dir

    check = subprocess.run(
        [ruff, "format", "--check", "."],
        cwd=project_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    diff = subprocess.run(
        [ruff, "format", "--check", "--diff", "."],
        cwd=project_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    assert check.returncode == 0, (
        "the template ships Python that ruff would reformat, so a generated "
        f"project's first `pre-commit run` reds CI:\n{diff.stdout}{check.stdout}{check.stderr}"
    )


@pytest.mark.parametrize("include_examples", [True, False])
def test_generated_project_passes_ruff_check(copie, include_examples):
    """A freshly generated project passes ``ruff check``.

    The format guard above is not enough: it proved the template's Python is
    *shaped* right, while nothing checked whether it *lints*. A class-based hook
    shipped with three ARG002 violations under exactly that blind spot, and every
    generated project without a local ARG002 ignore failed its first
    `pre-commit run` -- the same failure the format guard exists to prevent,
    through the other half of the same door.

    Runs ruff with the project's own config, so this is what the project runs.
    """
    ruff = shutil.which("ruff")
    if ruff is None:
        pytest.skip("ruff is not installed in the test environment")

    result = copie.copy(extra_answers={"include_examples": include_examples})
    check = subprocess.run(
        [ruff, "check", "--force-exclude", "--no-fix", "."],
        cwd=result.project_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    assert check.returncode == 0, (
        "the template ships Python that fails `ruff check`, so a generated "
        f"project's first `pre-commit run` reds CI:\n{check.stdout}{check.stderr}"
    )


def test_update_guidance_restores_local_owned_files(copie_session_default):
    """The local-owned remedy must restore, not merely discard the rejection.

    A rejected-hunks update applies every hunk that applies and rejects only the
    rest, so a conflicted file is already partially updated. Guidance that treats
    the rejection's presence as evidence the file is untouched leads to keeping
    the template's changes in a file the project owns -- silently, with the
    update reporting success. Measured once: a local-owned page went 184 lines to
    78.
    """
    skill_dir = copie_session_default.project_dir / ".github" / "skills" / "update-from-template"
    if not skill_dir.is_dir():
        pytest.skip("update-from-template skill not shipped to generated projects")
    skill = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    conflicts = (skill_dir / "references" / "conflict-resolution.md").read_text(encoding="utf-8")

    assert "git checkout HEAD -- <file>" in skill, "the local-owned remedy does not restore the project's version"
    assert "Delete `.rej` without applying" not in skill, (
        "the local-owned remedy discards the rejection without undoing the hunks that already applied"
    )
    for wrong in ("Keeps local file intact", "local file is clean", "local file** unchanged"):
        assert wrong not in conflicts, f"the guidance still claims a conflicted file is untouched: {wrong!r}"


@contextlib.contextmanager
def caplog_at_warning():
    """Collect WARNING records from the hooks' mkdocs logger."""
    records = []

    class _Collect(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    logger = logging.getLogger("mkdocs.hooks")
    handler = _Collect(level=logging.WARNING)
    logger.addHandler(handler)
    previous, logger.disabled = logger.disabled, False
    try:
        yield records
    finally:
        logger.removeHandler(handler)
        logger.disabled = previous


def _write_sectioned_notebook(examples_dir, stem, *, title, section="", category="how-to", companion=None):
    """Write a marimo notebook whose __gallery__ carries section/companion keys.

    Distinct from _write_notebook above, which takes a raw gallery body: these
    tests care about specific keys, so they name them rather than spelling out
    the literal each time.
    """
    examples_dir.mkdir(parents=True, exist_ok=True)
    fields = [f'"title": {title!r}', f'"description": "Demo of {title}."', f'"category": {category!r}']
    if section:
        fields.append(f'"section": {section!r}')
    if companion:
        fields.append(f'"companion": {companion!r}')
    body = ",\n    ".join(fields)
    (examples_dir / f"{stem}.py").write_text(
        f'"""Notebook."""\n\nimport marimo\n\n__generated_with = "0.9.0"\n__gallery__ = {{\n    {body},\n}}\napp = marimo.App()\n',
        encoding="utf-8",
    )


def test_seed_pages_every_project_rewrites_are_never_redelivered(copie_session_default):
    """The landing page and the tutorial are seeded once, then left alone.

    Same shape as the logos: the template ships a placeholder every real project
    rewrites wholesale, then keeps trying to patch it. Copier applies an update as
    a diff against the *template's* version, so once the local file no longer
    resembles it, one shifted line rejects the whole hunk and the page silently
    reverts to the stub. v0.22.0 proved it -- gating a blank line behind
    {% raw %}{% if include_examples %}{% endraw %} was whitespace-only for projects without
    examples and still replaced a 244-line curated tutorial with the 74-line stub.
    Five of five projects with a customised getting-started.md were hit.
    """
    import yaml

    copier_yml = yaml.safe_load((Path(__file__).parent.parent / "copier.yml").read_text(encoding="utf-8"))
    skipped = copier_yml.get("_skip_if_exists") or []

    # The gallery index goes the same way once curated: yohou's lists six
    # hand-written section pages and v0.22.0 overwrote it with the generic one.
    # Troubleshooting was the one this list missed. A project's entries are about
    # Troubleshooting was briefly on this list and is deliberately not any more: see
    # test_the_template_seeds_no_troubleshooting_page. Skip-listing a page cuts both
    # ways, and that one was wanted by four projects and unwanted by three.
    seed_pages = (
        "docs/index.md",
        "docs/pages/tutorials/getting-started.md",
        "docs/pages/examples/index.md",
    )
    for page in seed_pages:
        assert page in skipped, f"{page} is re-delivered on every update; a stray line reverts it to the stub"

    # Still seeded, so a new project has a landing page, a tutorial and a gallery.
    for page in seed_pages:
        assert (copie_session_default.project_dir / page).is_file(), f"{page} is not seeded for a new project"


# Binaries the template ships and deliberately keeps overwriting. Skip-listing one of
# these would strand every project on the version it was generated with, so their
# absence from `_skip_if_exists` is a decision, not an oversight.
TEMPLATE_MANAGED_BINARIES = {
    "docs/assets/made_by_stateful-y.png": (
        "the org wordmark is the template's asset, not the project's; projects should "
        "track the current mark rather than freeze on their generation-time one"
    ),
}


def test_every_shipped_binary_is_classified():
    """Each binary the template ships is either skip-listed or named template-managed.

    Copier rewrites a binary on **every** run regardless of diff, with no conflict, no
    `.rej` and nothing in its output but a `Bin NNNN -> NNNN` line. `_skip_if_exists` is
    the only thing that stops it, so for a project-owned asset, absence from that list
    means artwork waiting to be destroyed.

    But "every binary must be skip-listed" is the wrong invariant, and asserting it would
    do damage. `made_by_stateful-y.png` is the org wordmark: the template *should* keep
    overwriting it, or a project generated two years ago displays a two-year-old mark
    forever. The v0.42.0 fan-out reported its absence from the skip list as a latent bug,
    having correctly measured that copier overwrites it every run. The measurement was
    right and the conclusion was backwards, which is why this test encodes the
    distinction rather than the count.

    So the real invariant is that every shipped binary is **classified**: project-owned
    and skip-listed, or template-managed and named above with a reason. A newly added
    binary belongs to neither set and fails here, which is the case the hand-maintained
    list could not catch.
    """
    import yaml

    root = Path(__file__).parent.parent
    copier_yml = yaml.safe_load((root / "copier.yml").read_text(encoding="utf-8"))
    skipped = set(copier_yml.get("_skip_if_exists") or [])

    template_dir = root / "template"
    binaries = []
    for path in sorted(template_dir.rglob("*")):
        if not path.is_file():
            continue
        # Detect by content, not by extension: a new asset type would slip past an
        # allowlist of suffixes the same way a new PNG slipped past a path list.
        if b"\0" not in path.read_bytes()[:8192]:
            continue
        binaries.append(path.relative_to(template_dir).as_posix())

    assert binaries, (
        "found no binaries under template/, so this test proves nothing. Either the "
        "null-byte detection is broken or the assets moved; fix the check, do not delete it"
    )

    unclassified = [b for b in binaries if b not in skipped and b not in TEMPLATE_MANAGED_BINARIES]
    assert not unclassified, (
        "these binaries are neither in _skip_if_exists nor listed as template-managed, so "
        "copier rewrites them on every run with no conflict and no .rej, and nothing "
        f"records whether that is intended: {unclassified}. Classify each one, with a reason."
    )

    # The two sets must stay disjoint, or the classification says nothing.
    both = sorted(set(TEMPLATE_MANAGED_BINARIES) & skipped)
    assert not both, f"binaries claimed as template-managed but also skip-listed: {both}"


def test_companion_marker_that_resolves_to_nothing_warns(copie_session_default):
    """A well-formed COMPANION_NOTEBOOKS naming no notebook is reported.

    The catch-all added in v0.21.2 only sees markers nothing *recognised*. A
    well-formed one is consumed and replaced with an empty string, so a page that
    asked for cards renders blank and the catch-all never sees it. This is the one
    marker the template seeds by default -- it relies on hello.py naming the
    tutorial, so any project that replaces hello.py without re-pointing its
    `companion` silently empties that section. Exactly the shape v0.21.2 existed
    to close, left open on the template's own default.
    """
    project_dir = copie_session_default.project_dir
    markers = _load_markers(project_dir, "companion_resolves_to_nothing")
    _reset_gallery_caches(markers)
    page = _FakePage("pages/tutorials/named-by-nobody.md", "pages/tutorials/named-by-nobody/index.html")

    with caplog_at_warning() as records:
        out = markers._inject(
            "# T\n\n<!-- COMPANION_NOTEBOOKS -->\n\n## Body\n", page, config={"repo_url": "https://x/y"}
        )

    assert records, "a page asked for companion cards, got none, and said nothing"
    assert "named-by-nobody" in " ".join(records), "the warning does not name the offending page"
    assert "<!-- COMPANION_NOTEBOOKS -->" not in out, "the marker leaked into the page"


def test_sectioned_gallery_is_still_findable_for_the_overflow_link(copie_session_default):
    """A gallery split across section pages still has a home to link to.

    A gallery too big for one page has no bare <!-- GALLERY --> at all -- it is a
    directory of <!-- GALLERY:section:... --> pages behind an index. Looking only
    for the bare marker returned None for those projects, and the caller dropped
    the "see all N examples" link on an `and gallery_url`. The symbols that
    overflow the cap are the most-used ones, so the link vanished exactly where
    the remaining examples mattered most: yohou renders 6 of
    PointReductionForecaster's 45 and links to none of the other 39. Silently --
    no marker is involved, so the catch-all cannot see it.
    """
    project_dir = copie_session_default.project_dir
    examples = project_dir / "docs" / "pages" / "examples"
    gallery = examples / "index.md"
    original = gallery.read_text(encoding="utf-8")

    # Reshape into a sectioned gallery: a curated index with no bare marker, and
    # section pages beside it. This is yohou's shape.
    gallery.write_text("# Examples\n\n- [Alpha](alpha.md)\n", encoding="utf-8")
    (examples / "alpha.md").write_text("# Alpha\n\n<!-- GALLERY:section:alpha -->\n", encoding="utf-8")
    markers = _load_markers(project_dir, "sectioned_gallery_home")
    try:
        _reset_gallery_caches(markers)
        assert "<!-- GALLERY -->" not in gallery.read_text(encoding="utf-8"), "fixture still has a bare marker"
        url = markers._get_gallery_page_url(project_dir)
        assert url == "/pages/examples/", (
            f"a sectioned gallery has no findable home (got {url!r}); the overflow link is dropped"
        )
    finally:
        (examples / "alpha.md").unlink()
        gallery.write_text(original, encoding="utf-8")
        _reset_gallery_caches(markers)


def test_dropped_overflow_link_warns(copie_session_default):
    """Having nowhere to link the remaining examples is reported, not swallowed.

    The drop happens on an `if`, not a marker, so nothing else can notice it.
    """
    project_dir = copie_session_default.project_dir
    markers = _load_markers(project_dir, "dropped_overflow_warns")
    _reset_gallery_caches(markers)

    # More notebooks than the cap, all using one symbol, and no gallery page.
    examples_dir = project_dir / "examples"
    for i in range(markers._API_EXAMPLES_CAP + 2):
        _write_sectioned_notebook(examples_dir, f"overflow_{i}", title=f"Overflow {i}", section="s")
    markers._NOTEBOOK_API_USAGE_CACHE = {"test_project.Widget": markers._get_gallery_items(project_dir)}
    markers._GALLERY_PAGE_CACHE = ""  # no gallery page anywhere

    with caplog_at_warning() as records:
        html = markers._build_api_examples_html(project_dir, "test_project.Widget")

    assert "See all" not in html, "the fixture did not reproduce the drop"
    assert records, "the overflow link was dropped with nothing said"
    assert "Widget" in " ".join(records), "the warning does not name the symbol whose examples were dropped"


def test_gallery_overflow_link_resolves_for_an_index_page(copie_session_default):
    """The "see all examples" link points where the gallery actually serves.

    Under use_directory_urls, `pages/examples/index.md` serves at
    `/pages/examples/` -- but the URL was built from the file path, yielding
    `/pages/examples/index/`, a 404. Dormant while the gallery was a non-index
    page; v0.22.0 moved it to index.md and so shipped the break by default.

    The link is emitted as raw HTML, so mkdocs never validates it and even
    --strict cannot see it: it surfaces only in RTD's post-build linkchecker.
    Driven through the real generated tree because that is the shape that broke.
    """
    project_dir = copie_session_default.project_dir
    gallery = project_dir / "docs" / "pages" / "examples" / "index.md"
    assert "<!-- GALLERY -->" in gallery.read_text(encoding="utf-8"), (
        "the seeded gallery page carries no <!-- GALLERY --> marker; this test would assert nothing"
    )

    markers = _load_markers(project_dir, "gallery_url_index")
    _reset_gallery_caches(markers)
    url = markers._get_gallery_page_url(project_dir)

    assert url == "/pages/examples/", f"the gallery link is {url!r}, which 404s; the page serves at /pages/examples/"

    # A gallery that is NOT an index page keeps its own segment -- the case that
    # worked before and must keep working.
    other = project_dir / "docs" / "pages" / "examples" / "browse.md"
    gallery_text = gallery.read_text(encoding="utf-8")
    gallery.write_text("# Moved\n", encoding="utf-8")
    other.write_text(gallery_text, encoding="utf-8")
    try:
        _reset_gallery_caches(markers)
        assert markers._get_gallery_page_url(project_dir) == "/pages/examples/browse/", (
            "a non-index gallery page lost its own path segment"
        )
    finally:
        other.unlink()
        gallery.write_text(gallery_text, encoding="utf-8")
        _reset_gallery_caches(markers)


def test_docs_use_no_em_or_en_dashes(copie_session_default):
    """Seeded prose punctuates without em or en dashes.

    A house style rule, and the template is where it has to hold: its pages are
    the first draft of every project's docs, so a dash seeded here is one every
    project inherits and nobody re-reads. Ranges are not punctuation and are left
    alone; this only catches the dash standing in for a comma, colon or bracket.
    """
    docs = copie_session_default.project_dir / "docs"
    pages = sorted(p for p in docs.rglob("*.md") if "examples" not in p.relative_to(docs).parts)
    assert pages, "no docs pages generated; this test would assert nothing"

    offenders = []
    for page in pages:
        for lineno, line in enumerate(page.read_text(encoding="utf-8").splitlines(), 1):
            for dash in ("\u2014", "\u2013"):
                if dash in line:
                    offenders.append(f"{page.relative_to(docs)}:{lineno}: {line.strip()}")

    assert not offenders, "seeded docs punctuate with em/en dashes:\n" + "\n".join(offenders)


# What the fleet actually runs, verified against all seven generated repos. A pin the
# fleet does not run is not a stale version number, it is a permanent local delta in
# every repo that copier must replay on every release -- see the test below.


def test_action_pins_are_consistent_and_current(copie_session_default):
    """Every workflow pins one version per action, and it is the one the fleet runs.

    A pin the fleet does not run is not a stale version number. Dependabot bumps the
    repo, so the difference becomes a local delta copier must replay on every release,
    and when a release touches that workflow the hunk can fail and take the repo's own
    bump down with it -- silently, because the older version still works and CI stays
    green. The template pinned checkout @v6 against a fleet on @v7 and two repos had
    the pin stranded on the wrong job. Then v0.25.0 fixed checkout alone, and the very
    next fan-out found `github-script` doing it again in two more repos: the repo's
    v8->v9 bump shared a hunk with its v6->v7 checkout bump, the hunk stopped applying
    once the template shipped v7 itself, and github-script silently fell back to v8.

    This asserted only actions/checkout while four other pins matched no repo in the
    fleet, which is why it passed throughout. Checking every action is the point: a
    partial check that reads as a complete one is worse than none.

    Pinned rather than merely self-consistent: consistency alone is satisfied by the
    whole fleet drifting together, which is the state this fixes.
    """
    workflows = sorted((copie_session_default.project_dir / ".github" / "workflows").glob("*.yml"))
    assert workflows, "no workflows generated"

    pins = {}
    for wf in workflows:
        for match in re.finditer(r"uses:\s*([\w./-]+)@(\S+)", wf.read_text(encoding="utf-8")):
            pins.setdefault(match.group(1), {}).setdefault(match.group(2), []).append(wf.name)

    assert pins, "no `uses:` action pins found at all; this test would assert nothing"

    split = {a: {v: sorted(f) for v, f in vs.items()} for a, vs in pins.items() if len(vs) > 1}
    assert not split, f"these actions are pinned at more than one version: {split}"

    # Currency is no longer asserted here. It used to be checked against a hand-written
    # map of sixteen actions in this file, which is a second source of truth that can
    # only drift: it went stale once with four pins matching no repo alive, and the test
    # stayed green throughout. The shared Renovate preset now reads the template's own
    # `uses:` refs directly, so a stale pin arrives as a pull request instead of as a
    # silently-passing assertion. What remains here is the part that is derived from the
    # rendered project and cannot go stale: one version per action.


@pytest.mark.slow
def test_action_pins_actually_resolve_on_github(copie_session_default):
    """Every action ref the template ships resolves to a real ref on GitHub.

    ``test_action_pins_are_consistent_and_current`` checks the template's pins are
    self-consistent -- it cannot tell whether a tag *exists*. That
    gap shipped ``ossf/scorecard-action@v2`` (no such tag; the action publishes only
    ``vX.Y.Z`` tags), which passed every test and then failed at runtime on every
    generated repo with "unable to find version v2". This closes it by resolving each
    pinned ref against GitHub.

    Network-gated: skips cleanly when ``gh`` or the network is unavailable, so it is a
    CI safety net (CI has an authenticated ``gh`` and no rate limit) rather than an
    offline tripwire. Marked ``slow`` so it stays out of the fast feedback loop.
    """
    gh = shutil.which("gh")
    if gh is None:
        pytest.skip("gh CLI not available")
    missing = {}
    uncheckable = []
    pins = {}
    for wf in sorted((copie_session_default.project_dir / ".github" / "workflows").glob("*.yml")):
        for match in re.finditer(r"uses:\s*([\w./-]+)@(\S+)", wf.read_text(encoding="utf-8")):
            pins[match.group(1)] = match.group(2)
    assert pins, "no action refs found in the rendered project; this test would verify nothing"

    for action, ref in pins.items():
        repo = "/".join(action.split("/")[:2])  # github/codeql-action/init -> github/codeql-action
        result = subprocess.run(
            [gh, "api", f"repos/{repo}/commits/{ref}", "--jq", ".sha"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode == 0:
            continue
        err = (result.stderr + result.stdout).lower()
        if "not found" in err or "404" in err or "no commit found" in err:
            # Definitive: the ref does not exist. This is the failure worth catching.
            missing[f"{action}@{ref}"] = result.stderr.strip()[:120]
        else:
            # Cannot verify: gh unauthenticated (no GH_TOKEN, e.g. the CI test env),
            # rate limited, or offline. Do NOT fail on these -- only a real 404 fails.
            uncheckable.append(f"{action}@{ref}")
    # A definitive 404 fails regardless of any refs we could not check.
    assert not missing, (
        f"these pinned action refs do not exist on GitHub (a non-existent pin passes the consistency "
        f"check but fails at runtime on every generated repo -- as ossf/scorecard-action@v2 did): {missing}"
    )
    if uncheckable:
        pytest.skip(
            f"could not verify {len(uncheckable)}/{len(pins)} pins "
            f"(gh unauthenticated or network unavailable); e.g. {uncheckable[0]}"
        )


def test_nav_order_is_diataxis_with_reference_last(copie_session_default, copie_minimal):
    """The nav reads learn -> do -> see -> understand -> look up, in that order.

    Reference is last on purpose: it is where you stop reading and start looking
    things up, so it earns its place by being findable rather than by being passed
    through. The fleet had drifted into three different orders -- only yohou put
    Reference last -- and the template itself shipped Reference before Explanation,
    which is where four of the repos got it from.

    Examples is present exactly when the package has notebooks: a nav entry for a
    section that does not exist is a build error, and a package with notebooks and
    no Examples entry hides them entirely.
    """
    import yaml

    class _Loader(yaml.SafeLoader):
        pass

    _Loader.add_multi_constructor("!", lambda loader, suffix, node: None)
    # `pymdownx.emoji` names its index and generator as callables, which YAML can
    # only express as `!!python/name:`. That is a global tag, so the `!` handler
    # above does not catch it and a bare SafeLoader raises ConstructorError.
    _Loader.add_multi_constructor("tag:yaml.org,2002:python/name:", lambda loader, suffix, node: suffix)

    def _top_level(project_dir):
        nav = yaml.load((project_dir / "mkdocs.yml").read_text(encoding="utf-8"), Loader=_Loader)["nav"]
        return [key for entry in nav if isinstance(entry, dict) for key in entry]

    with_examples = _top_level(copie_session_default.project_dir)
    assert with_examples == ["Home", "Tutorials", "How-to Guides", "Examples", "Explanation", "Reference"], (
        f"nav order drifted: {with_examples}"
    )

    # A package with no notebooks must not advertise an Examples section.
    result = copie_minimal.copy(extra_answers={"include_examples": False})
    without = _top_level(result.project_dir)
    assert "Examples" not in without, f"a package with no notebooks still has an Examples nav entry: {without}"
    assert without[-1] == "Reference", f"Reference is not last without examples: {without}"


def test_examples_are_a_top_level_section(copie_session_default):
    """Examples is its own nav section, not a page filed under Tutorials.

    A gallery is not a tutorial: it holds how-tos too, it is browsed rather than
    read in order, and it grows until it needs subpages of its own. Filing it
    under Tutorials caps it at one page and hides it from anyone who is past the
    tutorials -- which is most of the people who want a runnable example.
    """
    project_dir = copie_session_default.project_dir

    assert (project_dir / "docs" / "pages" / "examples" / "index.md").is_file(), (
        "the examples gallery is not at pages/examples/index.md"
    )
    assert not (project_dir / "docs" / "pages" / "tutorials" / "examples.md").exists(), (
        "the gallery is still filed under tutorials"
    )

    import yaml

    class _Loader(yaml.SafeLoader):
        pass

    _Loader.add_multi_constructor("!", lambda loader, suffix, node: None)
    # `pymdownx.emoji` names its index and generator as callables, which YAML can
    # only express as `!!python/name:`. That is a global tag, so the `!` handler
    # above does not catch it and a bare SafeLoader raises ConstructorError.
    _Loader.add_multi_constructor("tag:yaml.org,2002:python/name:", lambda loader, suffix, node: suffix)
    nav = yaml.load((project_dir / "mkdocs.yml").read_text(encoding="utf-8"), Loader=_Loader)["nav"]

    top_level = [key for entry in nav if isinstance(entry, dict) for key in entry]
    assert "Examples" in top_level, f"Examples is not a top-level nav section; top level is {top_level}"

    # Nothing may still point at the old path: a nav entry for a file that does
    # not exist is a build error, but a *link* to one is a silent 404.
    stale = [
        p for p in (project_dir / "docs").rglob("*.md") if "tutorials/examples.md" in p.read_text(encoding="utf-8")
    ]
    assert not stale, f"these pages still link the old gallery path: {[str(p) for p in stale]}"


def test_companion_card_precedes_the_install_step(copie_session_default):
    """The notebook is offered before the reader is asked to install anything.

    The card links a marimo playground whose dependencies are declared in the
    notebook itself, so running it is an *alternative* to installing rather than
    something installing unlocks. Offering it after the install step asks the
    reader to do the work first and only then mentions they need not have.

    It still precedes the body: a reader decides whether to run the notebook
    instead of reading the page, so the offer has to arrive before the thing it
    is an alternative to -- it used to sit below "Next Steps" and "Get help",
    past anyone who wanted it.
    """
    page = copie_session_default.project_dir / "docs" / "pages" / "tutorials" / "getting-started.md"
    text = page.read_text(encoding="utf-8")
    assert "<!-- COMPANION_NOTEBOOKS -->" in text, "the seeded tutorial offers no companion notebook"

    marker_at = text.index("<!-- COMPANION_NOTEBOOKS -->")
    install_at = text.index("## Installation")
    body_at = text.index("## Your First Example")

    assert marker_at < install_at, (
        "the notebook is offered only after the reader has installed the package, "
        "when running it in the browser is the alternative to installing"
    )
    assert marker_at < body_at, "the companion offer comes after the page body instead of before it"

    tail = text[text.index("## Next Steps") :] if "## Next Steps" in text else ""
    assert "<!-- COMPANION_NOTEBOOKS -->" not in tail, "the companion offer is stranded in the footer"


def test_misspelled_marker_warns_instead_of_shipping_blank_space(copie_session_default):
    """A marker with the right name and the wrong syntax is reported.

    The per-marker warnings only fire for a *well-formed* marker that resolves to
    nothing. A misspelled one was worse and completely silent: yohou shipped
    `<!-- GALLERY:quickstart -->`, which matches neither the bare nor the
    sectioned pattern, so nothing claimed it, nothing substituted it, and it
    reached the page as a raw comment rendering as blank space. The code that
    would have reported it never saw it.
    """
    project_dir = copie_session_default.project_dir
    markers = _load_markers(project_dir, "unhandled_markers")
    _reset_gallery_caches(markers)
    page = _FakePage("pages/examples/x.md", "pages/examples/x/index.html")

    for marker in ("<!-- GALLERY:quickstart -->", "<!-- SUBPAGES_FOR:x -->", "<!-- EXAMPLES_FOR -->"):
        with caplog_at_warning() as records:
            out = markers._inject(f"# X\n\n{marker}\n", page, config={"repo_url": "https://x/y"})
        assert records, f"{marker} shipped silently; it renders as blank space and nothing says so"
        assert marker in out, f"{marker} was consumed without being understood"

    # An ordinary comment is not in the marker namespace and must stay quiet, or
    # the warning becomes noise and gets ignored -- which is how this started.
    with caplog_at_warning() as records:
        markers._inject("# X\n\n<!-- prettier-ignore -->\n", page, config={"repo_url": "https://x/y"})
    assert not records, "an ordinary HTML comment was flagged as a broken marker"


def test_nested_notebook_playground_link_keeps_its_subdirectory(copie_session_default):
    """The marimo link points at the notebook's real path, not a flat guess.

    The HTML export is flat (docs/examples/<stem>/), so [View] keys on the stem.
    The playground is not: it reconstructs the repo path from this URL, so a URL
    built from the stem alone 404s for every notebook in a subdirectory -- 78 of
    yohou's 79. yohou's pre-de-fork hooks.py kept the subdirectory for exactly
    this reason and the behaviour was lost when the fork was dropped.

    The link is generated rather than authored, so mkdocs never validates it and
    --strict stays green while every one of them is broken.
    """
    project_dir = copie_session_default.project_dir
    nested = project_dir / "examples" / "data-features"
    _write_sectioned_notebook(nested, "nested_demo", title="Nested Demo", section="data-features")
    try:
        markers = _load_markers(project_dir, "nested_playground")
        _reset_gallery_caches(markers)
        item = next(i for i in markers._get_gallery_items(project_dir) if i["stem"] == "nested_demo")

        assert item["open_path"] == "/examples/data-features/nested_demo/edit/", (
            f"playground url is {item['open_path']!r}; it drops the subdirectory and 404s"
        )
        # [View] keys on the stem because the export really is flat.
        assert item["view_path"] == "/examples/nested_demo/"
    finally:
        (nested / "nested_demo.py").unlink()
        nested.rmdir()


def test_duplicate_notebook_stems_are_reported(copie_session_default):
    """Two notebooks sharing a stem export to one page; the loser must not vanish quietly.

    The export dir is keyed on the stem alone, so a second notebook rmtree's the
    first and both gallery cards point at whichever won. yohou has exactly this:
    data-features/signal_processing.py and visualization/signal_processing.py --
    79 View links, 78 unique. The winner is filesystem-order dependent, since the
    export walk is unsorted while the gallery's is sorted.
    """
    project_dir = copie_session_default.project_dir
    a = project_dir / "examples" / "dir_a"
    b = project_dir / "examples" / "dir_b"
    _write_sectioned_notebook(a, "collide", title="A", section="a")
    _write_sectioned_notebook(b, "collide", title="B", section="b")
    try:
        # A fresh build module loads fresh, empty-cache build steps, so prebuild
        # scans the notebooks from scratch -- no gallery-cache reset is needed here,
        # and the caches build.py owns are not the marker gallery caches anyway.
        build = _load_build(project_dir, "stem_collision")
        os.environ["MKDOCS_SKIP_NOTEBOOKS"] = "1"
        with caplog_at_warning() as records:
            build.prebuild()
        assert any("collide" in r for r in records), (
            "two notebooks share a stem and overwrite each other's export, and nothing said so"
        )
    finally:
        os.environ.pop("MKDOCS_SKIP_NOTEBOOKS", None)
        for d in (a, b):
            (d / "collide.py").unlink()
            d.rmdir()


def test_api_table_module_links_point_at_pages_that_exist(copie_session_minimal):
    """Every Module cell links to a module page that is generated, or does not link.

    A root export belongs to no submodule and has no module page. The cell pointed at
    `pages/api/` regardless -- but that is only the directory the generated module
    pages live in; it has no index of its own, so the link 404'd. yohou-nixtla found
    it in production on `BaseNixtlaForecaster`, its one root export.

    Nothing catches this: the cell is raw HTML this hook emits, which mkdocs --strict
    never validates, and only a project that has a root-only export renders such a
    row at all. So the check is that every Module href corresponds to a module the
    hook actually generates a page for -- not that this one string is gone.
    """
    project_dir = copie_session_minimal.project_dir
    pkg = project_dir / "src" / "minimal_project"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "_base.py").write_text(
        '"""Private module."""\n\n\nclass BaseThing:\n    """A public base class in a private module."""\n',
        encoding="utf-8",
    )
    (pkg / "widgets.py").write_text('"""Widgets."""\n\n\nclass Widget:\n    """A widget."""\n', encoding="utf-8")
    (pkg / "__init__.py").write_text(
        '"""Pkg."""\n\nfrom minimal_project._base import BaseThing\n'
        "from minimal_project.widgets import Widget\n\n"
        '__all__ = ["BaseThing", "Widget"]\n',
        encoding="utf-8",
    )
    markers = _load_markers(project_dir, "api_module_links")
    markers._api_pages._SURFACE_CACHE = None
    markers._api_pages._API_NAME_LOOKUP_CACHE = None

    html = markers._build_api_table_html(project_dir, "")
    assert "BaseThing" in html, "no root export rendered; this test would assert nothing"

    generated = {mod["module_name"] for mod in markers._get_submodules(project_dir)}
    assert generated, "no submodules found; this test would assert nothing"

    # The Name cell links too, at pages/api/generated/<qualified>/, and wraps its
    # label in <code>. Only the Module cell does not, which is what separates them.
    module_links = re.findall(r'<td><a href="pages/api/([^"]*)">(?!<code>)', html)
    assert module_links, "no Module cell links at all; the row shape changed and this asserts nothing"
    for target in module_links:
        assert target.strip("/") in generated, (
            f"a Module cell links to pages/api/{target}, which the hook generates no page for; "
            f"it generates pages only for {sorted(generated)}"
        )


def test_root_only_exports_reach_the_api(copie_session_minimal):
    """A symbol exported only from the package root still gets a page and a table row.

    _get_submodules skips every `_`-prefixed name -- right for private modules,
    and it also excludes __init__.py itself. A package that keeps a base class in
    _base.py and re-exports it from the root (an ordinary layout) therefore has a
    public symbol belonging to no submodule, which reached no page and never
    appeared in the table. yohou-nixtla ships 18 names in __all__ and listed 17.
    """
    project_dir = copie_session_minimal.project_dir
    pkg = project_dir / "src" / "minimal_project"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "_base.py").write_text(
        '"""Private module."""\n\n\nclass BaseThing:\n    """A public base class in a private module."""\n',
        encoding="utf-8",
    )
    (pkg / "widgets.py").write_text('"""Widgets."""\n\n\nclass Widget:\n    """A widget."""\n', encoding="utf-8")
    (pkg / "__init__.py").write_text(
        '"""Pkg."""\n\nfrom minimal_project._base import BaseThing\n'
        "from minimal_project.widgets import Widget\n\n"
        '__all__ = ["BaseThing", "Widget"]\n',
        encoding="utf-8",
    )
    markers = _load_markers(project_dir, "root_exports")
    markers._api_pages._SURFACE_CACHE = None
    markers._api_pages._API_NAME_LOOKUP_CACHE = None

    html = markers._build_api_table_html(project_dir, "")
    assert "BaseThing" in html, "a symbol exported only from the package root is missing from the API table"
    assert "minimal_project.BaseThing" in html, "the root export is not published at its public path"

    # A name a real submodule publishes keeps its module path -- root adoption is
    # for the homeless only, not a second home for everything.
    roots = markers._get_root_members(project_dir)
    assert [c["name"] for c in roots["classes"]] == ["BaseThing"], (
        f"root adoption swallowed a symbol that has a module: {[c['name'] for c in roots['classes']]}"
    )

    markers._api_pages._SURFACE_CACHE = None
    markers._api_pages._API_NAME_LOOKUP_CACHE = None
    assert markers._api_pages._get_api_name_lookup(project_dir).get("BaseThing") == "minimal_project.BaseThing", (
        "See Also cannot resolve a root-exported symbol"
    )


def test_subpages_reports_a_sibling_missing_from_the_nav(copie_session_default):
    """An index lists sibling files; the sidebar comes from mkdocs.yml. Disagreement is reported.

    When a nav entry is dropped the index papers over it -- the page is still
    listed and still linked, while vanishing from navigation. mkdocs reports
    not-in-nav pages at INFO, which --strict does not fail on, so nothing else
    says a word. A copier update deleted a real nav entry exactly this way and
    every other guard passed it.
    """
    project_dir = copie_session_default.project_dir
    # Real sibling files in a directory of their own: the index scans its own
    # directory off the filesystem, so the siblings have to exist on disk (both
    # carry an H1 so it is the nav miss, not a missing title, that flags them).
    subdir = project_dir / "docs" / "pages" / "orphan-index"
    subdir.mkdir(parents=True, exist_ok=True)
    (subdir / "configure.md").write_text("# Configure\n\nHow to configure.\n", encoding="utf-8")
    (subdir / "troubleshooting.md").write_text("# Troubleshooting\n\nWhen things break.\n", encoding="utf-8")

    markers = _load_markers(project_dir, "subpages_orphan")
    page = _FakePage("pages/orphan-index/index.md", "pages/orphan-index/index.html")
    # troubleshooting is deliberately absent from the nav.
    config = {
        "nav": [
            {"How-to Guides": ["pages/orphan-index/index.md", {"Configuration": "pages/orphan-index/configure.md"}]}
        ]
    }

    with caplog_at_warning() as records:
        markers._inject("# H\n\n<!-- SUBPAGES -->\n", page, config=config)

    assert any("troubleshooting" in r for r in records), (
        "a page missing from the nav is still listed by the index, and nothing reports it"
    )


def test_gallery_section_marker_renders_only_that_section(copie_session_default):
    """`<!-- GALLERY:section:name -->` renders that section's cards and no others.

    A gallery outgrows one page and splits into per-topic subpages, each asking
    for its own slice. Only the bare `<!-- GALLERY -->` used to be understood,
    so the sectioned form matched nothing, survived as a literal HTML comment,
    and every subpage rendered zero cards while the build stayed green. yohou
    shipped six such pages.
    """
    project_dir = copie_session_default.project_dir
    examples = project_dir / "examples"
    _write_sectioned_notebook(examples, "sec_alpha_one", title="Alpha One", section="alpha")
    _write_sectioned_notebook(examples, "sec_alpha_two", title="Alpha Two", section="alpha")
    _write_sectioned_notebook(examples, "sec_beta_one", title="Beta One", section="beta")

    markers = _load_markers(project_dir, "gallery_section")
    _reset_gallery_caches(markers)

    page = _FakePage("pages/examples/alpha.md", "pages/examples/alpha/index.html")
    out = markers._inject("# Alpha\n\n<!-- GALLERY:section:alpha -->\n", page, config={"repo_url": "https://x/y"})

    assert "<!-- GALLERY:section:alpha -->" not in out, "the sectioned marker was left in the page as a dead comment"
    assert "Alpha One" in out and "Alpha Two" in out, "the section's own notebooks are missing from its page"
    assert "Beta One" not in out, "a notebook from another section leaked into this section's page"


def test_unknown_gallery_section_warns_instead_of_rendering_nothing(copie_session_default, caplog):
    """A section naming no notebook warns, so --strict catches the typo.

    This is the failure mode that hid the bug above: a marker that resolves to
    nothing looks exactly like a page that never had one. Renaming a section and
    missing a page silently empties it, so the miss has to be loud.
    """
    project_dir = copie_session_default.project_dir
    _write_sectioned_notebook(project_dir / "examples", "sec_real", title="Real", section="real")

    markers = _load_markers(project_dir, "gallery_section_unknown")
    _reset_gallery_caches(markers)

    page = _FakePage("pages/examples/typo.md", "pages/examples/typo/index.html")
    with caplog.at_level(logging.WARNING, logger="mkdocs.hooks"):
        markers._inject("# T\n\n<!-- GALLERY:section:typoed -->\n", page, config={"repo_url": "https://x/y"})

    assert "typoed" in caplog.text, "a gallery section matching no notebook rendered silently; --strict cannot catch it"


def test_companion_cards_render_without_a_marker_on_the_page(copie_session_default):
    """A notebook's `companion` is enough on its own to place it on that page.

    The association used to need declaring twice: the notebook naming the page,
    and the page carrying `<!-- COMPANION_NOTEBOOKS -->`. Miss the second and
    the notebook points at a page that never shows it, with nothing reporting
    it. Three sibling repos had 23 notebooks in exactly that state.
    """
    project_dir = copie_session_default.project_dir
    _write_sectioned_notebook(
        project_dir / "examples",
        "companion_no_marker",
        title="Unmarked Companion",
        companion="pages/how-to/configure.md",
    )

    markers = _load_markers(project_dir, "companion_no_marker")
    _reset_gallery_caches(markers)

    page = _FakePage("pages/how-to/configure.md", "pages/how-to/configure/index.html")
    out = markers._inject("# Configure\n\nProse.\n", page, config={"repo_url": "https://x/y"})

    assert "Unmarked Companion" in out, "a notebook naming this page as its companion is nowhere on it"


def test_companion_cards_stay_inside_an_indented_marker(copie_session_default):
    """A marker nested in an admonition keeps its whole replacement nested.

    yohou wraps the marker in `!!! tip "Try it interactively"`. A plain
    str.replace indents only the first line, so the heading stayed in the box
    and the cards fell out at column 0 and closed it -- rendering a tip callout
    whose entire body was a heading repeating its own title. The markdown looked
    correct; only the built HTML showed it.
    """
    project_dir = copie_session_default.project_dir
    _write_sectioned_notebook(
        project_dir / "examples",
        "companion_indented",
        title="Indented Companion",
        companion="pages/how-to/troubleshooting.md",
    )

    markers = _load_markers(project_dir, "companion_indented")
    _reset_gallery_caches(markers)

    page = _FakePage("pages/how-to/troubleshooting.md", "pages/how-to/troubleshooting/index.html")
    source = '# Troubleshooting\n\n!!! tip "Try it interactively"\n    <!-- COMPANION_NOTEBOOKS -->\n'
    out = markers._inject(source, page, config={"repo_url": "https://x/y"})

    assert "Indented Companion" in out, "the companion card vanished"
    body = out.split('!!! tip "Try it interactively"\n', 1)[1]
    for line in body.split("\n"):
        if line.strip():
            assert line.startswith("    "), (
                f"line {line!r} escaped the admonition -- it renders as a sibling, not inside the callout"
            )


def test_index_page_lists_its_subpages(copie_session_default):
    """`<!-- SUBPAGES -->` lists the pages an index introduces, in nav order.

    An index is the page guaranteed to fall behind: adding a page elsewhere is
    what makes it stale, and nothing fails when it does. Every generated index
    used to describe its Diataxis quadrant and then name none of its own pages.
    """
    project_dir = copie_session_default.project_dir
    # Real sibling files, plus a page nested one directory deeper. The index
    # scans its own directory off the filesystem, so the direct children have to
    # exist and the nested one proves the scan does not descend into subsections.
    subdir = project_dir / "docs" / "pages" / "subpages-order"
    (subdir / "nested").mkdir(parents=True, exist_ok=True)
    (subdir / "configure.md").write_text("# How to Configure the Thing\n\nDetails.\n", encoding="utf-8")
    (subdir / "troubleshooting.md").write_text("# Troubleshooting\n\nDetails.\n", encoding="utf-8")
    (subdir / "contribute.md").write_text("# Contributing to the Project\n\nDetails.\n", encoding="utf-8")
    # A nested section owns its own index; the how-to index must not reach into it.
    (subdir / "nested" / "deep.md").write_text("# Deep Nested Page\n\nDetails.\n", encoding="utf-8")

    markers = _load_markers(project_dir, "subpages")
    page = _FakePage("pages/subpages-order/index.md", "pages/subpages-order/index.html")
    # Troubleshooting is deliberately the nav's only entry AND the last of the
    # three by title ("Contributing to..." < "How to Configure..." <
    # "Troubleshooting"). Asserting it leads therefore fails if nav order is
    # ignored -- picking a page that sorts first alphabetically would pass
    # either way and assert nothing.
    config = {
        "nav": [
            {
                "How-to Guides": [
                    "pages/subpages-order/index.md",
                    {"Troubleshooting": "pages/subpages-order/troubleshooting.md"},
                ]
            },
        ]
    }
    out = markers._inject("# How-to\n\n<!-- SUBPAGES -->\n", page, config=config)

    assert "<!-- SUBPAGES -->" not in out, "the marker was left in the page as a dead comment"
    for name, title in (("configure", "Configure"), ("troubleshooting", "Troubleshoot"), ("contribute", "Contribut")):
        assert f"({name}.md)" in out, f"the index does not link its own subpage {name}.md"
        assert title in out, f"the index links {name}.md without naming it ({title!r} missing)"

    assert out.index("(troubleshooting.md)") < out.index("(contribute.md)"), (
        "subpages ignore the configured nav order; the index contradicts the sidebar beside it"
    )
    assert "deep.md" not in out and "Deep Nested" not in out, (
        "the index lists a page from a nested subsection; the scan is not limited to direct children"
    )


def test_subpage_with_no_h1_falls_back_to_its_nav_title(copie_session_default):
    """A page whose H1 only appears after snippet expansion still gets listed.

    `reference/changelog.md` is often a bare `--8<-- "CHANGELOG.md"` include: it
    has no H1 in its own source, growing one only once snippets expand, which is
    after this hook runs. Reading the source alone, the page looks malformed --
    so it was dropped from its own index and the warning failed --strict. The nav
    already names it, and that name is what the sidebar shows.
    """
    project_dir = copie_session_default.project_dir
    docs_dir = project_dir / "docs" / "pages" / "navfallback"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "changelog.md").write_text('--8<-- "CHANGELOG.md"\n', encoding="utf-8")
    (docs_dir / "orphan.md").write_text("Body with no heading and no nav entry.\n", encoding="utf-8")

    markers = _load_markers(project_dir, "subpages_navfallback")
    page = _FakePage("pages/navfallback/index.md", "pages/navfallback/index.html")
    config = {"nav": [{"Reference": [{"Changelog": "pages/navfallback/changelog.md"}]}]}
    out = markers._inject("# Nav\n\n<!-- SUBPAGES -->\n", page, config=config)

    assert "[Changelog](changelog.md)" in out, (
        "a page whose H1 comes from a snippet include was dropped from its own index"
    )
    # An orphan with neither an H1 nor a nav title has no name to show, and
    # inventing one from the filename would hide a genuinely malformed page.
    assert "orphan.md" not in out, "a page with no H1 and no nav title was listed under an invented name"


def test_subpage_index_summarises_each_page_from_its_own_source(copie_session_default):
    """Each listed subpage carries a summary read out of that page.

    A hand-written index re-states every title and blurb, so it drifts from the
    pages the moment one is edited. Reading both from the page itself means
    there is no second copy to drift.
    """
    project_dir = copie_session_default.project_dir
    docs_dir = project_dir / "docs" / "pages" / "subtest"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "frontmatter.md").write_text(
        "---\ndescription: Summary from frontmatter.\n---\n\n# Frontmatter Page\n\nSome other prose.\n",
        encoding="utf-8",
    )
    (docs_dir / "prose.md").write_text(
        "# Prose Page\n\n!!! note\n    An admonition, not the summary.\n\nThe first real paragraph.\n",
        encoding="utf-8",
    )

    markers = _load_markers(project_dir, "subpages_desc")
    page = _FakePage("pages/subtest/index.md", "pages/subtest/index.html")
    out = markers._inject("# Sub\n\n<!-- SUBPAGES -->\n", page, config={})

    assert "Summary from frontmatter." in out, "a frontmatter description was not used as the summary"
    assert "The first real paragraph." in out, "the first prose paragraph was not used as the summary"
    assert "An admonition, not the summary." not in out, "an admonition was mistaken for the page's opening prose"


def test_release_jobs_agree_on_the_version_they_are_shipping(copie_session_default):
    """Both publish-release jobs must read the same version out of the same PR title.

    create-release used a pre-release-aware pattern and pypi-publish a plain one, so
    for `v1.2.0-alpha.1` the first cut a release for v1.2.0-alpha.1 while the second
    went looking for v1.2.0's artifacts and found nothing. Nothing catches it until a
    project ships its first pre-release, and sklearn-optuna carries a local patch to
    the second job -- which means every generated project needs the same patch.

    Runs the patterns rather than comparing them: two different spellings of a correct
    regex are fine, and one spelling used twice is not the property under test.
    """
    workflow = copie_session_default.project_dir / ".github" / "workflows" / "publish-release.yml"
    assert workflow.is_file(), "no publish-release workflow; this test would assert nothing"

    patterns = re.findall(r"grep -oP '([^']+)'", workflow.read_text(encoding="utf-8"))
    assert patterns, "no version-extraction pattern found; this test would assert nothing"

    title = "chore(release): update CHANGELOG.md for v1.2.0-alpha.1"
    extracted = set()
    for pattern in patterns:
        found = re.search(pattern.replace(r"\.", r"\."), title)
        extracted.add(found.group(0) if found else None)

    assert extracted == {"v1.2.0-alpha.1"}, (
        f"the release jobs disagree about which version this PR ships: {extracted}. A job that "
        f"reads v1.2.0 will look for artifacts the job that read v1.2.0-alpha.1 never published"
    )


def test_nightly_tests_the_pythons_the_project_supports(copie):
    """The nightly matrix follows the answers, like every other matrix does.

    nightly.yml hardcoded ["3.11", "3.12", "3.13", "3.14"] while tests.yml derived
    its matrix from min/max_python_version. A project that caps below 3.14 gets a
    nightly job on a Python it does not support: yohou-nixtla excludes 3.14 because
    scipy ships no cp314 wheel, kedro-azureml has capped at 3.13 since its first
    commit. Both had deleted it locally, so the hardcoded list came back as a
    rejected hunk on every update, and the nightly went red on a version nobody
    claimed to support.

    Driven through a real render at a capped max, reproducing yohou-nixtla's answers.
    The default answers happen to end at 3.14, so the hardcoded list matched them
    exactly -- which is why this looked correct for as long as it did.
    """
    import yaml

    result = copie.copy(extra_answers={"min_python_version": "3.11", "max_python_version": "3.13"})
    assert result.exit_code == 0
    project_dir = result.project_dir

    nightly = yaml.safe_load((project_dir / ".github" / "workflows" / "nightly.yml").read_text(encoding="utf-8"))
    tests = yaml.safe_load((project_dir / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8"))

    matrix = nightly["jobs"]["test"]["strategy"]["matrix"]["python-version"]
    assert matrix, "the nightly matrix is empty; this test would assert nothing"

    answers = yaml.safe_load((project_dir / ".copier-answers.yml").read_text(encoding="utf-8"))
    lo, hi = answers["min_python_version"], answers["max_python_version"]
    assert all(lo <= v <= hi for v in matrix), (
        f"nightly runs {matrix}, outside the project's own {lo}-{hi}; it is hardcoded, not derived"
    )
    assert matrix == tests["jobs"]["test-full"]["strategy"]["matrix"]["python-version"], (
        "nightly and the full test suite disagree about which Pythons this project supports"
    )


def test_hooks_docstrings_read_as_instructions(copie_session_default):
    """The docs_build modules survive a docstring linter, because projects lint them.

    The template does not `select = ["D"]`, so a pristine render lints clean and the
    template cannot see this. Projects can: yohou selects D, and v0.25.0's new
    _module_source docstring ("The file backing a submodule...") tripped D401 there,
    reddening a repo for a file the template owns and Tier 1 forbids it editing. The
    repo's only outs were a local ignore that drifts forever, or a fork of a Tier 1
    file. Neither should be the price of a template docstring. hooks.py split into
    _markers.py, build.py and _git_ref.py, so all three are linted.
    """
    build_dir = copie_session_default.project_dir / BUILD_DIR
    modules = [build_dir / name for name in ("_markers.py", "build.py", "_git_ref.py")]
    for module in modules:
        assert module.is_file(), f"no {module.name} generated; this test would assert nothing"

    result = subprocess.run(
        ["uvx", "ruff", "check", "--select", "D401", "--no-cache", *[str(m) for m in modules]],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"a docs_build module fails D401 in any project that lints docstrings:\n{result.stdout}"
    )


def test_the_two_skill_mirrors_stay_byte_identical():
    """.claude/skills and .github/skills are one skill set read by two tools.

    CLAUDE.md tells contributors to edit both, and nothing enforced it. A convention
    that lives only in prose is how this repo lost its logos for months: the guard was
    a heading in a markdown file, and the logos burned underneath it. These two mirrors
    have already drifted in a way that reddened CI, when .github/skills carried an
    MD007 exemption that .claude/skills did not and byte-identical files linted
    differently.

    Tracked files only: the openspec-* skills under .claude/skills are gitignored and
    deliberately unmirrored, so walking the directory would compare a set that is not
    supposed to match.
    """
    root = Path(__file__).parent.parent

    def tracked(rel):
        out = subprocess.run(
            ["git", "ls-files", rel], cwd=root, capture_output=True, text=True, check=True
        ).stdout.split()
        return {path[len(rel) + 1 :]: (root / path).read_bytes() for path in out}

    claude, github = tracked(".claude/skills"), tracked(".github/skills")

    assert claude, "no tracked files under .claude/skills; this test would assert nothing"
    assert set(claude) == set(github), (
        f"the skill mirrors hold different files: only in .claude/skills "
        f"{sorted(set(claude) - set(github))}, only in .github/skills {sorted(set(github) - set(claude))}"
    )
    differing = sorted(name for name, blob in claude.items() if github[name] != blob)
    assert not differing, f"these skills have drifted between the two mirrors: {differing}"


def test_uv_subprocesses_cannot_retarget_the_runner_venv():
    """No `uv` subprocess may resolve its project environment to the venv running the tests.

    nox exports UV_PROJECT_ENVIRONMENT at its session venv, and the 17 `uv`/`uvx nox`
    calls in this suite inherit it, so a `uv sync` meant for a generated project
    re-syncs the runner's venv instead. One such test, with no xdist at all, installed
    test_project and marimo into .nox/test-3-14 and re-resolved Markdown off the
    version uv.lock pins. Under xdist that swap races every other worker: a worker
    importing markdown.extensions.toc while Markdown was being replaced died with
    ModuleNotFoundError, on 3.14 only, reproducibly, for a change that touched no code.

    The effect is the wrong thing to assert on: which worker pollutes first is
    scheduling-dependent, so this pins the cause instead.
    """
    assert os.environ.get("UV_PROJECT_ENVIRONMENT") is None, (
        "UV_PROJECT_ENVIRONMENT points at the test runner's own venv, so any `uv sync` "
        "a test runs inside a generated project will re-resolve the suite's packages "
        "underneath it; conftest must unset it for the session"
    )


def test_docs_warnings_are_fatal_somewhere_automated(copie_session_default):
    """Something that runs on every PR must build the docs with warnings fatal.

    Every marker warning this template emits was decorative until this existed.
    Nothing ran `mkdocs build --strict`: not CI, not nox's default sessions, and
    RTD sets no `fail_on_warning`. So a page that silently lost its whole card
    grid produced a warning in a log nobody reads, and shipped. A warning nothing
    fails on is not a signal.
    """
    project_dir = copie_session_default.project_dir

    noxfile = (project_dir / "noxfile.py").read_text(encoding="utf-8")
    assert "def check_docs" in noxfile, "no nox session builds the docs with warnings fatal"
    session = noxfile[noxfile.index("def check_docs") :]
    session = session[: session.find("@nox.session", 1) if session.find("@nox.session", 1) > 0 else len(session)]
    assert '"-s"' in session, "check_docs builds the docs without strict mode (-s), so warnings stay advisory"
    assert "MKDOCS_SKIP_NOTEBOOKS" in session, (
        "check_docs executes every notebook; that is too slow to run per-PR and it will be dropped from CI"
    )
    # An unpinned session takes the ambient interpreter, which can sit outside
    # requires-python and die in `uv sync` before mkdocs ever runs. CI passes
    # today only because the runner's default happens to be in range.
    assert (
        "python=PYTHON_VERSIONS[0]" in noxfile[noxfile.index("def check_docs") - 60 : noxfile.index("def check_docs")]
    ), "check_docs pins no Python; it runs on whatever the caller happens to have"

    workflow = project_dir / ".github" / "workflows" / "tests.yml"
    assert workflow.is_file(), "no tests workflow"
    assert "nox -s check_docs" in workflow.read_text(encoding="utf-8"), (
        "the strict docs build is never run by CI, so its warnings gate nothing"
    )


def test_seeded_reference_index_lists_the_headingless_changelog(copie_session_default):
    """The template's own seeded pages must survive their own SUBPAGES marker.

    v0.21.0 shipped `<!-- SUBPAGES -->` in reference/index.md next to a
    changelog.md that is a bare `--8<-- "CHANGELOG.md"` with no H1 of its own.
    Every generated project's docs build therefore failed --strict, on the very
    warning added to catch unresolved markers. Driven through the real seeded
    pages and the real mkdocs.yml nav, because the synthetic fixtures all
    happened to give their pages an H1 -- which is exactly how it shipped.
    """
    project_dir = copie_session_default.project_dir
    changelog = project_dir / "docs" / "pages" / "reference" / "changelog.md"
    assert "# " not in changelog.read_text(encoding="utf-8"), (
        "the seeded changelog grew an H1; this test no longer reproduces the shipped bug"
    )

    docs = project_dir / "docs"
    markers = _load_markers(project_dir, "seeded_reference_index")
    page = _FakePage("pages/reference/index.md", "pages/reference/index.html")
    source = (docs / "pages" / "reference" / "index.md").read_text(encoding="utf-8")
    assert "<!-- SUBPAGES -->" in source, "the seeded reference index no longer asks for its subpages"

    # No config passed: the extension reads the real mkdocs.yml nav itself and
    # scans the real reference/ directory for api.md and changelog.md. The other
    # SUBPAGES fixtures give their pages an H1; this one is driven through the real
    # seeded pages and real nav, which is how the headingless-changelog bug shipped.
    with caplog_at_warning() as records:
        out = markers._inject(source, page)

    assert "(changelog.md)" in out, "the seeded reference index drops its own changelog"
    assert not records, f"the seeded docs warn on their own marker, which fails --strict: {records}"


def test_headingless_changelog_still_gets_a_summary(copie_session_default):
    """The changelog row carries a summary like every other row.

    Its title comes from the nav (it has no H1 of its own until snippets expand)
    and its summary has nowhere to come from -- a bare include has no prose to
    derive one from. So it rendered as a bare `- [Changelog](changelog.md)`
    beside siblings that had one. Projects fixed that locally by giving the page
    its own H1, which drifts: changelog.md is Tier 1. Shipping the frontmatter in
    the template is the version that survives an update.
    """
    project_dir = copie_session_default.project_dir
    changelog = project_dir / "docs" / "pages" / "reference" / "changelog.md"
    text = changelog.read_text(encoding="utf-8")

    assert "description:" in text, "the seeded changelog has no description; its index row renders bare"
    assert '--8<-- "CHANGELOG.md"' in text, "the changelog no longer includes the real CHANGELOG"
    assert not re.search(r"^# ", text, re.MULTILINE), (
        "the seeded changelog grew its own H1; it would duplicate the one inside CHANGELOG.md"
    )

    markers = _load_markers(project_dir, "changelog_summary")
    title, description = markers._page_title_and_description(str(changelog))
    assert title is None, "a bare include has no H1 of its own; the nav supplies the title"
    assert description, "the changelog frontmatter yields no summary"


def test_generated_index_pages_introduce_their_subpages(copie_session_default):
    """Every seeded Diataxis index asks for its subpage list.

    Pinning the seed, not just the mechanism: yohou-nixtla's how-to index was
    the template's own index verbatim, so a template that ships the marker on
    none of its indexes leaves every generated project's index bare.
    """
    pages = copie_session_default.project_dir / "docs" / "pages"
    for quadrant in ("tutorials", "how-to", "reference", "explanation"):
        index = pages / quadrant / "index.md"
        assert index.exists(), f"{quadrant} has no index page"
        assert "<!-- SUBPAGES -->" in index.read_text(encoding="utf-8"), (
            f"the {quadrant} index describes its quadrant but never lists its own pages"
        )


def test_claude_md_is_seeded_and_committable(copie_session_default):
    """A generated project gets a project-instructions file it is allowed to commit.

    The template used to ignore six `CLAUDE*` filename variants and ship no
    replacement, so no generated project could record its own invariants anywhere the
    repository could see. Across the fleet that left the knowledge describing seven
    projects living outside all seven of them.
    """
    project = copie_session_default.project_dir
    claude_md = project / "CLAUDE.md"
    assert claude_md.is_file(), "no CLAUDE.md was seeded into the generated project"
    assert claude_md.stat().st_size > 200, "the seeded CLAUDE.md is empty or a stub"

    gitignore = (project / ".gitignore").read_text(encoding="utf-8")
    for variant in ("CLAUDE.md", "CLAUDE_INSTRUCTIONS.md", ".claude.md", "claude-prompt.md"):
        assert not re.search(rf"^{re.escape(variant)}$", gitignore, re.MULTILINE), (
            f"{variant} is still ignored, so a project cannot commit its own instructions"
        )


def test_claude_md_is_registered_as_seed_once():
    """`CLAUDE.md` must be in `_skip_if_exists`, or an update reverts a project's edits.

    Copier applies an update as a diff against the *template's* copy. Once a project
    has rewritten this file wholesale, one shifted line rejects the whole hunk and the
    page reverts to the stub, with the project's content left in a `.rej` nobody
    reads. That is not hypothetical: v0.22.0 did exactly this to five projects'
    getting-started.md from a whitespace-only change. `_skip_if_exists` is the only
    thing copier itself honours here; the update skill's classification is advisory.
    """
    config = yaml.safe_load(Path("copier.yml").read_text(encoding="utf-8"))
    assert "CLAUDE.md" in config["_skip_if_exists"], (
        "CLAUDE.md is shipped but not seed-once; a template update would revert every project's own instructions"
    )


def test_claude_md_survives_a_later_template_run(tmp_path):
    """A project's rewritten CLAUDE.md is not overwritten by a later template run.

    The behavioural half of what test_claude_md_is_registered_as_seed_once only
    documents, and the same shape as the branding test above. Registering a file in
    `_skip_if_exists` is a claim; re-running the template is what checks it.

    This matters because an attempt to reproduce the original v0.22.0 loss through
    `copier update` did not reproduce it: copier's three-way merge preserved a
    rewritten CLAUDE.md even with the guard removed, for both a wholly-rewritten file
    and a file still resembling the template's with one line changed. So the guard's
    necessity is not demonstrated by that route. What IS demonstrable, and what this
    pins, is that an overwriting run leaves the project's version alone -- and the
    control below shows such a run genuinely does overwrite anything unguarded, so the
    survival is the guard's doing and not the run being a no-op.
    """
    from copier import run_copy

    answers = {
        "project_name": "Seeded",
        "project_slug": "seeded",
        "package_name": "seeded",
        "description": "d",
        "author_name": "A",
        "author_email": "a@b.c",
        "github_username": "u",
        "version": "0.1.0",
        "min_python_version": "3.11",
        "max_python_version": "3.14",
        "license": "MIT",
        "include_actions": True,
        "include_examples": True,
    }
    template_dir = str(Path(__file__).parent.parent)
    project = tmp_path / "seeded-project"
    run_copy(template_dir, str(project), data=answers, defaults=True, overwrite=True, unsafe=True, vcs_ref="HEAD")

    claude_md = project / "CLAUDE.md"
    assert claude_md.is_file(), "the template must seed CLAUDE.md so a new project has something to start from"
    owned = "# Seeded\n\nPROJECT-OWNED CONTENT THAT MUST SURVIVE.\n"
    claude_md.write_text(owned, encoding="utf-8")

    # The control: a file the template owns and does NOT guard. If this survives too,
    # the run overwrote nothing and the assertion below would prove nothing.
    readme = project / "README.md"
    readme.write_text("CLOBBER ME\n", encoding="utf-8")

    run_copy(template_dir, str(project), data=answers, defaults=True, overwrite=True, unsafe=True, vcs_ref="HEAD")

    assert readme.read_text(encoding="utf-8") != "CLOBBER ME\n", (
        "the control file was not overwritten, so this run proves nothing about the guard"
    )
    assert claude_md.read_text(encoding="utf-8") == owned, (
        "the template overwrote the project's own CLAUDE.md; _skip_if_exists is not holding"
    )
