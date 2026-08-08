# Security

Every package generated from this template inherits a hardened, security-first posture by
default. This page explains the measures a generated project ships with and what each one
means for the people who depend on that package, so adopters know exactly what they are
getting and downstream users know what protects them.

The template repository itself follows the same posture as its own first adopter, and
these controls are kept current across template releases so they do not drift.

## How releases reach users safely

**Trusted publishing (OIDC).** Generated projects publish to PyPI through GitHub's OpenID
Connect trusted-publishing flow. No long-lived PyPI API token exists to be stolen: a
release can only originate from the project's own audited release workflow.

**Signed artifacts (PEP 740 attestations).** Every published distribution carries a
Sigstore attestation binding it to the exact workflow run that built it, so a consumer can
verify that an installed artifact is the one the project actually released.

**A software bill of materials (SBOM).** Each release ships a CycloneDX SBOM listing every
dependency it resolves, so a newly disclosed vulnerability in a transitive dependency can
be traced to the affected releases in seconds.

**Immutable, monitored dependencies.** Third-party GitHub Actions and Python dependencies
are pinned and kept current by Renovate as reviewable pull requests, so nothing is swapped
out from under a release.

## How the code is checked

**Static security analysis.** ruff's flake8-bandit (`S`) ruleset scans every change for
insecure patterns (unsafe subprocess use, weak hashing, hardcoded credentials, unsafe
deserialization) before it can merge. It runs on public and private projects alike.

**Deep analysis (CodeQL).** Public projects additionally run GitHub's CodeQL data-flow
analysis, which catches vulnerability classes such as injection and path traversal that
line-level linting cannot see.

**Secret scanning.** gitleaks runs as a pre-commit hook and as an un-bypassable CI check,
so credentials never enter a codebase or a release.

## How the pipeline itself is hardened

**Least privilege.** Every generated workflow runs with a read-only token by default; only
the jobs that must write are granted more.

**A single merge gate.** No change lands until the full test suite and the security checks
above all pass, enforced as one required status check.

**Untrusted input never becomes code.** Values an outsider controls -- a pull request
title, an issue body, a fork's branch name -- reach a workflow's shell only as environment
variables. Workflow expressions are substituted into a script *before* the shell parses
it, so interpolating one directly turns a crafted pull request title into commands that
run with the release job's privileges. Quoting does not help; passing the value through
`env:` does, because the runner then hands it over as data. A test asserts this over both
the generated workflows and the ones this repository runs.

**Scoped automation identity.** Release automation uses a short-lived, narrowly-scoped
GitHub App token rather than a broad personal access token.

## Transparency and disclosure

**An independent security grade.** Public projects are scored weekly by the
[OpenSSF Scorecard](https://securityscorecards.dev/), a public automated audit of their
security practices, so a project's posture is verifiable rather than merely asserted.

**Responsible disclosure.** Every project ships a `SECURITY.md` describing how to report a
vulnerability privately, and a `CODEOWNERS` file so changes are reviewed before they merge.

**Visibility-aware.** A private project does not ship the public-only controls (CodeQL, the
public Scorecard grade); it keeps the static analysis and secret scanning, which run
identically regardless of visibility, so its security page never claims a control it does
not run.
