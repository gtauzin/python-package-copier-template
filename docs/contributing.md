# Contributing

## Setup

```bash
# Clone the repository
git clone https://github.com/gtauzin/python-package-copier-template.git
cd python-package-copier-template

# Install dependencies
uv sync --group test --group docs

# Install pre-commit hooks (optional)
uv run pre-commit install
```

## Test Template Changes

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

## Code Quality

```bash
# Format and fix all issues
just fix

# Check code
just check
```

## Documentation

```bash
# Build documentation
uvx nox -s build_docs

# Serve documentation at localhost:8080
uvx nox -s serve_docs
# or: just serve
```

## Modifying the Template

### Edit Template Files

Template files are in the `template/` directory. Files ending with `.jinja` are rendered by Copier with variable substitution.

### Edit Template Configuration

Edit `copier.yml` to add or modify template prompts and variables.

### Test Your Changes

After making changes:
1. Run `uv run pytest -v` to test template generation
2. Generate a test project: `uvx copier copy . /tmp/test-project --trust`
3. Verify the generated project works
