# How to Update from Template

This guide shows you how to pull in the latest template improvements to an existing project generated from python-package-copier.

## Prerequisites

- A project previously generated with `uvx copier copy gh:stateful-y/python-package-copier`
- The project must contain a `.copier-answers.yml` file (generated automatically)
- [copier](https://copier.readthedocs.io/) installed (`uvx copier` works)

## Check Your Current Template Version

```bash
cat .copier-answers.yml
```

The `_commit` field shows the template commit your project was generated from.

## Update to Latest Template

Run from your project's root directory:

```bash
copier update --trust
```

Copier will:

1. Pull the latest template from `gh:stateful-y/python-package-copier`
2. Show you a diff of changes
3. Prompt for any new configuration questions added since your last update
4. Apply updates while preserving your modifications

## Update to a Specific Version

Pin to a specific template version:

```bash
copier update --trust --vcs-ref=v1.2.0
```

Or update to a specific commit:

```bash
copier update --trust --vcs-ref=abc123
```

## Handle Conflicts

If you've modified files that the template also changed, Copier will flag conflicts.

### Inline Conflict Markers (Default)

```bash
copier update --trust --conflict inline
```

This adds Git-style conflict markers in the affected files:

```text
<<<<<<< before updating
your local changes
=======
template changes
>>>>>>> after updating
```

Resolve them manually, then commit.

### Reject Files

```bash
copier update --trust --conflict rej
```

This creates `.rej` files alongside conflicting files. Review each `.rej` file, apply the changes you want, and delete the `.rej` files.

## What Gets Updated

Template updates can include:

- **CI workflow improvements** - new testing strategies, updated actions versions
- **Tool configuration** - ruff rules, coverage settings, pre-commit hooks
- **Documentation scaffolding** - new doc pages, improved templates
- **Build system** - dependency group changes, hatchling config

## What Is Preserved

Copier respects your local changes. Files you've customized are merged, not overwritten. Specifically:

- Your source code in `src/` is never touched by template updates
- Your test files in `tests/` are preserved
- Custom content you added to documentation is preserved
- Dependencies you added to `pyproject.toml` are preserved

### CLAUDE.md and other seed-once files

A few files are delivered **once**, when your project is generated, and then never
again. `CLAUDE.md` is one of them, alongside your logo and favicon, the documentation
landing page, and the getting-started tutorial.

These are files every project rewrites completely. Once yours no longer resembles the
template's version, there is nothing left to merge: an update applied as a diff against
the template's copy would reject the whole change and revert your page to the starter
content, leaving your work in a `.rej` file nobody reads. That is not a theoretical
risk. One template release changed a single blank line and replaced five projects'
hand-written getting-started pages with the 74-line stub.

So the template stops delivering them. Rewrite `CLAUDE.md` however you like: record why
a dependency is pinned, which template assumptions your project breaks, what a failing
check actually means. Updates will leave it alone, and you will not see a conflict for
it because there is no conflict to have.

The trade is that improvements the template later makes to these files do **not** reach
you automatically. If you want them, copy them across by hand. That is deliberate: a
template that can append to a page it does not own can also delete from it.

## AI-Assisted Updates

If you use GitHub Copilot or a similar AI coding assistant, you can ask it to handle the update for you. The template ships with an **`update-from-template` skill** that automates the full workflow:

1. Pre-flight checks (clean working tree, current template version)
2. Detecting which files you've customized vs. kept as-is
3. Running `copier update` on a dedicated branch
4. Resolving conflicts using a 3-tier file classification (template-managed, merge-required, local-owned)
5. Verifying tests and linting pass after the update

To trigger it, ask your AI assistant: *"update from template"* or *"sync template changes"* from within your generated project.

## Troubleshooting

**Problem: `copier update` fails with "not a copier project"**
: Ensure `.copier-answers.yml` exists in the project root. If it was accidentally deleted, you cannot update - you would need to regenerate the project.

**Problem: Too many conflicts after a long gap**
: Update incrementally by specifying intermediate versions with `--vcs-ref`.

**Problem: New template variables have no answers**
: Copier will prompt you for any new variables interactively. To set defaults non-interactively, use `--defaults`.

## See Also

- [Template Variables](../reference/template-variables.md) - understand what each variable controls
- [Project Structure](../reference/project-structure.md) - what files the template generates
