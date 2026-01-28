# Quick Start

Get your Python package up and running in 5 minutes.

## Prerequisites

Install [uv](https://docs.astral.sh/uv/) for fast package management:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Create Your Package

```bash
uvx copier copy gh:stateful-y/python-package-copier-template my-package
```

Answer the prompts about your project (name, author, license, etc.). See [copier.yml](https://github.com/stateful-y/python-package-copier-template/blob/main/copier.yml) for all options.

## Initialize Your Project

```bash
cd my-package

# Install dependencies
uv sync --group dev

# Set up pre-commit hooks
uv run pre-commit install
```

## Verify Setup

```bash
# Run tests
uv run pytest

# View documentation
uvx nox -s serve_docs
```

## Push to GitHub

```bash
git init
git add .
git commit -m "feat: initial project setup"

# Create repo on GitHub, then:
git remote add origin https://github.com/yourusername/my-package.git
git branch -M main
git push -u origin main
```

## Setup CI/CD

### Codecov (Coverage Reporting)

1. Sign up at [codecov.io](https://codecov.io/)
2. Add your repository
3. Go to Settings → Copy the upload token
4. In GitHub: Settings → Secrets and variables → Actions → New secret
5. Add `CODECOV_TOKEN` with your token

### PyPI Publishing (Automated Releases)

1. Create account at [pypi.org](https://pypi.org/account/register/)
2. Go to Account settings → API tokens → Add API token
3. Token name: `my-package`, Scope: Entire account
4. Copy the token (starts with `pypi-`)
5. In GitHub: Settings → Secrets and variables → Actions → New secret
6. Add `PYPI_API_TOKEN` with your token

Release your package by pushing a version tag:

```bash
git tag v0.1.0
git push origin v0.1.0
```

This triggers: changelog generation → PyPI upload → GitHub release creation.

### ReadTheDocs (Documentation)

1. Go to [readthedocs.org](https://readthedocs.org/accounts/signup/)
2. Sign in with GitHub
3. Click "Import a Project"
4. Select your repository
5. Click "Build version" - your docs are live!

Documentation builds automatically on every push to main.

## Next Steps

- **[Reference Guide](reference.md)** - Full command reference, CI/CD setup, testing guide
- **[Contributing](contributing.md)** - For template developers
- **[GitHub Template](https://github.com/stateful-y/python-package-copier-template)** - Source code and issues
