# Python Package Copier Template - AI Coding Agent Instructions

## Project Overview

This is a **Copier template project** that generates modern Python packages. You're working on the *template itself*, not a generated project. The `template/` directory contains Jinja2 templates (`.jinja` files) that copier renders when creating new Python packages.

**Key distinction**:
- Changes to root files (`noxfile.py`, `pyproject.toml`) affect this template repository
- Changes to `template/*.jinja` files affect generated projects
- Root `pyproject.toml` only needs test/docs dependencies; generated projects in `template/pyproject.toml.jinja` define the full Python package setup

## Template Architecture

### Directory Structure
- **`template/`**: Jinja2 templates for generated projects
  - All files ending in `.jinja` are rendered by Copier
  - Variable substitution uses `{{ variable_name }}` syntax
  - Non-.jinja files are copied verbatim
- **`copier.yml`**: Template configuration defining user prompts and defaults
- **Root files**: Development setup for the template repository itself

### Template Variables
Variables defined in `copier.yml` are used in `.jinja` files:
- `{{ package_name }}`: Python import name (underscores)
- `{{ project_slug }}`: Repository/URL name (hyphens)
- `{{ project_name }}`: Human-readable display name
- `{{ python_version }}`: Minimum Python version (e.g., "3.10")
- `{{ author_name }}`, `{{ author_email }}`: Maintainer info
- `{{ github_username }}`: GitHub org/user for URLs

See `template/pyproject.toml.jinja` and `template/noxfile.py.jinja` for usage examples.

## Developer Workflows

### Testing Template Changes
```bash
# Test template generation (uses tests/conftest.py fixture)
uv run pytest -v

# Or use nox for multi-version testing
uvx nox -s tests
```

The test suite uses copier's `run_copy()` to generate actual projects in temp directories (`tmp_path`), then validates:
- File/directory structure matches expectations
- Generated content includes required tools and configurations
- Multiple license options generate correctly
- GitHub workflows are properly templated with uv and ty

**Important**: `CopierTestFixture` (in [tests/conftest.py](tests/conftest.py)) provides default answers for all prompts. Tests use `result.project_dir` to access the generated temporary project. Assertions should verify *generated* project content, not template source files.

**Common test pattern**:
```python
def test_feature(copie):
    result = copie.copy(extra_answers={"license": "MIT"})
    assert (result.project_dir / "LICENSE").is_file()
    content = (result.project_dir / "pyproject.toml").read_text()
    assert "expected_string" in content
```

See [tests/test_template.py](tests/test_template.py) for assertion patterns.

### Code Quality
```bash
# Format and lint (pre-commit hooks)
uvx nox -s fix

# Check without fixing
just check

# Direct ruff usage
uv run ruff check tests/
```

### Documentation
```bash
# Build docs
uvx nox -s build_docs

# Live preview at localhost:8080
uvx nox -s serve_docs
# or: just serve
```

## Project-Specific Conventions

### Tooling Stack
Generated projects use this opinionated modern Python stack:
- **uv**: Fast dependency management (replaces pip/poetry)
- **hatchling + hatch-vcs**: Build backend with VCS-based versioning
- **ruff**: Combined linter + formatter (replaces black, isort, flake8)
- **ty**: Type checker (not mypy/pyright)
- **nox**: Task runner with uv backend (installed globally via `uvx nox`, NOT a project dependency)
- **pytest**: Testing with coverage via `covdefaults`

**Critical**: nox is NOT listed in `template/pyproject.toml.jinja` dependencies. It's installed system-wide with `uv tool install nox` or invoked via `uvx nox`. Generated projects' GitHub workflows use `uv tool install nox` for CI. Do not add nox to dependency groups when testing if it appears in generated projects.

### Nox Sessions
Both template and generated projects use nox with `uv` backend:
- Sessions install deps via `session.run_install("uv", "sync", ...)`
- Set `UV_PROJECT_ENVIRONMENT` env var to point to nox's virtualenv
- Default sessions defined in `nox.options.sessions`

Example from `template/noxfile.py.jinja`:
```python
nox.options.default_venv_backend = "uv|virtualenv"
session.run_install("uv", "sync", "--group", "dev",
    env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location})
```

### Justfile Commands
The `justfile` provides convenient shortcuts:
- `just test`: Quick test run with uv
- `just fix`: Run pre-commit hooks (formatting/linting)
- `just serve`: Documentation preview
- Commands delegate to either `uv run` (simple) or `uvx nox` (complex)

### Pre-commit Configuration
Generated projects include pre-commit hooks for:
- Ruff formatting and linting (auto-fix enabled)
- Interrogate (docstring coverage, excludes tests/)
- Type checking with ty (src/ only, via local hook)
- Standard checks (trailing whitespace, YAML/TOML validation)

Note: `ty` runs as a local hook requiring system installation.

## Common Patterns

### Adding Template Variables
1. Add question to `copier.yml` with type, help text, default
2. Use `{{ variable_name }}` in `.jinja` files
3. Update `tests/conftest.py` fixture if adding required fields
4. Test generation with `pytest`

### Modifying Generated Structure
When adding files to generated projects:
- Create in `template/` with `.jinja` suffix if needs variable substitution
- Update `tests/test_template.py` expected files/dirs lists
- Document in `docs/structure.md` (if exists)

### Version Constraints
- Template itself: `requires-python = ">=3.10"` (in root `pyproject.toml`)
- Generated projects: Uses `{{ python_version }}` from copier prompt
- Generated `noxfile.py.jinja` tests against multiple Python versions (3.10-3.14)

## Integration Points

### GitHub Actions
Generated projects include workflows (if `include_github_actions: true`):
- `tests.yml`: Run nox tests on push/PR with matrix strategy across Python versions
- `publish-release.yml`: Build and publish to PyPI, create GitHub release on tag push
- `changelog.yml`: Automated changelog generation with git-cliff on version tags
- `nightly.yml`: Scheduled dependency testing against latest package versions
- `dependabot.yml`: Automated dependency updates

### Changelog & Versioning
Generated projects use automated changelog and version management:
- **git-cliff**: Generates changelogs from conventional commits (config in `.git-cliff.toml.jinja`)
- **commitizen**: Enforces conventional commit messages via pre-commit hook
- **hatch-vcs**: VCS-based versioning (reads from git tags, writes to `_version.py`)
- Changelog format follows "Keep a Changelog" style
- On tag push, `changelog.yml` workflow auto-generates CHANGELOG.md

Example commit format: `feat: add new feature` or `fix: resolve bug`

### ReadTheDocs
- Always included via `.readthedocs.yml.jinja`
- Uses mkdocs-material theme
- Builds with uv for fast installs

### Copier Updates
Generated projects include `.copier-answers.yml` for template updates:
```bash
copier update --trust
```

## Critical Files

- **`copier.yml`**: All template configuration and user prompts
- **`tests/conftest.py`**: Copier test fixture with default answers
- **`template/pyproject.toml.jinja`**: Core dependency and tool config for generated projects
- **`template/noxfile.py.jinja`**: Task automation for generated projects
- **`template/.pre-commit-config.yaml.jinja`**: Code quality enforcement

## Development Setup

```bash
# Initial setup
uv sync --group test --group docs

# Quick validation
just all  # runs check + test

# Before committing
just pre-commit
```

Avoid `pip install` or `python -m venv` - this project uses uv exclusively.
