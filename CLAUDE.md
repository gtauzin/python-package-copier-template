# Python Package Copier

## Project Overview
This is a **Copier template** for generating modern Python packages.
- **Root**: configuration for *this* repo (tests, docs for the template).
- **`template/`**: Jinja2 source files for *generated* projects. Changes here affect output.
- **`copier.yml`**: Defines user prompts/variables (e.g., `{{ package_name }}`).

## Critical Workflows
- **Package Management**: Uses **uv** exclusively. No `pip` or `venv`.
- **Task Running**: `uvx nox` (global install) or `just`.
- **Testing**:
    - **Fast (Unit)**: `just test-fast` (Checks file structure/content generation).
    - **Slow (Integration)**: `just test-slow` (Runs `nox` *inside* generated projects).
    - **Fixture**: Use `copie` fixture (wraps `CopierTestFixture`) in `tests/conftest.py`.
- **Lint/Fix**: `just fix` (Runs `uv run prek`; prek and the lint tools are all pinned by `uv.lock`).

## Architecture & Patterns
- **Template Files**: End in `.jinja`. Variables: `{{ min_python_version }}`.
- **Conditional Dirs**: directory names like `{% if include_examples %}examples{% endif %}/`.
- **Tech Stack (Target)**: `uv`, `hatchling` (build), `ruff` (linter), `ty` (types), `nox` (tasks).
- **Nox Configuration**:
    - **Root**: `noxfile.py` tests the template.
    - **Template**: `template/noxfile.py.jinja` tests the *generated* package.
    - **Important**: `nox` is NOT a project dependency; it's run via `uvx`.

## Development Rules
1. **Adding Features**:
    - Update `copier.yml` (prompts).
    - Update `template/` files.
    - Update `tests/conftest.py` default answers.
    - Add test case in `tests/test_template.py`.
2. **Dependencies**:
    - Root `pyproject.toml`: Only for testing the template (copier, pytest).
    - Template `pyproject.toml.jinja`: Definition for generated packages.
3. **CI/CD**:
    - Template uses `tests.yml` (fast/full split).
    - Generated projects get `tests.yml`, `changelog.yml` (git-cliff), `publish-release.yml`.

## Common Commands
```bash
just test-fast        # Run unit tests (fast feedback)
just fix              # Auto-format and lint
just serve            # Preview docs
uv sync --group test  # Install test deps
```

## Skills
Skills in `.claude/skills/` mirror `.github/skills/` (kept for GitHub Copilot). Edit both when changing one. This is now enforced: `tests/test_repo_workflows.py` asserts the two trees track the same files and are byte-identical. The check is scoped to files git tracks, because both trees deliberately ignore `openspec-*` skills as tool state the openspec CLI writes into whichever copy it likes.

Skills that ship to *generated* projects live in `template/.github/skills/` and are a separate set — they are not mirrored here. Within `template/`, the `.github/skills/` and `.claude/skills/` copies must stay byte-identical. Note that `test_claude_skills_generated` checks only that both trees carry the same skill *names* and that each has a `SKILL.md`; two copies whose contents diverged would still pass it.

`polish-changelog` is **not on `main`**. Its content lives on the unmerged branch `feat/changelog-polish-skill` and in `~/.claude/skills/polish-changelog/` (global, out-of-repo, updated by hand), so it is available in every repo but tracked in none. The `changelog-polish` capability spec under `openspec/specs/` is canonical and describes behaviour the repo does not currently ship. Either land that branch or treat the global copy as the only source.
