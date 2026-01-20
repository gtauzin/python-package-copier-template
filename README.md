# Python Package Copier Template

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![Tests](https://github.com/gtauzin/python-package-copier-template/workflows/Tests/badge.svg)](https://github.com/gtauzin/python-package-copier-template/actions/workflows/tests.yml)
[![Documentation](https://readthedocs.org/projects/python-package-copier-template/badge/?version=latest)](https://python-package-copier-template.readthedocs.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A modern, production-ready Python package template using [Copier](https://copier.readthedocs.io/). Save hours of setup time with best practices, modern tooling (uv, ruff, ty, pytest), and comprehensive CI/CD pipelines already configured.

📚 **[Full Documentation](https://python-package-copier-template.readthedocs.io/)**

## Quick Start

```bash
# Create a new package
uvx copier copy gh:gtauzin/python-package-copier-template my-package

# Initialize
cd my-package
uv sync --group dev
uv run pytest
```

## Features

- Fast package management with [uv](https://github.com/astral-sh/uv)
- Code formatting and linting with [ruff](https://github.com/astral-sh/ruff)
- Type checking with [ty](https://github.com/astral-sh/ty)
- Testing with [pytest](https://pytest.org/) and coverage via Codecov
- Documentation with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/)
- CI/CD with GitHub Actions
- Pre-commit hooks for code quality
- Modern PEP 517/518 build with hatchling
- Task automation with nox and just

## Template Development

```bash
# Clone and setup
git clone https://github.com/gtauzin/python-package-copier-template.git
cd python-package-copier-template
uv sync --group test --group docs

# Test
just test

# Documentation
just serve
```

See the [Contributing Guide](https://python-package-copier-template.readthedocs.io/contributing/) for details.

## License

MIT License - see the [LICENSE](LICENSE) file for details.
