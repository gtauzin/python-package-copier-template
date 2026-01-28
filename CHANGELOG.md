# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [0.5.0] - 2026-01-28

This **minor release** includes 3 commits.


### Features
- Make just install pre-commit by @gtauzin

### Bug Fixes
- Transfer repos ownership to stateful-y by @gtauzin
- Make just install point to dev group by @gtauzin

### Contributors

Thanks to all contributors for this release:
- @gtauzin
## [0.4.0] - 2026-01-28

This **minor release** includes 4 commits.


### Features
- Add docstring testing support and restructure documentation  ([#37](https://github.com/gtauzin/python-package-copier-template/pull/37)) by @gtauzin
- Add optional marimo notebook examples  ([#38](https://github.com/gtauzin/python-package-copier-template/pull/38)) by @gtauzin

### Bug Fixes
- Improve release notes extraction from CHANGELOG.md  ([#35](https://github.com/gtauzin/python-package-copier-template/pull/35)) by @gtauzin
- Correct copier source path and add update documentation  ([#36](https://github.com/gtauzin/python-package-copier-template/pull/36)) by @gtauzin

### Refactoring
- Rename `include_github_actions` into `include_actions` and `python_version` into `min_python_version`  ([#38](https://github.com/gtauzin/python-package-copier-template/pull/38)) by @gtauzin

### Contributors

Thanks to all contributors for this release:
- @gtauzin

## [0.3.0] - 2026-01-22

This **minor release** includes 7 commits.


### Features
- Add dependency groups for dev, checks, and examples  ([#28](https://github.com/gtauzin/python-package-copier-template/pull/28)) by @gtauzin
- Add PR title validation and improve git-cliff configuration  ([#33](https://github.com/gtauzin/python-package-copier-template/pull/33)) by @gtauzin

### Bug Fixes
- Extract release notes from merged CHANGELOG.md instead of regenerating  ([#25](https://github.com/gtauzin/python-package-copier-template/pull/25)) by @gtauzin
- Remove license classifier from template  ([#26](https://github.com/gtauzin/python-package-copier-template/pull/26)) by @gtauzin
- Update lint command to check types correctly  ([#27](https://github.com/gtauzin/python-package-copier-template/pull/27)) by @gtauzin
- Exclude _version.py from ruff and coverage reports  ([#29](https://github.com/gtauzin/python-package-copier-template/pull/29)) by @gtauzi

### Documentation
- Document automated release workflow with git-cliff and changelog PR  ([#30](https://github.com/gtauzin/python-package-copier-template/pull/30)) by @gtauzin

### Contributors

Thanks to all contributors for this release:
- @gtauzin

## [0.2.0] - 2026-01-21

This **minor release** includes 13 commits.


### Features
- Automate release notes with git-cliff and commitizen  ([#6](https://github.com/gtauzin/python-package-copier-template/pull/6)) by @gtauzin
- Align template repo tooling with generated projects  ([#7](https://github.com/gtauzin/python-package-copier-template/pull/7)) by @gtauzin
- Enrich CHANGELOG generation with metadata and fix lint issues  ([#21](https://github.com/gtauzin/python-package-copier-template/pull/21)) by @gtauzin

### Bug Fixes
- Remove non-functional include_docker prompt  ([#5](https://github.com/gtauzin/python-package-copier-template/pull/5)) by @gtauzin
- Use PR instead of direct push for CHANGELOG updates  ([#8](https://github.com/gtauzin/python-package-copier-template/pull/8), [#9](https://github.com/gtauzin/python-package-copier-template/pull/9), [#10](https://github.com/gtauzin/python-package-copier-template/pull/10), [#11](https://github.com/gtauzin/python-package-copier-template/pull/11)) by @gtauzin
- Create GitHub Release after changelog PR is merged  ([#13](https://github.com/gtauzin/python-package-copier-template/pull/13), [#15](https://github.com/gtauzin/python-package-copier-template/pull/15), [#17](https://github.com/gtauzin/python-package-copier-template/pull/17), [#19](https://github.com/gtauzin/python-package-copier-template/pull/19), [#23](https://github.com/gtauzin/python-package-copier-template/pull/23)) by @gtauzin

### Contributors

Thanks to all contributors for this release:
- @gtauzin

## [0.1.0] - 2026-01-20

This **minor release** includes 1 commit.

### Added
- Modern Python package template using Copier
- Type checking with ty
- Fast dependency management with uv
- Linting and formatting with ruff
- Testing with pytest and nox
- Documentation with MkDocs Material theme
- GitHub Actions CI/CD workflows
- Pre-commit hooks configuration
- Task automation with justfile
- Comprehensive test suite for template validation
- ReadTheDocs integration
- Multiple license options (MIT, Apache-2.0, BSD-3-Clause, GPL-3.0, Proprietary)
- Example code and tests
- Full documentation structure

### Contributors

Thanks to all contributors for this release:
- @gtauzin
