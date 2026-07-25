# Project Structure

## Generated Project Tree

```text
my-package/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.yml
│   │   ├── feature_request.yml
│   │   └── config.yml
│   ├── workflows/
│   │   ├── tests.yml
│   │   ├── pr-title.yml
│   │   ├── changelog.yml
│   │   ├── publish-release.yml
│   │   └── nightly.yml
│   └── pull_request_template.md
├── docs/
│   ├── index.md
│   ├── tutorials/
│   │   ├── getting-started.md
│   │   └── examples.md
│   ├── how-to/
│   │   ├── configure.md
│   │   └── contribute.md
│   ├── reference/
│   │   └── api.md
│   └── explanation/
│       └── concepts.md
├── src/
│   └── package_name/
│       ├── __init__.py
│       ├── example.py
│       └── py.typed
├── tests/
│   ├── conftest.py
│   └── test_example.py
├── .editorconfig
├── .gitignore
├── .pre-commit-config.yaml
├── .readthedocs.yml
├── CHANGELOG.md
├── CONTRIBUTING.md
├── justfile
├── LICENSE
├── mkdocs.yml
├── noxfile.py
├── pyproject.toml
├── renovate.json
└── README.md
```

## File Roles

### Root Files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Project metadata, dependencies, build config, tool settings |
| `noxfile.py` | Test automation sessions (multi-version testing, linting, docs) |
| `justfile` | Convenience commands wrapping nox sessions |
| `mkdocs.yml` | Documentation site configuration |
| `.pre-commit-config.yaml` | Git hook configuration for code quality |
| `.readthedocs.yml` | ReadTheDocs build configuration |
| `.editorconfig` | Editor-neutral formatting settings |
| `LICENSE` | Project license (based on `license` template variable) |
| `CHANGELOG.md` | Auto-generated changelog from conventional commits |
| `CONTRIBUTING.md` | Quick-start contributing guide (redirects to full docs) |
| `README.md` | Project overview, badges, installation instructions |

### Source Code (`src/`)

The project uses a **src layout** - all package code lives under `src/<package_name>/`:

| File | Purpose |
|------|---------|
| `__init__.py` | Package initialization with version import |
| `hello.py` | Example module with a sample function |
| `py.typed` | PEP 561 marker for type checker support |

### Tests (`tests/`)

| File | Purpose |
|------|---------|
| `conftest.py` | Shared fixtures for pytest |
| `test_hello.py` | Example test file |
| `test_examples.py` | Marimo notebook tests (if `include_examples=true`) |

### GitHub Configuration (`.github/`)

| File | Purpose |
|------|---------|
| `workflows/tests.yml` | CI testing pipeline |
| `workflows/pr-title.yml` | PR title conventional commit validation |
| `workflows/changelog.yml` | Changelog generation on version tags |
| `workflows/publish-release.yml` | GitHub Release + PyPI publishing |
| `workflows/nightly.yml` | Daily dependency testing |
| `renovate.json` | Automated dependency update PRs (Renovate; self-contained, or a stub extending a shared preset) |
| `pull_request_template.md` | PR description template |
| `ISSUE_TEMPLATE/` | Bug report and feature request templates |

### Documentation (`docs/`)

| File | Purpose |
|------|---------|
| `index.md` | Documentation homepage |
| `tutorials/getting-started.md` | Installation and first steps (tutorial) |
| `tutorials/examples.md` | Interactive examples gallery (if `include_examples=true`) |
| `how-to/configure.md` | Configuration guide scaffold |
| `how-to/contribute.md` | Full contributing guidelines |
| `reference/api.md` | Auto-generated API reference |
| `explanation/concepts.md` | Core concepts and architecture |

## Conditional Files

Some files are only generated based on template variable choices:

| Condition | Files Generated |
|-----------|----------------|
| `include_actions=true` | `.github/workflows/*` |
| `include_examples=true` | `examples/hello.py`, `tests/test_examples.py`, `docs/pages/tutorials/examples.md`, `docs/stylesheets/gallery.css` |
