"""Comprehensive tests for documentation content in generated projects.

This test module validates:
- Documentation page content and structure
- Variable substitution in documentation
- mkdocs.yml navigation structure
- Documentation build consistency
- Examples documentation (when enabled)
"""

import yaml


class SafeMkdocsLoader(yaml.SafeLoader):
    """Custom YAML loader that handles !!python/name: tags without importing modules.

    This is needed because mkdocs.yml contains Material for MkDocs emoji configuration
    with !!python/name: tags that reference Python modules that may not be installed
    during testing. We convert these tags to plain strings for validation purposes.
    """

    pass


def construct_python_name(loader, suffix, node):
    """Convert !!python/name: tags to strings instead of importing the modules."""
    return loader.construct_scalar(node)


# Register multi constructor to handle any python/name: tag
SafeMkdocsLoader.add_multi_constructor("tag:yaml.org,2002:python/name:", construct_python_name)


class TestDocsIndexContent:
    """Test the main documentation index page."""

    def test_docs_index_includes_project_info(self, copie):
        """Test that docs index includes project metadata."""
        custom_answers = {
            "project_name": "My Awesome Tool",
            "description": "A powerful tool for data analysis",
            "author_name": "Jane Smith",
        }
        result = copie.copy(extra_answers=custom_answers)
        assert result.exit_code == 0

        docs_index = result.project_dir / "docs" / "index.md"
        assert docs_index.is_file()

        content = docs_index.read_text(encoding="utf-8")

        # Should include project name in welcome heading and throughout
        assert "My Awesome Tool" in content
        assert "Welcome to My Awesome Tool's documentation!" in content

        # Should include CTA cards with proper structure
        assert "Get Started in 5 Minutes" in content
        assert "Need Help?" in content
        assert "Learn the Concepts" in content

    def test_docs_index_structure(self, copie):
        """Test that docs index has proper markdown structure."""
        result = copie.copy(extra_answers={})
        assert result.exit_code == 0

        docs_index = result.project_dir / "docs" / "index.md"
        content = docs_index.read_text(encoding="utf-8")

        # Should have headings
        assert "#" in content

        # Should not be empty
        assert len(content.strip()) > 100


class TestGettingStartedPage:
    """Test the getting started documentation page."""

    def test_getting_started_exists(self, copie):
        """Test that getting started page exists."""
        result = copie.copy(extra_answers={})
        assert result.exit_code == 0

        getting_started = result.project_dir / "docs" / "pages" / "tutorials" / "getting-started.md"
        assert getting_started.is_file()

    def test_getting_started_includes_installation(self, copie):
        """Test that getting started includes installation instructions."""
        result = copie.copy(extra_answers={"package_name": "my_package"})
        assert result.exit_code == 0

        getting_started = result.project_dir / "docs" / "pages" / "tutorials" / "getting-started.md"
        content = getting_started.read_text(encoding="utf-8")

        # Should mention installation
        assert "install" in content.lower()

        # Should include package name in code blocks
        assert "my_package" in content or "my-package" in content

    def test_getting_started_includes_usage_example(self, copie):
        """Test that getting started includes basic usage examples."""
        result = copie.copy(extra_answers={})
        assert result.exit_code == 0

        getting_started = result.project_dir / "docs" / "pages" / "tutorials" / "getting-started.md"
        content = getting_started.read_text(encoding="utf-8")

        # Should have code blocks
        assert "```" in content

        # Should mention usage or example
        assert "usage" in content.lower() or "example" in content.lower()


class TestConceptsPage:
    """Test the concepts (explanation) documentation page."""

    def test_concepts_exists(self, copie):
        """Test that concepts page exists."""
        result = copie.copy(extra_answers={})
        assert result.exit_code == 0

        concepts = result.project_dir / "docs" / "pages" / "explanation" / "concepts.md"
        assert concepts.is_file()

    def test_concepts_has_content(self, copie):
        """Test that concepts page has meaningful content."""
        result = copie.copy(extra_answers={})
        assert result.exit_code == 0

        concepts = result.project_dir / "docs" / "pages" / "explanation" / "concepts.md"
        content = concepts.read_text(encoding="utf-8")

        # Should have multiple sections
        assert content.count("#") >= 2


class TestConfigurePage:
    """Test the configuration how-to page."""

    def test_configure_exists(self, copie):
        """Test that configure page exists."""
        result = copie.copy(extra_answers={})
        assert result.exit_code == 0

        configure = result.project_dir / "docs" / "pages" / "how-to" / "configure.md"
        assert configure.is_file()


class TestTroubleshootingPage:
    """The template deliberately seeds no troubleshooting page."""

    def test_the_template_seeds_no_troubleshooting_page(self, copie):
        """Troubleshooting is a project's own how-to, so the template must not ship one.

        It was a seed page, and seeding it was a trap either way. Left unprotected, a
        single em-dash in the stub's prose reverted sklearn-wrap's 225-line error
        reference and yohou-nixtla's 178 lines on frequency detection and CUDA OOM,
        each surviving only in a .rej. Adding it to _skip_if_exists fixed that and
        broke the other half: skip-if-exists means copy-if-absent, so the three
        projects that had deleted or renamed the page got the stub resurrected on
        every release -- and where configure.md does not exist, its link failed the
        strict build.

        A project's troubleshooting entries are about its own failures. Nothing
        generic belongs there, so the template seeds nothing and a project writes its
        own how-to if it wants one.
        """
        result = copie.copy(extra_answers={})
        assert result.exit_code == 0

        how_to = result.project_dir / "docs" / "pages" / "how-to"
        assert how_to.is_dir(), "no how-to directory; this test would assert nothing"
        assert not (how_to / "troubleshooting.md").exists(), (
            "the template seeds a troubleshooting page again; it is either clobbering a project's "
            "curated one or resurrecting a page three projects deleted"
        )

        mkdocs = (result.project_dir / "mkdocs.yml").read_text(encoding="utf-8")
        assert "how-to/troubleshooting.md" not in mkdocs, (
            "the nav still points at a troubleshooting page the template no longer ships, "
            "so every generated project fails its own strict docs build"
        )


class TestAPIReferencePage:
    """Test the API reference documentation page."""

    def test_api_reference_exists(self, copie):
        """Test that API reference page exists."""
        result = copie.copy(extra_answers={})
        assert result.exit_code == 0

        api_reference = result.project_dir / "docs" / "pages" / "reference" / "api.md"
        assert api_reference.is_file()

    def test_api_reference_includes_package_name(self, copie):
        """Test that API reference mentions the package name."""
        result = copie.copy(extra_answers={"package_name": "custom_pkg"})
        assert result.exit_code == 0

        api_reference = result.project_dir / "docs" / "pages" / "reference" / "api.md"
        content = api_reference.read_text(encoding="utf-8")

        # Should reference the package via the API_TABLE placeholder
        assert "API_TABLE" in content or "custom_pkg" in content

    def test_api_reference_has_code_documentation(self, copie):
        """Test that API reference includes code documentation."""
        result = copie.copy(extra_answers={})
        assert result.exit_code == 0

        api_reference = result.project_dir / "docs" / "pages" / "reference" / "api.md"
        content = api_reference.read_text(encoding="utf-8")

        # Should have API_TABLE placeholder (resolved at build time by the marker extension)
        assert "<!-- API_TABLE -->" in content


class TestContributingPage:
    """Test the contributing documentation page."""

    def test_contributing_page_exists(self, copie):
        """Test that contributing page exists."""
        result = copie.copy(extra_answers={})
        assert result.exit_code == 0

        contributing = result.project_dir / "docs" / "pages" / "how-to" / "contribute.md"
        assert contributing.is_file()

    def test_contributing_includes_development_setup(self, copie):
        """Test that contributing page includes development setup."""
        result = copie.copy(extra_answers={})
        assert result.exit_code == 0

        contributing = result.project_dir / "docs" / "pages" / "how-to" / "contribute.md"
        content = contributing.read_text(encoding="utf-8")

        # Should mention development setup
        assert "develop" in content.lower()

        # Should mention uv (the dependency manager)
        assert "uv" in content

    def test_contributing_includes_testing_info(self, copie):
        """Test that contributing page includes testing information."""
        result = copie.copy(extra_answers={})
        assert result.exit_code == 0

        contributing = result.project_dir / "docs" / "pages" / "how-to" / "contribute.md"
        content = contributing.read_text(encoding="utf-8")

        # Should mention testing
        assert "test" in content.lower()

        # Should mention nox or pytest
        assert "nox" in content or "pytest" in content

    def test_contributing_includes_lint_documentation(self, copie):
        """Test that contributing page documents the lint command with all three interfaces."""
        result = copie.copy(extra_answers={})
        assert result.exit_code == 0

        contributing = result.project_dir / "docs" / "pages" / "how-to" / "contribute.md"
        content = contributing.read_text(encoding="utf-8")

        # Should have lint section
        assert "Run linters and type checkers" in content or "lint" in content.lower()

        # Should document all three ways to run lint
        assert "just lint" in content
        assert "uvx nox -s lint" in content
        assert "uv run ruff check src tests" in content
        assert "uv run ty check src" in content

    def test_contributing_has_github_links_in_questions_section(self, copie):
        """Test that Questions section has clickable GitHub links."""
        custom_answers = {
            "github_username": "testuser",
            "project_slug": "test-project",
        }
        result = copie.copy(extra_answers=custom_answers)
        assert result.exit_code == 0

        contributing = result.project_dir / "docs" / "pages" / "how-to" / "contribute.md"
        content = contributing.read_text(encoding="utf-8")

        # Should have Questions section
        assert "## Questions?" in content

        # Should have GitHub issue link
        assert "[Open an issue on GitHub](https://github.com/testuser/test-project/issues/new)" in content

        # Should have GitHub discussions link
        assert "[Start a discussion in the repository](https://github.com/testuser/test-project/discussions)" in content

    def test_contributing_has_proper_semver_list_formatting(self, copie):
        """Test that Semantic Versioning section has properly formatted list."""
        result = copie.copy(extra_answers={})
        assert result.exit_code == 0

        contributing = result.project_dir / "docs" / "pages" / "how-to" / "contribute.md"
        content = contributing.read_text(encoding="utf-8")

        # Should have Version Numbering section with Semantic Versioning
        assert "### Version Numbering" in content
        assert "[Semantic Versioning](https://semver.org/)" in content

        # Check that there's a blank line before the list (proper markdown formatting)
        lines = content.split("\n")
        semver_line_idx = None
        for i, line in enumerate(lines):
            if "[Semantic Versioning](https://semver.org/):" in line:
                semver_line_idx = i
                break

        assert semver_line_idx is not None, "Semantic Versioning line not found"

        # Next line should be blank, then the list items
        assert lines[semver_line_idx + 1].strip() == "", "Missing blank line before list"
        assert "- **Major**" in lines[semver_line_idx + 2]

    def test_contributing_has_improved_mermaid_colors(self, copie):
        """Test that release process mermaid diagram has improved colors for visibility."""
        result = copie.copy(extra_answers={})
        assert result.exit_code == 0

        contributing = result.project_dir / "docs" / "pages" / "how-to" / "contribute.md"
        content = contributing.read_text(encoding="utf-8")

        # Should have mermaid diagram with improved styling
        assert "```mermaid" in content

        # Check for improved color styling (amber/orange and emerald green with white text)
        assert "fill:#f59e0b" in content  # Amber/orange color
        assert "fill:#10b981" in content  # Emerald green color
        assert "color:#fff" in content  # White text color for contrast


class TestExamplesPage:
    """Test the examples documentation page (when enabled)."""

    def test_examples_page_exists_when_enabled(self, copie):
        """Test that examples page exists when include_examples=True."""
        result = copie.copy(extra_answers={"include_examples": True})
        assert result.exit_code == 0

        examples_page = result.project_dir / "docs" / "pages" / "examples" / "index.md"
        assert examples_page.is_file()

    def test_examples_page_not_exists_when_disabled(self, copie):
        """Test that examples page doesn't exist when include_examples=False."""
        result = copie.copy(extra_answers={"include_examples": False})
        assert result.exit_code == 0

        examples_page = result.project_dir / "docs" / "pages" / "examples" / "index.md"
        assert not examples_page.exists()

    def test_examples_page_references_notebooks(self, copie):
        """Test that examples page references marimo notebooks."""
        result = copie.copy(extra_answers={"include_examples": True})
        assert result.exit_code == 0

        examples_page = result.project_dir / "docs" / "pages" / "examples" / "index.md"
        content = examples_page.read_text(encoding="utf-8")

        # Should reference examples or notebooks
        assert "example" in content.lower()

        # Should have iframe or links to examples
        assert "examples/" in content or "iframe" in content.lower()

    def test_examples_page_uses_gallery_placeholder(self, copie):
        """Test that examples page has gallery placeholder and running instructions."""
        result = copie.copy(extra_answers={"include_examples": True})
        assert result.exit_code == 0

        examples_page = result.project_dir / "docs" / "pages" / "examples" / "index.md"
        assert examples_page.is_file()

        content = examples_page.read_text(encoding="utf-8")

        # Should have GALLERY placeholder for dynamic gallery generation
        assert "<!-- GALLERY -->" in content
        # Should have Running Examples Locally section
        assert "## Running Examples Locally" in content
        assert "just example" in content

    def test_examples_page_describes_diataxis_grouping(self, copie):
        """Test that examples page intro describes tutorial/how-to grouping."""
        result = copie.copy(extra_answers={"include_examples": True})
        assert result.exit_code == 0

        examples_page = result.project_dir / "docs" / "pages" / "examples" / "index.md"
        content = examples_page.read_text(encoding="utf-8")

        assert "Tutorials" in content
        assert "How-to Guides" in content


class TestMkdocsConfiguration:
    """Test mkdocs.yml configuration."""

    def test_mkdocs_yml_structure(self, copie):
        """Test that mkdocs.yml has proper structure."""
        result = copie.copy(extra_answers={})
        assert result.exit_code == 0

        mkdocs_file = result.project_dir / "mkdocs.yml"
        assert mkdocs_file.is_file()

        mkdocs_data = yaml.load(mkdocs_file.read_text(encoding="utf-8"), Loader=SafeMkdocsLoader)

        # Required fields
        assert "site_name" in mkdocs_data
        assert "nav" in mkdocs_data or "navigation" in mkdocs_data
        assert "theme" in mkdocs_data

    def test_mkdocs_yml_includes_project_metadata(self, copie):
        """Test that mkdocs.yml includes correct project metadata."""
        custom_answers = {
            "project_name": "Custom Project",
            "description": "Custom description",
            "author_name": "Custom Author",
            "github_username": "custom-org",
            "project_slug": "custom-project",
        }
        result = copie.copy(extra_answers=custom_answers)
        assert result.exit_code == 0

        mkdocs_file = result.project_dir / "mkdocs.yml"
        content = mkdocs_file.read_text(encoding="utf-8")
        mkdocs_data = yaml.load(content, Loader=SafeMkdocsLoader)

        # Check site_name
        assert mkdocs_data["site_name"] == "Custom Project"

        # Check site_description
        assert "site_description" in mkdocs_data
        assert mkdocs_data["site_description"] == "Custom description"

        # Check repo_url
        assert "repo_url" in mkdocs_data
        assert "custom-org" in mkdocs_data["repo_url"]
        assert "custom-project" in mkdocs_data["repo_url"]

    def test_mkdocs_yml_navigation_structure(self, copie):
        """Test that mkdocs.yml has proper navigation structure."""
        result = copie.copy(extra_answers={"include_examples": False})
        assert result.exit_code == 0

        mkdocs_file = result.project_dir / "mkdocs.yml"
        mkdocs_data = yaml.load(mkdocs_file.read_text(encoding="utf-8"), Loader=SafeMkdocsLoader)

        nav = mkdocs_data.get("nav", [])
        assert len(nav) > 0

        # Should have standard pages
        nav_str = str(nav).lower()
        assert "getting" in nav_str or "start" in nav_str
        assert "contributing" in nav_str
        assert "api" in nav_str or "reference" in nav_str

    def test_mkdocs_yml_navigation_includes_examples_when_enabled(self, copie):
        """Test that navigation includes examples when enabled."""
        result = copie.copy(extra_answers={"include_examples": True})
        assert result.exit_code == 0

        mkdocs_file = result.project_dir / "mkdocs.yml"
        mkdocs_data = yaml.load(mkdocs_file.read_text(encoding="utf-8"), Loader=SafeMkdocsLoader)

        nav = mkdocs_data.get("nav", [])
        nav_str = str(nav).lower()

        # Should include examples in navigation
        assert "example" in nav_str

    def test_mkdocs_yml_navigation_lists_the_citation_page_under_reference(self, copie_session_default):
        """Citing is a lookup, so the page belongs in Reference and must be in the nav.

        The nav entry is not only placement: the Reference index resolves its own
        contents from `<!-- SUBPAGES -->`, which reads the nav. A page missing from the
        nav is a page nothing links to.
        """
        mkdocs_file = copie_session_default.project_dir / "mkdocs.yml"
        mkdocs_data = yaml.load(mkdocs_file.read_text(encoding="utf-8"), Loader=SafeMkdocsLoader)

        reference = next((section["Reference"] for section in mkdocs_data["nav"] if "Reference" in section), None)
        assert reference is not None, "the nav has no Reference section"

        titles = [title for entry in reference if isinstance(entry, dict) for title in entry]
        assert "Citation" in titles, f"the Reference section does not list the citation page: {titles}"

        pages = [page for entry in reference if isinstance(entry, dict) for page in entry.values()]
        assert "pages/reference/citation.md" in pages, "the Citation nav entry points somewhere else"

    def test_mkdocs_yml_navigation_excludes_examples_when_disabled(self, copie):
        """Test that navigation excludes examples when disabled."""
        result = copie.copy(extra_answers={"include_examples": False})
        assert result.exit_code == 0

        mkdocs_file = result.project_dir / "mkdocs.yml"
        mkdocs_data = yaml.load(mkdocs_file.read_text(encoding="utf-8"), Loader=SafeMkdocsLoader)

        nav = mkdocs_data.get("nav", [])
        nav_str = str(nav).lower()

        # Should NOT include examples in navigation
        assert "example" not in nav_str

    def test_mkdocs_yml_uses_material_theme(self, copie):
        """Test that mkdocs.yml uses Material theme."""
        result = copie.copy(extra_answers={})
        assert result.exit_code == 0

        mkdocs_file = result.project_dir / "mkdocs.yml"
        mkdocs_data = yaml.load(mkdocs_file.read_text(encoding="utf-8"), Loader=SafeMkdocsLoader)

        theme = mkdocs_data.get("theme", {})
        if isinstance(theme, dict):
            assert theme.get("name") == "material"
        else:
            assert theme == "material"

    def test_mkdocs_yml_includes_plugins(self, copie):
        """Test that mkdocs.yml includes necessary plugins."""
        result = copie.copy(extra_answers={})
        assert result.exit_code == 0

        mkdocs_file = result.project_dir / "mkdocs.yml"
        mkdocs_data = yaml.load(mkdocs_file.read_text(encoding="utf-8"), Loader=SafeMkdocsLoader)

        assert "plugins" in mkdocs_data
        plugins = mkdocs_data["plugins"]

        # Should have search plugin
        plugins_str = str(plugins).lower()
        assert "search" in plugins_str

    def test_mkdocs_yml_includes_marimo_plugin_when_examples_enabled(self, copie):
        """Test that mkdocs.yml does not include marimo plugin (marimo embed is used instead)."""
        result = copie.copy(extra_answers={"include_examples": True})
        assert result.exit_code == 0

        mkdocs_file = result.project_dir / "mkdocs.yml"
        mkdocs_data = yaml.load(mkdocs_file.read_text(encoding="utf-8"), Loader=SafeMkdocsLoader)

        plugins = mkdocs_data.get("plugins", [])
        plugins_str = str(plugins).lower()

        # marimo plugin is not used - we use marimo-embed directive instead
        assert "marimo" not in plugins_str

    def test_mkdocs_yml_excludes_marimo_plugin_when_examples_disabled(self, copie):
        """Test that mkdocs.yml excludes marimo plugin when examples disabled."""
        result = copie.copy(extra_answers={"include_examples": False})
        assert result.exit_code == 0

        mkdocs_file = result.project_dir / "mkdocs.yml"
        mkdocs_data = yaml.load(mkdocs_file.read_text(encoding="utf-8"), Loader=SafeMkdocsLoader)

        plugins = mkdocs_data.get("plugins", [])
        plugins_str = str(plugins).lower()

        # Should NOT include marimo plugin
        assert "marimo" not in plugins_str

    def test_mkdocs_yml_has_hooks_configured(self, copie):
        """The marker extension is registered in mkdocs.yml; the hooks: key is gone."""
        result = copie.copy(extra_answers={})
        assert result.exit_code == 0

        mkdocs_file = result.project_dir / "mkdocs.yml"
        mkdocs_data = yaml.load(mkdocs_file.read_text(encoding="utf-8"), Loader=SafeMkdocsLoader)

        # The `hooks:` key is gone -- the successor engine does not execute it, so
        # markers resolve through a markdown extension registered here instead.
        assert "hooks" not in mkdocs_data, "the hooks: key should be gone from mkdocs.yml"
        extensions = [e for e in mkdocs_data["markdown_extensions"] if isinstance(e, str)]
        assert "docs_build._markers" in extensions, "the marker extension is not registered in mkdocs.yml"
        assert "docs_build._glossary" in extensions, "the glossary extension is not registered in mkdocs.yml"

    def test_mkdocs_yml_emoji_uses_a_live_index(self, copie):
        """Emoji must name an index explicitly, because the default one is dead.

        A bare ``pymdownx.emoji`` falls back to the EmojiOne index, whose asset
        URLs point at an ``emojione/2.2.7`` CDN path that has been offline since
        2017. Every emoji rendered as a broken image, in every engine, with no
        warning -- the declaration looked deliberate and did the wrong thing.

        This test previously asserted the opposite (that no ``!!python/name:``
        tag appears) which is what allowed the bare declaration to stand. The
        tag is required: ``emoji_index`` takes a callable and YAML cannot name
        one otherwise. Every reader of this file registers a constructor for it.
        """
        result = copie.copy(extra_answers={})
        assert result.exit_code == 0

        mkdocs_file = result.project_dir / "mkdocs.yml"
        assert mkdocs_file.is_file()
        content = mkdocs_file.read_text(encoding="utf-8")

        assert "pymdownx.emoji" in content
        assert "emoji_index: !!python/name:pymdownx.emoji.twemoji" in content
        assert "emoji_generator: !!python/name:pymdownx.emoji.to_svg" in content

        # The index is deliberately pymdownx's, not Material's: the template
        # uses no `:material-*:` shortcodes, and naming the theme package here
        # would bind the markdown config to the theme. Assert on the *value*,
        # not the string -- the config comment names the rejected alternative,
        # so a bare substring check would fail on the explanation.
        assert "emoji_index: !!python/name:material.extensions.emoji" not in content
        assert "!!python/name:pymdownx.emoji.emojione" not in content

    def test_mkdocs_yml_magiclink_enables_repo_shorthand(self, copie):
        """Magiclink must enable the shorthand, or only bare URLs autolink.

        Declared bare, ``pymdownx.magiclink`` autolinks full URLs but renders
        ``#12`` and ``@octocat`` as literal text -- the issue, pull request and
        user shorthand is the reason to enable it on a project hosted on GitHub.
        The shorthand also needs ``user`` and ``repo`` to resolve a bare ``#12``.
        """
        result = copie.copy(extra_answers={"github_username": "acme", "project_slug": "widget"})
        assert result.exit_code == 0

        content = (result.project_dir / "mkdocs.yml").read_text(encoding="utf-8")

        assert "repo_url_shorthand: true" in content
        assert "social_url_shorthand: true" in content
        assert "user: acme" in content
        assert "repo: widget" in content


class TestDocumentationVariableSubstitution:
    """Test that template variables are correctly substituted in all docs."""

    def test_all_docs_use_correct_package_name(self, copie):
        """Test that all documentation uses the correct package name."""
        result = copie.copy(extra_answers={"package_name": "my_custom_pkg"})
        assert result.exit_code == 0

        docs_pages = [
            result.project_dir / "docs" / "index.md",
            result.project_dir / "docs" / "pages" / "tutorials" / "getting-started.md",
            result.project_dir / "docs" / "pages" / "reference" / "api.md",
        ]

        for page in docs_pages:
            if page.exists():
                content = page.read_text(encoding="utf-8")

                # Should not have template placeholders
                assert "{{" not in content
                assert "}}" not in content
                assert "package_name" not in content or "my_custom_pkg" in content

    def test_docs_use_correct_github_username(self, copie):
        """Test that documentation uses correct GitHub username in URLs."""
        result = copie.copy(
            extra_answers={
                "github_username": "my-custom-org",
                "project_slug": "my-project",
            }
        )
        assert result.exit_code == 0

        # Check mkdocs.yml
        mkdocs_file = result.project_dir / "mkdocs.yml"
        content = mkdocs_file.read_text(encoding="utf-8")

        assert "my-custom-org" in content
        assert "github.com/my-custom-org/my-project" in content

        # Check contributing page
        contributing = result.project_dir / "docs" / "pages" / "how-to" / "contribute.md"
        if contributing.exists():
            contrib_content = contributing.read_text(encoding="utf-8")
            # Should reference the correct repository
            assert "my-custom-org" in contrib_content or "my-project" in contrib_content
