# Quick Start

Get started with the Python Package Copier Template in minutes.

## Prerequisites

```bash
# Install uv (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Create a New Package

```bash
# Using uvx (recommended - no installation needed)
uvx copier copy gh:gtauzin/python-package-copier-template my-package

# Or using installed copier
copier copy gh:gtauzin/python-package-copier-template my-package
```

## Answer the Prompts

Copier will ask questions to customize your project. See [copier.yml](https://github.com/gtauzin/python-package-copier-template/blob/main/copier.yml) for all available options.

## Initialize Your Project

```bash
cd my-package

# Install dependencies
uv sync --group dev

# Install pre-commit hooks
uv run pre-commit install

# Run tests
uv run pytest

# Serve documentation
uvx nox -s serve_docs
```

## Create GitHub Repository

```bash
git init
git add .
git commit -m "feat: initial project setup from template"

# Create repository on GitHub, then:
git remote add origin https://github.com/yourusername/my-package.git
git branch -M main
git push -u origin main
```

## Enable CI/CD Features

### Codecov (Coverage Reporting)

1. Sign up at [codecov.io](https://codecov.io/)
2. Add your repository
3. Get your Codecov token
4. Add `CODECOV_TOKEN` secret to GitHub repository settings

### PyPI Publishing (Automated Releases)

1. Create PyPI API token at [pypi.org/manage/account/token](https://pypi.org/manage/account/token/)
2. Add as `PYPI_API_TOKEN` secret in GitHub repository settings
3. Push a tag to trigger release:
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```

### ReadTheDocs (Documentation Hosting)

1. Go to [readthedocs.org](https://readthedocs.org/)
2. Import your GitHub repository
3. Documentation builds automatically on push

## For Template Users

Use this section if you want to **create a new Python package** using the template.

### 1. Install Prerequisites

```bash
# Install uv (recommended for fast package management)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Alternatively, install copier globally
pip install copier
```

### 2. Create Your Project

```bash
# Using uvx (recommended - no installation needed)
uvx copier copy gh:gtauzin/python-package-copier-template my-awesome-package

# Or using installed copier
copier copy gh:gtauzin/python-package-copier-template my-awesome-package
```

### 3. Answer the Prompts

Copier will ask questions to customize your project:

```
🎤 Name of the new project (e.g., 'My Awesome Package')
   My Awesome Package

🎤 Python package name (e.g., 'my_awesome_package')
   my_awesome_package

🎤 Author or maintainer name
   Your Name

🎤 Author or maintainer email
   your.email@example.com

[... continue with other prompts ...]
```

For detailed explanations of each prompt, see the [Usage Guide](usage.md).

### 4. Initialize Your Project

```bash
cd my-awesome-package

# Install dependencies
uv sync --group dev

# Install pre-commit hooks
uv run pre-commit install

# Run tests to verify setup
uv run pytest

# View documentation locally
uvx nox -s serve_docs
```

### 5. Create GitHub Repository

```bash
# Initialize git
git init
git add .
git commit -m "feat: initial project setup from template"

# Create repository on GitHub via web interface, then:
git remote add origin https://github.com/yourusername/my-awesome-package.git
git branch -M main
git push -u origin main
```

### Next Steps for Users

- Read the [Usage Guide](usage.md) for template customization options
- Review [Generated Project Overview](generated-project.md) for project structure
- Explore [Features](features.md) for complete capability list

---

## For Template Developers

Use this section if you want to **modify or contribute to the template itself**.

### Setup Template Development Environment

```bash
# Clone the template repository
git clone https://github.com/gtauzin/python-package-copier-template.git
cd python-package-copier-template

# Install dependencies
uv sync --group test --group docs
```

### Test Template Changes

```bash
# Run automated tests
uv run pytest -v

# Or use just
just test

# Generate a test project manually
uvx copier copy . /tmp/test-project --trust

# Verify the generated project works
cd /tmp/test-project
uv sync --group dev
uv run pytest
```

### Common Development Tasks

```bash
# Format and lint template code
just fix

# Build template documentation
just docs

# Serve template documentation locally (http://localhost:8080)
just serve

# Run all quality checks
just all
```

### Modify Template Files

Template files are in the `template/` directory. Edit template files with your preferred editor and test your changes:

```bash

uvx copier copy . /tmp/test-project --trust
```

### Next Steps for Developers

- Read the [Development Guide](development.md) for comprehensive instructions
- Review [Template Structure](structure.md) to understand architecture
- Check [Features](features.md) to see what the template provides

---

## Common Commands Reference

### For Generated Projects

```bash
# Development
uv sync --group dev       # Install dependencies
uv run pytest             # Run tests
uv run pytest --cov       # Run tests with coverage
uv run ruff check src     # Lint code
uv run ruff format src    # Format code

# Using Nox
uvx nox -l                    # List available sessions
uvx nox -s tests              # Run tests
uvx nox -s fix                # Fix code style
uvx nox -s build_docs         # Build documentation
uvx nox -s serve_docs         # Serve documentation

# Using Just
just test                 # Quick test
just format               # Format code
just docs                 # Build docs
just serve                # Serve docs locally
just all                  # Run all checks
```

### For Template Development

```bash
# Template testing
uv run pytest                                     # Run template tests
uvx copier copy . /tmp/test --trust              # Generate test project

# Template quality
uv run ruff check tests/                          # Lint template code
uv run ruff format tests/                         # Format template code

# Template documentation
uvx nox -s build_docs                             # Build template docs
uvx nox -s serve_docs                             # Serve template docs

# Using Just (template repo)
just test                 # Test template generation
just fix                  # Format template code
just serve                # Serve template docs
```

---

## Troubleshooting

### "uv not found"

Install uv:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### "copier not found"

Install copier or use uvx:
```bash
pip install copier
# or just use: uvx copier
```

### Tests fail after project generation

Install dependencies first:
```bash
cd my-package
uv sync --group dev
uv run pytest
```

### Documentation not building

Install docs dependencies:
```bash
uv sync --group docs
uvx nox -s build_docs
```

### Pre-commit hooks failing

Ensure pre-commit is installed:
```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

---

## Getting Help

- **Template Issues**: See [Development Guide](development.md)
- **Usage Questions**: Check [Usage Guide](usage.md)
- **Feature Details**: Read [Features](features.md)
- **Architecture**: Review [Template Structure](structure.md)
