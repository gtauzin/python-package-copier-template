"""Nox sessions for the python-package-copier."""

from pathlib import Path

import nox

# Require Nox version 2024.3.2 or newer to support the 'default_venv_backend' option
nox.needs_version = ">=2024.3.2"

# Set 'uv' as the default backend for creating virtual environments
nox.options.default_venv_backend = "uv|virtualenv"

# Keep the session virtualenvs under `.artifacts/` with every other piece of
# throwaway output, instead of dropping a `.nox/` at the repo root.
nox.options.envdir = ".artifacts/nox"

# The single definition of where build output goes; readers derive from it.
ARTIFACTS_DIR = Path(".artifacts")
SITE_DIR = ARTIFACTS_DIR / "site"

# Default sessions to run when nox is called without arguments
nox.options.sessions = ["fix", "test_fast", "serve_docs"]


@nox.session(python=["3.11", "3.12", "3.13", "3.14"], venv_backend="uv")
def test(session: nox.Session) -> None:
    """Run the tests with pytest."""
    # Install dependencies
    session.run_install(
        "uv",
        "sync",
        "--group",
        "tests",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )

    # Run tests with parallel execution
    session.run(
        "pytest",
        "tests/",
        "-n",
        "auto",
        "-v",
        *session.posargs,
    )


@nox.session(python=["3.11", "3.12", "3.13", "3.14"], venv_backend="uv")
def test_fast(session: nox.Session) -> None:
    """Run fast tests (excludes slow and integration tests)."""
    # Install dependencies
    session.run_install(
        "uv",
        "sync",
        "--group",
        "tests",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )

    # Run fast tests only with parallel execution
    session.run(
        "pytest",
        "tests/",
        "-m",
        "not slow and not integration",
        "-n",
        "auto",
        "-v",
        *session.posargs,
    )


@nox.session(python=["3.11", "3.12", "3.13", "3.14"], venv_backend="uv")
def test_slow(session: nox.Session) -> None:
    """Run slow and integration tests."""
    # Install dependencies
    session.run_install(
        "uv",
        "sync",
        "--group",
        "tests",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )

    # Run slow/integration tests only with parallel execution
    session.run(
        "pytest",
        "tests/",
        "-m",
        "slow or integration",
        "-n",
        "auto",
        "-v",
        "-v",
        *session.posargs,
    )


# Unlike every other session, this one owns no environment. `uv run --locked` resolves
# prek from uv.lock, and each local hook resolves its own tool from that same project
# environment. A nox venv here would be a second environment that only ever holds the
# runner -- which is the redundant install this session used to pay for on every run.
@nox.session(venv_backend="none")
def fix(session: nox.Session) -> None:
    """Format the code base to adhere to our styles, and complain about what we cannot do automatically."""
    # Run at the pre-push stage. A hook with no `stages:` key runs at every stage, so this
    # one pass covers the full suite: the autofixing formatters AND the pre-push gate
    # (interrogate), while excluding commitizen (pinned to commit-msg). A plain `prek run`
    # uses the pre-commit stage, which since interrogate moved to pre-push would silently
    # skip it -- here and in the CI lint job that runs this session. --locked pins the exact
    # uv.lock versions, so a stale lock fails loudly and local matches CI, and it keeps prek
    # pinned -- never use `uvx prek`.
    session.run(
        "uv",
        "run",
        "--locked",
        "prek",
        "run",
        "--all-files",
        "--show-diff-on-failure",
        "--stage",
        "pre-push",
        *session.posargs,
        external=True,
    )


@nox.session(venv_backend="uv")
def lint(session: nox.Session) -> None:
    """Run linters."""
    # Install dependencies. --locked pins the exact uv.lock versions so this matches CI.
    session.run_install(
        "uv",
        "sync",
        "--locked",
        "--no-default-groups",
        "--group",
        "lint",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )

    # Run ruff check
    session.run("ruff", "check", "tests/", external=True)

    # Run rumdl markdown linter (resolved from the lint group, not uvx-latest)
    session.run("rumdl", "check", ".", external=True)


@nox.session(venv_backend="uv")
def link_docs(session: nox.Session) -> None:
    """Check the built documentation for dead links."""

    site_dir = SITE_DIR
    if not site_dir.exists():
        session.error(f"{site_dir}/ not found. Run 'just build' or 'nox -s build_docs' first.")

    session.run(
        "uvx",
        "linkchecker",
        str(site_dir / "index.html"),
        "--no-status",
        "--no-warnings",
        "--ignore-url",
        "material/overrides",
        *session.posargs,
        external=True,
    )


@nox.session(venv_backend="uv")
def build_docs(session: nox.Session) -> None:
    """Build the documentation with the engine that publishes it.

    Zensical, not MkDocs. `.readthedocs.yml` runs `zensical build` and the `justfile`
    does too, so a nox session on MkDocs built an artifact nobody publishes: it could
    stay green through a Zensical-only failure, and the empty-site bug this repo has
    already hit is exactly that shape (zero HTML at exit 0, `--strict` included).
    """
    # Install dependencies
    session.run_install(
        "uv",
        "sync",
        "--group",
        "docs",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )

    # Build the docs. Zensical has no --clean flag; it rebuilds site/ in place.
    session.run("zensical", "build", external=True)


@nox.session(venv_backend="uv")
def serve_docs(session: nox.Session) -> None:
    """Run a development server for working on documentation."""
    # Install dependencies
    session.run_install(
        "uv",
        "sync",
        "--group",
        "docs",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )

    # Serve with the publishing engine, matching build_docs and the justfile.
    session.log("###### Starting local server. Press Control+C to stop server ######")
    session.run("zensical", "serve", "-a", "localhost:8080", external=True)
