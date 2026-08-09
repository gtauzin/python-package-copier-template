"""Single source of truth for where a generated project's docs build tooling lives.

Everything the docs build needs and the site must never publish lives in one
directory, ``docs_build/``: the build modules (``build.py`` and its siblings), the
theme overrides, and the mkdocstrings templates. It is a sibling of ``docs/`` rather
than a child of it, and that is the whole point. Mkdocs copies every non-page file
under ``docs_dir`` into the site, and the successor engine ignores the
``exclude_docs`` key that used to suppress that -- so location, not configuration,
is what keeps build tooling out of the published site under either engine.

The overrides and templates used to sit in a second directory, ``docs_theme/``.
Merging them here costs one root entry and keeps the same guarantee, since both
directories were already outside ``docs_dir`` for the same reason.

Every test that constructs a path to build tooling routes through here, so the next
relocation is one edit instead of another few dozen.
"""

BUILD_DIR = "docs_build"

# Subdirectories of BUILD_DIR. `OVERRIDES_DIR` holds the theme's `custom_dir`
# templates; `TEMPLATES_DIR` holds the mkdocstrings `custom_templates` tree.
OVERRIDES_DIR = f"{BUILD_DIR}/overrides"
TEMPLATES_DIR = f"{BUILD_DIR}/templates"

# Where a build writes. This must agree with `site_dir` in the generated mkdocs.yml,
# which is the only thing that decides where the site actually lands -- Zensical has
# no site-dir flag to override it with. `tests/test_artifact_paths.py` asserts the
# agreement; this constant exists so the tests that READ a built site do not each
# spell the path out again.
ARTIFACTS_DIR = ".artifacts"
SITE_DIR = f"{ARTIFACTS_DIR}/site"


def build_module(project_dir, name):
    """Path to a build-tooling module in a generated project.

    ``name`` is a bare filename, e.g. ``"build.py"`` or ``"_api_pages.py"``.
    """
    return project_dir / BUILD_DIR / name


def mkdocstrings_templates(project_dir):
    """Path to the mkdocstrings override templates in a generated project."""
    return project_dir / TEMPLATES_DIR / "python" / "material"


def site_path(project_dir):
    """Path to the built documentation site in a generated project."""
    return project_dir / SITE_DIR
