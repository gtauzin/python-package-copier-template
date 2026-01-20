"""Nox sessions for the python-package-copier-template."""

import nox

# Require Nox version 2024.3.2 or newer to support the 'default_venv_backend' option
nox.needs_version = ">=2024.3.2"

# Set 'uv' as the default backend for creating virtual environments
nox.options.default_venv_backend = "uv|virtualenv"

# Default sessions to run when nox is called without arguments
nox.options.sessions = ["fix", "tests", "serve_docs"]


@nox.session(python=["3.10", "3.11", "3.12"], venv_backend="uv")
def tests(session: nox.Session) -> None:
    """Run the tests with pytest."""
    # Install dependencies
    session.run_install(
        "uv",
        "sync",
        "--group",
        "test",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )

    # Run tests
    session.run(
        "pytest",
        "tests/",
        "-v",
        *session.posargs,
    )


@nox.session(venv_backend="uv")
def fix(session: nox.Session) -> None:
    """Format the code base to adhere to our styles, and complain about what we cannot do automatically."""
    # Install dependencies
    session.run_install(
        "uv",
        "sync",
        "--no-default-groups",
        "--group",
        "fix",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )
    # Run pre-commit
    session.run("pre-commit", "run", "--all-files", "--show-diff-on-failure", *session.posargs, external=True)


@nox.session(venv_backend="uv")
def lint(session: nox.Session) -> None:
    """Run linters."""
    # Install dependencies
    session.run_install(
        "uv",
        "pip",
        "install",
        "ruff",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )

    # Run ruff check
    session.run("ruff", "check", "tests/", external=True)


@nox.session(venv_backend="uv")
def build_docs(session: nox.Session) -> None:
    """Build the documentation."""
    # Install dependencies
    session.run_install(
        "uv",
        "sync",
        "--group",
        "docs",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )
    # Build the docs
    session.run("mkdocs", "build", "--clean", external=True)


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
    # Build and serve the docs
    session.run("mkdocs", "build", "--clean", external=True)
    session.log("###### Starting local server. Press Control+C to stop server ######")
    session.run("mkdocs", "serve", "-a", "localhost:8080", external=True)
