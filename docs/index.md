# Python Package Copier Template

A modern, production-ready Python package template using [Copier](https://copier.readthedocs.io/).

## Overview

This Copier template creates Python packages with best practices, modern tooling, and comprehensive CI/CD pipelines already configured. Save hours of initial setup time and focus on writing code.

## Features

- **Modern tooling**: [uv](https://github.com/astral-sh/uv) for 10-100x faster package management
- **Code quality**: [ruff](https://github.com/astral-sh/ruff) for ultra-fast linting and formatting
- **Type checking**: [ty](https://github.com/astral-sh/ty) with strict mode enabled
- **Testing**: [pytest](https://pytest.org/) with coverage reporting via covdefaults
- **Documentation**: [MkDocs](https://www.mkdocs.org/) with Material theme and ReadTheDocs integration
- **CI/CD**: GitHub Actions for automated testing, linting, and PyPI releases
- **Automated releases**: Tag-based workflow with [git-cliff](https://git-cliff.org/) changelog generation, automatic PyPI publishing, and GitHub release creation with changelog PR workflow
- **Coverage reporting**: Codecov integration for test coverage tracking
- **Pre-commit hooks**: Automated code quality checks on every commit
- **Build system**: Modern PEP 517/518 compliant build with hatchling + hatch-vcs
- **Automation**: [nox](https://nox.thea.codes/) for multi-environment testing and [just](https://github.com/casey/just) for task running
- **Versioning**: Semantic versioning derived from Git tags

## Quick Links

- [Quick Start](quickstart.md) - Get started in minutes
- [Reference](reference.md) - Technology stack and generated project structure
- [Contributing](contributing.md) - Contributing to the template
