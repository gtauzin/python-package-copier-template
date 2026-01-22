# Reference

## Technology Stack

| Category | Tool | Purpose |
|----------|------|---------|
| **Build** | hatchling | Modern build backend |
| **Build** | hatch-vcs | Git-based versioning |
| **Package Manager** | uv | Fast dependency management |
| **Formatter** | ruff | Code formatting |
| **Linter** | ruff | Code linting |
| **Type Checker** | ty | Static type checking |
| **Test Framework** | pytest | Unit testing |
| **Test Automation** | nox | Multi-environment testing |
| **Coverage** | pytest-cov | Code coverage |
| **Pre-commit** | pre-commit | Git hooks |
| **Documentation** | MkDocs | Static site generator |
| **Doc Theme** | Material | Beautiful theme |
| **API Docs** | mkdocstrings | Docstring extraction |
| **Task Runner** | just | Command automation |
| **CI/CD** | GitHub Actions | Automation platform |
| **Coverage Reporting** | Codecov | Test coverage tracking |
| **Dependency Updates** | Dependabot | Automated updates |

## Generated Project Structure

```
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
│   ├── dependabot.yml
│   └── pull_request_template.md
├── docs/
│   ├── index.md
│   ├── getting-started.md
│   ├── user-guide.md
│   ├── api-reference.md
│   └── contributing.md
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
└── README.md
```

## GitHub Actions Workflows

### tests.yml - Continuous Integration

Runs on every push and pull request:
- Tests across Python 3.10, 3.11, 3.12, 3.13, 3.14
- Tests on Ubuntu, Windows, and macOS
- Matrix of 15 combinations
- **Uploads coverage to Codecov** (requires `CODECOV_TOKEN` secret)
- **Uploads test results to Codecov**

### pr-title.yml - Pull Request Title Validation

Runs on pull requests to main:
- Validates PR title follows [Conventional Commits](https://www.conventionalcommits.org/) format
- Required types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`
- Ensures consistency with changelog generation (git-cliff)
- Helps maintain clean commit history

### changelog.yml - Automated Changelog

Triggers on version tags (`v*.*.*`):
- Generates changelog from conventional commits using git-cliff
- Creates a **Pull Request** with updated `CHANGELOG.md`
- Runs pre-commit hooks on generated changelog
- Builds and validates package distributions
- Publishes to PyPI automatically (requires trusted publishing or `PYPI_API_TOKEN` secret)
- **Requires** `RELEASE_AUTOMATION_TOKEN` secret for PR creation

### publish-release.yml - Automated GitHub Releases

Triggers when changelog PR is merged:
- Detects merged PRs with the `changelog` label
- Extracts version from PR title
- Downloads build artifacts from changelog workflow
- Creates a **GitHub Release** with:
  - Release notes extracted from `CHANGELOG.md`
  - Package distributions attached (wheel + sdist)
  - Automatic tagging

**Complete release flow**: Tag push → Changelog PR → PyPI publish → Merge PR → GitHub Release

### nightly.yml - Proactive Monitoring

Runs daily on schedule:
- Tests against latest dependencies
- **Uploads coverage to Codecov** (requires `CODECOV_TOKEN` secret)
- Creates GitHub issue on failure

## Key Configuration Files

### pyproject.toml

Central configuration containing:
- Project metadata (name, version, description)
- Dependencies and dependency groups
- Build system configuration (hatchling + hatch-vcs)
- Tool configurations (ruff, pytest, coverage)

### noxfile.py

Task automation sessions:
- `tests` - Run tests on Python 3.10-3.14
- `tests_coverage` - Run tests with coverage
- `fix` - Auto-format and fix code issues
- `lint` - Check code quality
- `build_docs` - Build documentation
- `serve_docs` - Serve docs at localhost:8080

### mkdocs.yml

Documentation configuration:
- Material theme
- Search functionality
- API documentation via mkdocstrings

### .pre-commit-config.yaml

Pre-commit hooks:
- Ruff formatter and linter
- Type checking with ty
- YAML/TOML validation
- Docstring coverage checks
- Trailing whitespace and EOF fixes

### .readthedocs.yml

ReadTheDocs configuration:
- Automatic documentation builds
- Version management
- uv for fast installs

## Updating Projects Created from This Template

Projects generated from this template include a `.copier-answers.yml` file that tracks the template version and source. This enables you to pull in template updates as they are released.

### Update Command

To update your generated project with the latest template changes:

```bash
copier update --trust
```

Run this from your project's root directory.

### What Gets Updated

Copier will:
1. Pull the latest template changes from `gh:gtauzin/python-package-copier-template`
2. Show you a diff of changes
3. Prompt for any new configuration questions
4. Apply updates while preserving your modifications

### Handling Conflicts

If you've modified files that the template also changed:
- Copier will show you conflicts
- Use `--conflict` flag to control merge strategy:
  - `copier update --trust --conflict inline` - Inline conflict markers (default)
  - `copier update --trust --conflict rej` - Create `.rej` files for conflicts

### Version Pinning

To update to a specific template version:

```bash
copier update --trust --vcs-ref=v1.2.0
```

Or update to a specific commit:

```bash
copier update --trust --vcs-ref=abc123
```

### Checking Current Version

View your current template version:

```bash
cat .copier-answers.yml
```

The `_commit` field shows the template commit your project was generated from.
