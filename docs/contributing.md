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

## Commit Message Format

This project uses [Conventional Commits](https://www.conventionalcommits.org/) to automate changelog generation and releases. All commit messages must follow this format:

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### Commit Types

- `feat:` - A new feature (triggers minor version bump)
- `fix:` - A bug fix (triggers patch version bump)
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting, etc.)
- `refactor:` - Code refactoring
- `perf:` - Performance improvements
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks

### Breaking Changes

To indicate a breaking change (triggers major version bump):
- Add `!` after the type: `feat!: remove deprecated API`
- Or include `BREAKING CHANGE:` in the footer

### Examples

```bash
feat: add support for Python 3.13
fix(tests): correct test fixture configuration
docs: update quickstart guide
feat!: remove support for Python 3.9
```

The pre-commit hook will validate your commit messages automatically.

## Release Process

Releases are automated via GitHub Actions. Here's how it works:

### Creating a Release

1. **Ensure all changes follow conventional commits** - The changelog is auto-generated from commit messages

2. **Create and push a version tag**:
   ```bash
   git tag v0.2.0
   git push origin v0.2.0
   ```

3. **GitHub Actions automatically**:
   - Generates the changelog using [git-cliff](https://git-cliff.org/)
   - Creates a **Pull Request** with the updated `CHANGELOG.md`
   - Creates a GitHub Release with auto-generated release notes

4. **Manual step**:
   - Review and merge the CHANGELOG PR to update the main branch
   - The PR is automatically labeled with `changelog` and `automated`

### Version Numbering

This project follows [Semantic Versioning](https://semver.org/):
- **MAJOR** (1.0.0): Breaking changes
- **MINOR** (0.1.0): New features (backward compatible)
- **PATCH** (0.0.1): Bug fixes

The version is tracked via Git tags and managed by `hatch-vcs`.

### What Gets Into the Changelog

Based on your commit types:
- `feat:` → **Added** section
- `fix:` → **Fixed** section
- `docs:` → **Documentation** section
- `perf:` → **Performance** section
- `refactor:` → **Refactored** section
- `style:` → **Styling** section
- `test:` → **Testing** section
- `chore:` → **Miscellaneous** section

Commits that don't follow conventional format are excluded from the changelog.
