---
name: fan-out-to-packages
description: Roll a template change out to every stateful-y package generated from python-package-copier, one agent per repo in parallel. Use when a template release must reach the fleet, when auditing all generated projects for a shared defect, or when applying a docs/config convention everywhere. Covers the seven repos and what differs between them, the copier update hazards that destroy local content silently, the per-repo invariants, and the verification discipline that stops a green result from being meaningless.
---

# Fan Out To Packages

Roll a change out to every package generated from this template. One agent per repo,
in parallel, each owning exactly one clone.

**The governing fact: this fleet fails silently.** Copier overwrites local files with
no conflict and no `.rej`. Docs markers that resolve to nothing render nothing.
Hook-emitted links are invisible to `--strict`. Almost every real defect found in this
fleet was invisible in a green build, and almost every *first* measurement of it was
wrong. Plan for that or the fan-out reports success and ships damage.

## 1. The fleet

Seven repos in `stateful-y`, all generated from this template (verify with
`.copier-answers.yml` `_src_path`). `internal`, `kedro-dagster-example`,
`staged-recipes` and `website` are **not** generated and must never be included.

Every repo is a `src/<package>/` layout. Nothing in this fleet is flat, so
`_get_root_members`' hardcoded `src/<pkg>` path is inert here — a genuinely flat repo
would get a silent empty return from it, but none exists yet.

| repo | `include_examples` | what makes it different |
|---|---|---|
| **yohou** | True | The reference implementation and the biggest: ~79 notebooks in **7** groups (6 `examples/` subdirs plus top-level `quickstart.py`), 46 companion pages, 6 curated section pages, hand-written See Also bullets, a 35-link how-to index grouped under 8 headings. It **deleted the seed how-tos** (`contribute.md`, `troubleshooting.md`) for 36 curated ones, so any release touching those is inert here. The only repo that `select`s ruff's `D`, so it is the only one that sees a docstring defect in a template-owned file. Its docs are the quality bar — do not "normalise" them without a reason. Local drift measured 2026-07-21: `justfile` carries an `export-notebooks` recipe; `CONTRIBUTING.md` has 2 customised lines; `docs/pages/how-to/contribute.md` **does not exist** (deleted for the curated set, and confirmed NOT resurrected by update since it is not `_skip_if_exists`-listed). **Its curated how-tos correctly document prek** — `uv run prek install -f` (`contributing.md:38`, `installation.md:89`), `uv run prek run --all-files` (`contributing.md:240`), commitizen labelled as a `commit-msg` hook — **fixed in v0.28.4 (PR #110, `842eedc`).** For several rounds this cell claimed they "still document pre-commit" and agents re-flagged it as needing a PR without grepping (the copies-drift trap this file warns about, sprung on this file itself). Verify by content: `grep -rn pre-commit docs/` finds only the `.pre-commit-config.yaml` filename and immutable CHANGELOG history, no stale commands. **Bespoke setup-uv workflows copier does not own:** `examples.yml`, `regenerate-datasets.yml`, `export-notebooks.yml`, `docs-deploy.yml` each run `astral-sh/setup-uv` — a CI-touching release must audit by content (not by the six templated filenames) and hand-pin/annotate them. `docs-deploy.yml` was missing from this cell until the v0.31.1 fan-out found it — **four** bespoke files, not three. The v0.29.6 uv-version-pin fan-out hand-pinned the setup-uv steps; the v0.31.1 Renovate fan-out added a `# renovate:` annotation above each bespoke setup-uv pin AND pinned `examples.yml`'s previously-bare `uv tool install nox` to `==2026.7.11` (a deliberate behavioural change, flagged for review) so the customManager can bump it. **`changelog.yml` carries a local `env: GIT_LFS_SKIP_SMUDGE: 1` on the `changelog` job plus a 3-line `# yohou-local:` comment — 5 of its 17 drifted lines, the rest being the usual digest and `version:` pairs. It sits between `runs-on:` and `steps:`, which is the trailing context of any hunk the template adds to that job, so it is the single most fragile local delta in a release touching `changelog.yml`.** It survived v0.42.0 intact; hand-check it, never bulk-accept. Same hazard shape as the `nightly.yml` `test_docstrings` parametrization below, which this repo has already lost once to hunk-bundling. **Its curated how-to is `contributing.md`, not the template's `contribute.md`** — so a release fixing the templated page is inert here, which is how yohou's release instructions still said `git tag` (unsigned) after v0.42.0 shipped a signature gate that would have blocked its next release. Fixed in the v0.42.0 fan-out. |
| yohou-nixtla | True | 2 notebooks. Its logos were destroyed by a past update and restored from `f166f46`; **never touch `docs/assets/`**. That restore was only half a restore, and the consequence went unrecorded until v0.42.0: `logo.png` and `favicon.png` are still byte-identical to the **template's generic placeholders**, only `logo_dark.png`/`logo_light.png` are this repo's own — and `_skip_if_exists` now **freezes** the two placeholders that way, so no future update will ever replace them. Real branding there needs a human. `_base.py` is `_`-prefixed, so `BaseNixtlaForecaster` reached the API only once `_get_root_members` landed (17→18 rows). Answers cap at `max_python_version: 3.13` — scipy ships no cp314 wheel. Known-flagged: inert `environments` key under `[tool.coverage.report]`, `lightning_logs` xdist race, `/en/stable/` 404 (no stable release yet). |
| yohou-optuna | True | 5 notebooks, all flat. Carries **16 custom skills / 37 files** under `.claude/skills/` that must stay tracked (this cell said 15/36 until the v0.41.1 round measured it; the extra is `polish-changelog`). (`plot_model_comparison_bar` **does not exist anywhere** — not here, and not in `yohou` either: it is absent from the installed `yohou` source tree. This cell has now been wrong about it twice, each fix confidently reassigning an owner instead of checking whether the symbol exists. Its only traces are two stale lines in this repo's mirrored `create-yohou-plot` skill, which also names `plot_residual_time_series` and `plot_score_per_horizon` against real exports `plot_residuals` / `plot_score_per_step` / `plot_score_summary`. Repo-owned staleness, not a fan-out concern; do not reassign it a third time.) |
| sklearn-wrap | True | 9 flat notebooks. `--extra config` is needed for **`ty`** and for **notebook execution during export**, but *not* for rendering: `check_docs` passes with pydantic absent because mkdocstrings uses griffe's static analysis. So `build_docs`/`build_steps` fail locally on `examples/yaml_config.py` while CI and RTD stay green — RTD's recipe passes the extra, the nox sessions never got it (`test_docstrings` already does, so the pattern exists locally). Pre-existing, verified identical on the prior tag. An earlier version of this table said the extra was "not for the docs build", full stop; that is wrong for the export leg. `test_docstrings` has **no matrix parametrization** here — a single ubuntu job on 3.11 — so do not go looking for one to preserve. Went RTD-red once from the v0.22.0 gallery bug. |
| sklearn-optuna | True | 9 flat notebooks. **See Also: 13 sections, 32 entries, 0 unlinked** — that is the whole useful fact. Do *not* re-add a breakdown of where those links point: this cell has carried three mutually contradictory versions (dependency-inventory resolution; 21 external to `docs.python.org`; 21 internal + 9 API + 2 external), each written confidently from a single agent's measurement, and a spot-check of a live page found 3 links all internal. Nothing in a fan-out turns on the answer. Carries `Sampler`/`Storage`, whose only member is `__init__` — filtered out — which makes it the fleet's test case for anything sensitive to *rendered* vs declared members. |
| **kedro-dagster** | **False** | No notebooks. Largest docstring surface (~126 See Also links). `docstring_options: {warn_unknown_params: false}` is **noise-critical, not CI-critical** — measured in the v0.41.2 round by a clean A/B in an isolated worktree, one tree, one nox env, only the key differing: **80** griffe warnings with it on, **0** with it off, and **exit 0, "No issues found", 98 pages either way**. This cell said 77 warnings and *fails the build*; both halves were wrong. Keep the key at `false` regardless — 80 lines of log noise is reason enough — but the real fix, if anyone wants it gone, is the pydantic docstrings, not the key. Snippets `base_path` must stay `[docs, .]`: it includes repo-root-relative `src/kedro_dagster/templates/*`. `datasets/` re-export layout. Renamed its page to **`troubleshoot.md`**, and keeps a `test-versions` job (with its `needs:`) that copier has deleted before — it lives in **`nightly.yml`**, as a `uses:` call to a dedicated **`tests-versions.yml`**, *not* in `tests.yml`; an agent grepping `tests.yml` per this file's old phrasing found nothing and briefly thought it had hit that exact loss. **No line number is recorded here on purpose**: it has been wrong three times running (:45, then :54, then :61 after v0.41.5 added lines above it), so locate it by name. **It is a reusable-workflow call with ZERO inline `steps`** — a job-list check that filters on step count drops it silently, which is the exact loss shape this cell exists to prevent. Its `test-compat` is also hardcoded `if: False`, so that check is permanently vacuous. Its curated `pages/reference/datasets.md` is the fleet's only multi-object `:::` page, which makes it the sole real test for anything about duplicate ids or per-object section stripping. Its `tests-versions.yml` `astral-sh/setup-uv` step is bespoke (copier does not own it) — a CI-touching release must hand-pin it; done in the v0.29.6 uv-version fan-out. |
| **kedro-azureml-pipeline** | **False** | No notebooks. `warn_unknown_params: false` is worth keeping — flipping it produces exactly **46** griffe warnings. The **46 is confirmed; the "and fails `--strict`" half is stale**: under zensical 0.0.51 the build prints all 46, then `No issues found`, exit 0. So it is noise-critical, not CI-critical. kedro-dagster's identical "77 warnings and now *fails* the build" claim is likely stale the same way and has not been re-measured. Its `inventories` is **the template default** (`docs.python.org` only), *not* a local extension — an earlier version of this table said it kept a local list, and an agent that went looking for one to preserve found nothing. `distributed/` re-export layout. Best index coverage in the fleet. Renamed its page to **`troubleshoot.md`**. `test_versions` matrix runs **10** jobs — 4 on 3.11, 4 on 3.12, 2 on 3.13, because 3.13 omits the `azure-ai-ml<1.20` pair. This cell said **12** for several releases; two independent fan-out agents measured 10 against byte-identical workflows, so the 12 was arithmetic rather than observation. Also: the ambient interpreter is 3.14, where **kedro raises `KedroPythonVersionWarning` on import**, so this package cannot be imported there despite `requires-python` having no upper bound — `check_docs` is pinned to 3.11 and unaffected. Answers cap at `max_python_version: 3.13`, but `requires-python` has **no upper bound** — see the interpreter note in §5. Its `test_versions` matrix lives in a bespoke `tests-versions.yml` with its own `astral-sh/setup-uv` step copier does not own — a CI-touching release must hand-pin it; done in the v0.29.6 uv-version fan-out. |

**`include_examples: False` is real and load-bearing.** For those two repos the gallery,
companion-notebook and `GALLERY:section` **substitution** machinery is Jinja-gated out of
their `docs_build/_markers.py` (7 `{% if include_examples %}` blocks), and
`docs_build/_notebooks.py` is not emitted at all. Not *entirely*, though — this file said
"entirely" and it is imprecise: `_MARKER_NAMES` (including `GALLERY`,
`COMPANION_NOTEBOOKS`, `EXAMPLES_FOR`) and the unhandled-marker regex stay **ungated** and
do render there. That is deliberate — it is the leftover-marker detector, and a stray
`<!-- GALLERY -->` in a no-examples repo should warn rather than render as blank space.
Do not "fix" it.
Any release that only touches example machinery is genuinely inert
for them — verify by diffing the two pristine renders rather than assuming either way.
If an update tries to introduce example content or an `Examples` nav entry there, that is
a template bug: report it, do not accommodate it.

## 2. Before dispatching

1. **The release must be TAGGED, not merged.** "Latest" means the newest *tag*. A repo
   whose `_commit` is ahead of the newest tag cannot update at all — it fails as
   `Downgrades are not supported`, not as a no-op. Verify the tag resolves and actually
   contains the change:
   `git rev-list -n1 vX.Y.Z` and grep the changed file out of `git show vX.Y.Z:<path>`.
2. **Any release that adds a generated file also changes `.claude/skills/update-from-template/references/file-classification.md`** (its update tier), and its `.github/skills/` twin — which is **gitignored in every repo**, so copier writes it to disk untracked and no one reviews it. List it in the brief; three v0.40.1 agents reported it as a delta item I had missed.
3. **Diff the two pristine renders across the version pair, per `include_examples` value.**
   This tells you what each repo will actually receive, and it is the only thing that makes
   a later "untouched!" result meaningful. Do it before writing the briefs.
4. **Give agents the expected DELTA, not an expected absolute count.** An absolute
   ("expect 56 symbols") goes stale the moment the repo merges anything: in one round a
   package merged a PR adding a public class between the fan-out's measurement and the
   agent's clone, so the brief said 56→57 and the agent correctly measured 57→58. Both
   were right; only the delta was durable. State the delta, name the symbols expected to
   appear or vanish, and tell the agent to re-derive its own baseline — an agent that
   trusts a stale absolute either reports a phantom regression or, worse, "fixes" it.
5. **Measure local drift in EVERY file the release touches, by CONTENT, before briefing.**
   Not the one file you think is risky, and never by line count. In the v0.28.4 round I
   compared `wc -l`, found three repos matching pristine exactly, and told their agents
   "no local drift to preserve" — while all three had differing content at identical line
   counts (two `justfile`s at 88 lines, a `CONTRIBUTING.md` at 29). Every repo in the fleet
   had drift in at least one touched file. Three agents caught it independently; a fourth
   then hit a real `UU` conflict in a file I had vouched for, which would have replaced a
   502-line curated page with copier's stub. Render pristine at each repo's own answers and
   diff — the same method §5 already prescribes for fork detection.

    And do not quote a drift COUNT as if it were canonical: the same file pair gives 178
    (git/Myers), 186 (git/histogram) and 272 (Python `difflib`) changed lines. Net line
    change agrees; the +/- total is algorithm-dependent. Counting drift estimates **risk**.
    Only a whole-file pre→post diff establishes **loss**.
6. **Write the per-repo briefs from THIS FILE, re-read now — not from working memory.**
   §1 is the corrected record; your recollection of it is a stale copy. In the v0.28.1 round
   I briefed kedro-azureml to "preserve its local `inventories` list" — a claim §1 already
   carried as *retracted*, with a note that an agent went looking and found nothing. The
   agent went looking again and found nothing again. Same for the root-export gap in §4,
   which I passed to an agent as an unfixed bug two releases after it was fixed. Both cost
   an agent real work, and both were one `grep` away. **A brief is a copy of this file's
   claims; copies drift.**
7. **Give each agent a scratch directory unique to its repo, and tell it to keep every file
   it writes inside that directory.** A unique directory is necessary but not sufficient:
   agents have still collided at the shared scratchpad root. One had a sibling overwrite its
   script mid-run, and the rewritten script cheerfully reported `LOST: NONE` — out of two
   empty lists. Another found a foreign script pointed at a different repo's clone and
   correctly refused to run it. Tell each agent to distrust any file it did not write.
8. **Do not assume the scratchpad is empty, and do not assume it is wiped.** It is *not*
   wiped between sessions — agents have found their previous clones intact, at the previous
   release's ref. That is the more dangerous direction: a stale clone updates from the wrong
   baseline and every later measurement is against a fiction. Have each agent clone fresh,
   and verify the ref it actually landed on rather than the ref it asked for. The work lives
   on GitHub, not on disk.
9. **`git show origin/main:...` in a local clone reads whatever that clone last fetched.**
   Read the baseline from GitHub, not from a working copy. In the v0.41.1 round I built the
   whole fan-out table by looping `git show origin/main:.copier-answers.yml` across the seven
   local clones **without fetching**, and got v0.40.0 for six of them. Every repo was actually
   on v0.40.1. The briefs then promised a two-release jump, ~20 action-pin conflicts and a new
   codeql file — none of which existed — and every drift number was measured against the wrong
   pristine render, inflating all of them. One agent caught it by re-deriving its own baseline,
   exactly as §2.4 tells them to; the other five were mid-flight and had to be corrected.
   `gh api "repos/OWNER/REPO/contents/.copier-answers.yml?ref=main"` is authoritative and takes
   one line per repo. I had already caught this same staleness once in the same session, on one
   repo, and fixed it there without generalising — which is how it survived to reach five briefs.
10. **Check where each repo's PR branch actually sits, not where `main` sits.** This fleet
   carries one long-lived `template-update/*` PR per repo whose branch name is frozen at the
   release that created it; the content advances every release while `main` stays behind. The
   branch name is not evidence of its version — read `_commit` from `.copier-answers.yml` on
   the branch and resolve it against the tag list.

## 3. What every repo must satisfy (the invariants)

**Template inefficiency — MOSTLY FIXED as of v0.41.5, and this paragraph was stale for
one release.** `nightly.yml` used to run `nox -s test_coverage` on every matrix entry while
that session is pinned to `PYTHON_VERSIONS[0]`, so the same suite ran once per entry and no
other interpreter was exercised; its Codecov upload was gated on a hardcoded `'3.12'` while
the report comes from the minimum version. yohou fixed all three locally, and **v0.41.5
adopted two of them upstream**: the `test_coverage`/`test` split by version, and the upload
re-gated onto the entry that produces the report. Measured on the fan-out: 3.12/3.13/3.14
now genuinely run their own interpreters, where before all entries re-ran the minimum.

Still local to yohou, and still worth preserving: its **parametrised
`test_docstrings-${{ matrix.python-version }}`** — the template emits a bare
`nox -s test_docstrings`. So "do not normalise yohou's `nightly.yml` toward the template's"
now applies to that one line and to yohou's comment wording, not to the whole file; in
v0.41.5 the file came out byte-identical, which is the correct outcome.
**That line is a live hazard on any release touching this file**: it sits immediately
between the two blocks v0.41.5 rewrote, and §4 records yohou having already lost it once to
hunk-bundling. Hand-check it; do not bulk-accept.


- The `docs_build/*.py` files are **Tier 1** — the `_markers.py`/`_glossary.py` markdown
  extensions, the `_see_also.py`/`_source_links.py` Griffe extensions, the shared
  `_git_ref.py`, and the `build.py`/`_api_pages.py`/`_notebooks.py`/`_markdown_export.py`
  build steps. Take the clean render, never a merge. Verify each is byte-identical to a
  fresh `copier copy` at the same ref. All six historical forks (of the former single
  `docs/hooks.py`) were eliminated by v0.20.0 and must not come back.
- **`git diff --stat -- docs/assets` is empty.** The only sanctioned exception in this
  fleet's history is yohou-nixtla's 2-file logo restore.
- `nox -s check_docs` passes with **0 warnings** (it builds `--strict`, notebooks skipped) —
  **but see §5: on this host that session is a vacuous pass and proves nothing.** Require a
  non-zero page count alongside the zero warnings, or take the result from CI.
- See Also: **0 BROKEN references** — not "0 unlinked". As of v0.29.2 a See Also target in
  a *dependency* package renders as plain code by design (`_see_also.py` cannot know at
  collection time whether an inventory will resolve it, and an unresolved autoref is fatal
  under `--strict`), so a green build legitimately shows a nonzero "unlinked" count — those
  are intentional foreign-package plain-code entries, not a regression (yohou-optuna trades
  ~2 such links). Audit for a `[text][target]` autoref that did NOT resolve, not for the
  absence of a link, and expect each block to render as a **flat single-level list**
  (v0.29.3 flattened hand-written `- [X] : desc` bullet See Also that used to nest). The
  absolute count is a measurement artifact — see §5.
- Every index links every one of its sibling pages.
- CI: report **how many checks RAN**, not just how many failed.

### Docs conventions (as of v0.23.0)

| page | convention |
|---|---|
| `docs/index.md` (home) | grid cards, **tailored per package** — leave alone |
| `pages/examples/index.md` | sectioned cards (`<!-- GALLERY -->`, or inline `<!-- GALLERY:section:… -->` per section) |
| `pages/{tutorials,how-to,reference,explanation}/index.md` | a **text list** of subpages, each with a one-line description — *not* cards, *not* tables |
| `pages/reference/api.md` (or `pages/api/index.md`) | frontmatter + H1 + one intro paragraph + `<!-- API_TABLE -->`, nothing else |
| nav order | `Home > Tutorials > How-to Guides > Examples > Explanation > Reference` — **Reference last**; `Examples` present iff the package has notebooks |
| companion card | after the prerequisites (and after any install section), before the first body section |

Group a section index under `##` headings only when it is big enough to need it — yohou's
35 how-tos earn it; 8 do not.

## 4. The hazards, all of which have fired

**Old build output stops being ignored.** The `.gitignore` entries for `site/`, `htmlcov/`,
`coverage.xml`, `.coverage`, `.nox/`, `.pytest_cache/` and `.ruff_cache/` collapse into one
`.artifacts/`. Whatever a previous build left at the root becomes untracked the moment the
update lands. Delete it; do not re-add ignore entries. A plain `git add -A` right after the
update will otherwise commit an entire built site.

This has already fired, and it fires in **maintainers' working clones, not in fresh ones** —
so a fan-out agent will not see it and will report the repo clean. `mkdocs.yml` now writes to
`.artifacts/site`, which is ignored; a root `site/` left over from before the consolidation is
not. Measured 2026-08-11 across the local clones: stale root `site/`, `.coverage`,
`coverage.xml` and `junit.*.xml` were sitting in several, and because `rumdl` runs
`rumdl check .` with `pass_filenames: false` and `[tool.rumdl] exclude` covers `.artifacts`
but not `site/`, **prek and pre-push failed on generated markdown in three repos** — blocking
commits that had nothing to do with it. The template is correct; the working copies are dirty.
Delete the stale output rather than adding excludes.

**A relocated file DESTROYS local content, silently.** `copier update` writes the file at
its new path **and deletes the old one itself** — no conflict, no `.rej`, no prompt. Measured
on yohou in the v0.41.0 round: two curated prose edits in `CONTRIBUTING.md` were destroyed by
the move and recovered only with `git show HEAD:CONTRIBUTING.md`. Nothing in the update's
output mentioned it.

This entry previously said the opposite — that the old copy is *left behind* as a duplicate,
so "carry the content over before deleting". There is no delete of yours to precede. An
earlier release did leave both copies, so **verify which happened** rather than assuming:

- After the update, `git show HEAD:<old-path> | diff - <new-path>`, and re-apply anything
  local the template's copy does not carry.
- If the old copy *did* survive, remove it — the consuming tool reads exactly one of the two
  and ignores the other without a word (GitHub reads `.github/CODEOWNERS` and never a root
  `CODEOWNERS`; Renovate loads one config).
- **Verify by grep, not `git status`.** An unresolved `.gitignore` conflict makes git omit the
  path from status entirely while the file sits on disk. This has fired before.
- Do not assume a relocated file is byte-identical to the template's just because it is
  Tier 1. This file claimed that on the strength of a `wc -l` sweep showing all seven repos
  at matching line counts — the exact mistake §2.5 warns about, made while writing the
  warning. yohou differed at an identical line count.

**`--conflict rej` MANUFACTURES the conflicts and destroys local content. Do not pass it.**
Copier's default is a three-way inline merge. The `update-from-template` skill prescribed
`--conflict rej` for years on the grounds that a `.rej` is easier to parse than markers
interleaved with content — reasoning about *reading* the outcome, which ignores what the two
modes do to the file. Measured in the v0.44.0 round on one repo, one release, same commit,
only the flag differing:

| | `--conflict rej` | default (inline) |
|---|---|---|
| `.rej` files | 5 | **0** |
| digest-pinned `uses:` lines | 49 → **26** | 49 → **49** |
| local `exclude:` block in `tests.yml` | **destroyed** | intact |
| tracked files changed | 7 | **2** |

`git apply --reject` is all-or-nothing **per hunk** and knows nothing of the merge base, so a
hunk carrying the template's change plus context lines the project legitimately edited fails as
a unit, and the template's version of everything that *did* apply lands. Inline does a real
three-way merge: where base, local and template agree it keeps the agreement, and it marks only
genuine divergence.

**The damage is not limited to what you would think to recount.** In one repo the reject mode
also replaced a live `Compat tests` pin set with the template's **disabled** placeholder and
dropped `lfs: true` from a checkout step. A digest recount reports those files clean. This is
why the rule is a whole-file pre→post diff and not a count of anything.

It also produced this round's most confusing result: one agent reported five `.rej` and a
49→26 digest revert while three others reported a spotless run on the same release, and the
difference was a flag one of them passed. **When two agents disagree about the same release,
compare their commands before theorising about their repos.**

**Copier destroys local content silently.**
- It **overwrites binaries every run**, regardless of diff — no conflict, no `.rej`, only a
  `Bin NNNN -> NNNN` line. This ate project logos for months. Only `_skip_if_exists`
  stops it; "Tier 3" is a convention for whoever *resolves* an update and is never reached.

    **`docs/assets/made_by_stateful-y.png` is deliberately NOT skip-listed, and reporting that
    as a gap is a known false positive.** The v0.42.0 fan-out flagged it: the skip list names
    four PNGs, the template ships five, and copier does overwrite the fifth on every run. Every
    word of that is true. The conclusion was backwards — it is the **org wordmark**, the
    template's asset rather than the project's, and skip-listing it would strand every project
    on whichever mark it was generated with. `test_project_branding_survives_a_second_template_run`
    has asserted exactly that, with the reason in a comment, since the logo fix landed.
    This is §5's "a deliberately narrow behaviour looks exactly like an incomplete fix", and it
    got as far as a written patch before the test's comment caught it. `copier.yml` now states
    the exclusion inline, and `test_every_shipped_binary_is_classified` requires each shipped
    binary to be either skip-listed or explicitly named template-managed, so a **new** binary
    still fails loudly while this one stops being re-reported.
- **The generated `tests/conftest.py` is effectively FROZEN. Any edit to it, including a
  comment, can rewrite a project's own imports.** Measured in the v0.41.4 pre-flight
  against real clones: inserting a comment block between the imports and the settings
  call left `def`/fixture names untouched but **replaced kedro-dagster's entire import
  header** -- its `# mypy: ignore-errors`, its `from __future__ import annotations`, and
  all sixteen of its scenario imports -- with the template's five-line stub. The file
  would not have imported. Reverting the conftest to byte-identical left it `UNCHANGED`
  in all four repos tested, with no `.rej`.
  Fleet conftests run 152 to 456 lines against the template's 25, so their import
  sections have no common ancestry with it and the header hunk rejects wholesale. If the
  template ever genuinely needs to change this file, pre-flight the update against every
  repo first and expect to hand-carry it, not diff it.
- **Moving a block within a template file is a whole-file rewrite, and it destroys
  divergent copies.** Measured in the v0.41.3 round: relocating a 15-line settings block
  from the middle of the template's `tests/conftest.py` to the end -- no content change,
  just position -- made `copier update` reject the entire file on a repo whose conftest
  had grown to 184 lines, reverting it to the 41-line template stub with 143 lines of
  local fixtures surviving only in a `.rej`. Reverting the move made the same update
  apply cleanly with no `.rej` at all, which is what identified the cause.
  This is the whitespace-tutorial hazard below with a different trigger, and it was
  introduced *by a fix for a lint warning*. Weigh the two failure modes before moving
  anything in a file projects customise: a lint error surfaces at staging and costs one
  line, a rejected hunk costs whatever the project had written.
- It applies an update as **a diff against the template's version**. Once a local file no
  longer resembles it, one shifted line rejects the whole hunk and the page reverts to the
  stub, content surviving only in a `.rej` nobody reads. A **whitespace-only** template
  change replaced a 244-line curated tutorial with a 74-line placeholder in one release.
- `_skip_if_exists` now covers the 4 logos, `docs/index.md`,
  `docs/pages/tutorials/getting-started.md`, `docs/pages/examples/index.md` and `CLAUDE.md`.

**A conflicted `.gitignore` hides the delivery you are verifying.** Fired on yohou in the
v0.38.0 fan-out. The project had added `reviews/` to the same block the template removed,
so `.gitignore` came out unmerged. Three independent signals said the repo was clean:

```text
copier update  -> exit 0
.rej sweep     -> no files
git status     -> the newly-delivered CLAUDE.md not listed
```

All three wrong. The unresolved `.gitignore` still contained `CLAUDE.md`, so git treated
the delivered file as **ignored** and omitted it from `status` -- while the file sat on disk
the whole time. Copier writes markers in place and leaves the file `UU`; it does not exit
non-zero and produces no `.rej` for that path. `.gitignore` is the one file whose own
conflicted content changes what `git status` reports, so it can conceal the delivery being
checked.

- Sweep for conflict markers as a **first-class check**, equal to the `.rej` sweep, not as
  a follow-up. `grep -rlE '^(<<<<<<<|>>>>>>>)' --exclude-dir=.git .`
- When `.gitignore` is among the changed files, **`git status` is not evidence of what was
  delivered.** Verify by path on disk and `git ls-files --error-unmatch <path>`.
- Resolve by keeping **both** intents. Here: the template's removal of its block, and the
  project's own `reviews/` entry moved to a section of its own with a comment saying why.
- **`mkdocs.yml` is NOT protected, and a nav-touching release clobbers it every time.**
  Not a risk — a certainty. v0.26.0 removed one nav line and the clobber fired in **7 of 7**
  repos: 227 curated nav leaves collapsed to 87. Once a repo's nav has diverged, the hunk
  rejects as a unit and copier falls back to the pristine nav wholesale, leaving the real
  one in a single `.rej`. Per repo: yohou 95→12, kedro-azureml 29→11, kedro-dagster 25→11,
  sklearn-wrap 24→16, sklearn-optuna 21→13, yohou-optuna 17→12, yohou-nixtla 16→12.
  **Every single clobber preserved correct section order and kept `Reference` last**, and
  several also injected a `configure.md` the repo does not have — a red `--strict` build.
  Order-checking passes all seven. Total-count checking passes several. **Only per-section
  counts catch it**, from parsed YAML, recorded *before* the update. yohou went further and
  diffed leaf-by-leaf, which is what you want on a big nav.
  Resolution is always `git checkout HEAD -- mkdocs.yml`, then hand-apply only what the
  template genuinely changed — usually nothing, and prove that by diffing
  `template/mkdocs.yml.jinja` across the pair rather than assuming.
- A **`.rej` holds the PROJECT's own changes** that could not be re-applied — not the
  template's. That is why local content goes missing and every conflicted file is
  partially applied.
- **A conflict does not always arrive as a `.rej`.** copier 9.17 delivered the same
  hazard as an inline git conflict — `pyproject.toml` in state `UU`, conflict markers in
  the file, **zero `.rej` files anywhere**. Two repos hit it in one round, both where the
  template appended a dependency onto the line a local entry already occupied. An agent
  sweeping only for `*.rej` sees a clean run and commits the markers. **Check
  `git status --porcelain` for `U` states as well as globbing for `.rej`**, and diff every
  touched file whole-file regardless of what either check says.
- **A `.rej` hunk that bundles a redundant change with load-bearing local work drops
  both, and the `.rej` count does not show it.** The unit of rejection is the hunk, not
  the line. yohou lost its `test_docstrings-${{ matrix.python-version }}` parametrization
  because the hunk also carried a now-redundant codecov bump — the bare session would have
  run 16 times against uninstalled interpreters. kedro-dagster lost its entire
  `test-versions` job and its `needs:` the same way, with no `.rej` of its own.
  yohou-optuna's `mkdocs.yml` hunk bundled the template's intended removal with 4 local
  entries: 5 vanished, the `.rej` showed 4. **Diff every touched file WHOLE-FILE against
  the pre-update baseline.** The update's own hunks always look innocent.
- **Every action pin must match what the fleet runs.** A pin the fleet does not run is not
  a stale version number: dependabot bumps the repo, so the gap becomes a permanent local
  delta copier replays on every release, and each replay is a chance to strand it. CI
  cannot catch it — the older version still works. v0.25.0 pinned `checkout` to the fleet's
  v7 and stopped there; the very next fan-out found the identical bug on `github-script` in
  four repos and `codecov` in another, because each repo's bump shared a hunk with its
  checkout bump and the hunk stopped applying once the template shipped v7 itself.
  `test_action_pins_are_consistent_and_current` now checks every action against
  `EXPECTED_ACTION_PINS` — it asserted only `checkout` while four other pins matched no repo
  alive, and stayed green throughout. `EXPECTED_ACTION_PINS` was **deleted** in v0.40.1
  (#269): Renovate reads the template's `uses:` refs directly, so a stale pin now arrives as
  a pull request instead of a silently-passing assertion.
- **THE FLEET IS DIGEST-PINNED AND THE TEMPLATE IS TAG-PINNED, so every `uses:` line
  conflicts on any release that bumps an action.** This is now the default shape of a
  fan-out conflict, not an edge case. Renovate's `helpers:pinGitHubActionDigests` rewrites
  each generated repo to `uses: owner/action@<40-hex> # v7`; the template ships `@v7`. The
  moment the template moves to `@v7.0.1`, that line matches neither side and rejects.
  v0.40.1 produced **20-22 inline conflicts per repo, in 8 files, with zero `.rej`** — in
  all seven repos at once.
  **Default: keep the LOCAL digest and discard the template's tag.** Digests
  are what the repo runs, what Scorecard's `PinnedDependenciesID` scores, and what Renovate
  maintains. Resolving toward the template silently un-pins the whole fleet. Do not add
  digests to anything new either — that is Renovate's job.

    **THE EXCEPTION, and it is not rare: when the template's action bump IS the payload, the
    local digest is the bug.** This rule read "always" for several releases and was wrong in
    v0.41.5, where the whole release existed to move `pypa/gh-action-pypi-publish` off v1.13.0
    — whose bundled twine < 7 rejected the `Metadata-Version: 2.5` that unpinned hatchling had
    started emitting, breaking PyPI publishing in **all seven repos at once**. Every local
    digest *was* v1.13.0. Obeying "always" produces seven fully green PRs that deliver nothing
    and leave the fleet unable to publish — this fleet's signature failure, at fan-out scale.
    Seven agents flagged it independently.
    So: keep the local digest **unless the release exists to move that action**, in which case
    re-pin to the new version's **dereferenced commit SHA**, preserving digest-pinning. The
    two cases are distinguishable only by asking what the release is *for* — v0.41.5 also
    bumped `actions/create-github-app-token`, where the default rule still applied. Before
    resolving, check what the local digest actually resolves to; if it is the version the
    release is fixing, keep it and you have shipped the bug.
    **Dereference annotated tags.** `gh api repos/OWNER/ACTION/git/ref/tags/vX.Y.Z` returns the
    **tag object**, not the commit — pinning that SHA pins something no workflow can check out.
    Use `repos/OWNER/ACTION/commits/vX.Y.Z`, or follow the tag object through `git/tags/<sha>`.
    **Resolve line-by-line, not hunk-by-hunk.** A single conflict block routinely bundles a
    digest revert *with* unrelated payload — in v0.41.5 `nightly.yml` carried the local
    codecov digest and the template's Codecov re-gate in one block, in at least four repos.
    Applying either rule to the whole block silently drops the other half.
    Consequence worth expecting: a workflow whose *only* template delta was the tag bump ends
    the update **byte-identical to before**. That is the correct outcome, not a failed update.
- **`uses:` is not the only local delta in a workflow — `astral-sh/setup-uv`'s `version:`
  input is a second one.** The template seeds `"0.10.0"`; Renovate has moved the fleet to
  `"0.12.1"`, at **13-17 sites per repo across five templated workflows**. Three agents
  independently caught a v0.40.1 brief that said the drift was "only `uses:` lines". Nothing
  broke, because the template did not touch those lines that round — but an agent resolving
  by regenerating a workflow from the pristine render rather than by editing conflict blocks
  would have reverted the uv pin in five files, silently. Audit both after any resolution.

**Docs fail by rendering nothing.**
- **Every link this hook emits is unvalidated, and that is where the bugs live.** `--strict`
  checks markdown links; it never sees raw HTML a hook injects. Three separate defects hid
  there: the gallery overflow link 404'd into RTD-red; every root export's API-table Module
  cell pointed at `pages/api/`, a directory with no index; and See Also was linkified only
  on `pages/api/generated/`, so a curated page rendered its entries as plain text while the
  same names linked on generated pages. That last one is the shape to remember — **it works
  everywhere anyone looked**. Check these by fetching the rendered links yourself.
- An unresolved marker renders as blank space; `--strict` never validated it. `check_docs`
  (v0.21.2) makes marker warnings fatal — that job is the only reason any of this is caught.
  **In CI. On this host it SOMETIMES catches nothing:** `zensical build -s` finishes in ~0.1s,
  writes an **empty `site/`**, and exits 0 — so `nox -s check_docs` returns "0 warnings" *with
  a deliberately broken link injected*. Root cause is inotify-instance exhaustion (128 limit),
  recorded in the Zensical notes; `--clean` does not help.
  **It is intermittent, not universal.** This entry said "on this host it catches nothing" and
  "every one of the seven v0.40.1 agents reproduced this", which was true of that round and
  wrong as a general claim. In the v0.41.1 round three agents measured it independently: one
  reproduced the vacuous pass, two got real builds (14.8s/39 pages, and 27.3s/98 pages) with
  inotify **over** the limit at the time. So exhaustion is not sufficient, and a real-looking
  build is not proof the host is healthy either.
  The consequence is unchanged and is the only part to rely on: **never accept "0 warnings" on
  its own**, because the failure and the success are indistinguishable without a count.
  So: a local `check_docs` pass is not evidence. Three things are —
  (a) assert the build emitted a **non-zero page count**, not just zero warnings;
  (b) re-run in a clean container (`python:3.13-slim` / `uv:python3.13-bookworm-slim`),
    where the same injected link correctly gives exit 1; or
  (c) take CI's `Docs build (strict)`, whose job log shows a real multi-second build and a
    real page count.
  This is the sharpest instance of the file's own rule: the checker was likelier to be
  wrong than the code, and it failed **silent and green**.
- **Hook-emitted raw HTML is invisible to `--strict`** — mkdocs never validates links inside
  it. The gallery overflow link 404'd into RTD-red this way; API-table `Name`/`Module` links
  have the same exposure. Only RTD's `post_build` linkchecker sees them, and CI does not run it.
  **`check_docs` can pass while RTD goes red.**
- `_get_submodules` skips `_`-prefixed modules, which silently excludes `__init__.py` too,
  so a public symbol exported only from the package root belongs to no submodule and once
  reached no page (yohou-nixtla: 17 rows against 18 names in `__all__`). **FIXED** by
  `_get_root_members` in `docs/_api_pages.py`, called at both generation sites and covered by
  a test that asserts the fixture actually has a root export so it cannot pass vacuously.
  This entry said "unfixed template bug" for two releases after the fix landed, while the
  fleet table three sections up said the opposite — and I repeated the stale half into a PR
  body and an agent brief before checking the code. **A recorded defect is a claim with a
  date on it.** Re-measure before repeating one, especially from this file.
- `__gallery__` assigned inside an `@app.cell` is invisible — `ast.iter_child_nodes` only
  sees module level. Both of yohou-nixtla's notebooks were in no gallery at all, silently.

**A GitHub SETTING is not a file, and a fan-out that only reads files cannot see it.** v0.42.0
shipped `renovate-automerge.yml`, whose approve step needs
`can_approve_pull_request_reviews`. That was set at the **org** level and three of the eight repos
carried an explicit repo-level `false` that the org value does **not** override
(python-package-copier, kedro-dagster, yohou-nixtla — **all three fixed on 2026-08-13; all eight
now read `true`, so do not re-report them, but DO re-read the setting rather than trusting this
sentence**). The workflow merged green in all eight, its
guard correctly declined on every human PR so the approve step never executed, and the 403 would
have surfaced days later on the first real Renovate PR — in the repo with the largest backlog. One
agent read the setting and found two; re-measuring all eight found three.

So: **when a release depends on a setting rather than a file, read that setting per repo and put the
values in the report.** An org-level value is evidence about the org default and nothing else. This
fleet has now been bitten by this class twice — see also the Dependabot dependency-graph blindness,
where the feature was "on" org-wide and 0 manifests were actually being scanned.

**A workflow with no `pull_request` trigger is verified by NOTHING in a fan-out.**
`nightly.yml` runs on `schedule` and `workflow_dispatch` only, so every green tick on every
PR proves its YAML parses, not that its steps work. v0.41.4 changed its Codecov step and
added `fail_ci_if_error: true` -- newly able to fail that job -- and seven green PRs would
have said nothing about it. Two agents flagged this rather than letting the green stand.
`gh workflow run <file> --repo OWNER/REPO --ref <pr-branch>` dispatches it on the PR branch
and gives real evidence in minutes; for v0.41.4 the log showed `CC_DISABLE_SEARCH: true`,
`CC_FILES: .../.artifacts/coverage.xml`, `Found 1 coverage files to report`. Do this
whenever a release touches a schedule-only workflow.

**But read the `on:` block; do not infer triggers from what appears in `gh pr checks`.** The
v0.42.0 brief told all seven agents that neither `changelog.yml` nor `publish-release.yml` has a
`pull_request` trigger. `publish-release.yml` has `pull_request: types: [closed]` on `main`. The
conclusion drawn from the false premise happened to be true — it never fires on `opened` or
`synchronize`, so it is absent from PR checks and unexercised by them — which is why six agents
repeated it without tripping over it. A wrong reason that yields a right answer is the brief error
that survives longest.

The consequence the false premise hid: **merging each fan-out PR fires that workflow.** It is
harmless here only because its `build` job is gated
`merged == true && contains(labels, 'changelog')` and a fan-out PR has no `changelog` label. Had
that `if:` been written slightly differently, seven merges would have cut seven releases. Two
workflows in this fleet can publish; check what a merge triggers, not just what a PR runs.

Corollary for the two release workflows specifically: **never dispatch `publish-release.yml` to
"verify" it.** It creates a GitHub Release and can reach PyPI. `changelog.yml` fires only on a
`v*.*.*` tag push, so exercising it means cutting a real release. Both are static-verification-only
in a fan-out, and the honest report says so.

**A pre-flight predicts destruction, not conflicts.** Running the update against clones of
all seven repos before tagging v0.41.4 correctly established that no conftest was harmed.
It also predicted `.rej`s in two repos and neither materialised, against the same tag and
the same `_commit`, unreconciled. The mechanism an agent gave for its own clean run is the
useful half: the template's hunk and the local edits sat on **different lines**, and
disjoint edits three-way merge without conflict -- a `.rej` needs a local edit on the lines
the template touches. Trust a pre-flight for *was anything destroyed*; treat its conflict
list as a list of things to check, never as a forecast.

**A merged PR accumulates more checks than an open one.** Comparing "how many checks RAN"
across rounds gave 33 on a merged PR against 32 on an open one in the same repo, which
reads as a silently shrinking check set. Benign: the four extra were release-path jobs
(`build`, `create-release`, `Publish the GitHub Release`, `Publish to PyPI`) that attach
only after merge. Compare open-to-open.

**Tooling lies.**
- **`gh pr edit` silently fails here** (GraphQL Projects-classic deprecation). Use
  `gh api -X PATCH repos/OWNER/REPO/pulls/N -f title=... -F body=@file` and **read it back**.
- **A CONFLICTING PR runs no Actions.** "0 failures" out of ~1 check is meaningless.
- **A DRAFT PR skips draft-gated jobs.** Many jobs in this fleet carry
  `if: ... pull_request.draft == false` (the full test matrix, compat, and the
  `tests-versions` matrix). On a draft PR they show `skipping`, so `gh pr checks` reports
  green over a thin subset — the heaviest jobs, and any job a CI-touching change most needs
  to exercise, never ran. Open PRs ready-for-review, not draft (see §7).
- **`gh pr checks` does not accept `--json` on this machine** — it exits with
  `unknown flag: --json`. An earlier version of this file called it a *silent* empty return;
  re-measured, it is a hard error, and the "empty result" agents watched for ~10 minutes was
  their own script swallowing stderr. Use the plain text form. So "0 checks" has two real
  causes — a conflicting PR runs no Actions, and a swallowed error — and neither is a pass.
- **`gh pr checks` also exits NON-ZERO while checks are still pending.** A poll loop that
  guards on exit status breaks out immediately and reports the partial state as final; mine
  did, on this release. Guard on the *output* (`grep -q pending`), not the exit code.
- **A workflow whose job-level `if` evaluates false still registers a check, as `skipping`.**
  Since v0.42.0 every repo ships `renovate-automerge.yml`, which triggers on `pull_request` and
  guards on Bot-author + `renovate/` branch + the `automerge` label. On any human PR that guard is
  correctly false, so **every fan-out PR from now on carries an extra
  `Approve and enable automerge  skipping` line**. Three agents flagged it in one round because the
  brief told them to expect the workflow to be *absent* from the check list; an agent hunting for a
  missing check finds a present one and has to work out which reading is wrong.
  It also **inflates the "how many checks RAN" tally** this file asks for two bullets down, which is
  the third hole in that number alongside `Compat tests` and `Validate Commit Message`. A `skipping`
  line here is the guard working, not firing.

    **But a workflow with NO `pull_request` trigger registers NO check at all — it is absent,
    not `skipping`.** These are two different outcomes and the v0.44.0 brief conflated them,
    which four agents corrected independently. `renovate-automerge.yml` triggers on
    `pull_request` with a false job guard, so it shows `skipping`.
    `drain-automerge-queue.yml` triggers only on `push` to `main`, so nothing appears for it
    anywhere. An agent told to expect a `skipping` line for it goes hunting for a workflow that
    was never going to be there, and may conclude the update dropped it.
    The rule: **derive the expected check list from each workflow's `on:` block**, not from the
    fact that a workflow exists in the tree.
- **`Compat tests` is hardcoded `if: false` in SIX of the seven repos** (yohou-optuna,
  yohou-nixtla, sklearn-optuna, sklearn-wrap, kedro-dagster, **kedro-azureml-pipeline** —
  `# disabled until pins are defined`), and the `ci-passed` roll-up treats `skipped` as
  acceptable. So its green covers a job that never runs in all but one repo. Five agents
  reported the `skipping` independently in one round, each having to establish it was
  pre-existing rather than a draft artifact. Record it here so the next round does not
  re-derive it: it is NOT draft-gating, and it is not something a fan-out introduced.

    **The count was "at least FIVE" and the list omitted kedro-azureml-pipeline; it is six.**
    Settled by reading all seven `tests.yml` files rather than by taking either agent's word:
    the kedro-azureml agent said six and was right, and yohou's said "one of the two repos
    where it is not `if: false`" and was wrong. **yohou is the only one that runs it**, and it
    ran and passed there on v0.42.0. A hedge like "at least five" reads as a fleet-wide fact
    and is exactly what stops the next round from checking.
- **`Validate Commit Message` does NOT skip on a multi-commit PR — it PASSES vacuously.**
  The `if: github.event.pull_request.commits == 1` is at **step** level, not job level, so
  the job reports `success` with all its real steps skipped. In `gh pr checks` that is
  indistinguishable from a real pass, and an agent watching for `skipping` to confirm the
  handoff will never see it. **Six agents measured this independently in one round.**

    The step-level gate is deliberate, and the workflow says why in its own comment: a
    job-level `if` reports *no* conclusion, which leaves a required status check stuck
    "waiting" and deadlocks the PR. The vacuous green is the price of making the job
    requireable.

    Two tells, since the check itself gives none: the **duration** collapses (28s with one
    commit, 2-4s with two), and the job log runs `Set up job` straight to `Complete job` with
    no step output. **It also inflates a "how many checks RAN" tally** -- it runs, and does
    nothing -- so that count, which this file asks for precisely because "0 failures" is
    meaningless, has the same hole in it.
    This entry said "flips from pass to skip, which is correct" — a green tick over an empty
    set, recorded as benign, which is this fleet's dominant failure shape. The substantive
    point is unchanged: with two commits GitHub
    takes the squash title from the **PR title**, which `pr-title.yml` validates instead.
    **This makes the PR title load-bearing for the changelog** — update it when you fold.
- **RTD 403s urllib's user-agent** — use `curl`. And in **yohou**, a green RTD preview is
  evidence of nothing about the PR: `.readthedocs.yml` does not build the docs at all, it
  `curl`s the `docs-site` release tarball that `docs-deploy.yml` publishes **from main**
  (Zensical needs ~8.6 GB and OOMs on RTD's ~1 GB limit). So every yohou PR preview serves
  main's content by construction. Verified on v0.40.1: RTD build pinned to the PR's exact
  commit returned 200 and served a page **without** the paragraph that PR added. §6's
  "fetch RTD state with curl" is a dead control there — use the container build's rendered
  `<article>` instead.
- **`pytest -p no:cacheprovider` now runs ZERO tests and reports success.** The generated
  `pyproject.toml` sets `cache_dir` under `.artifacts/`; disabling the cache plugin makes
  that option unrecognised and the run collapses before collection. An agent used the flag
  while falsifying a check, got "no failures", and nearly concluded the check was broken.
  Never add it, and assert a non-zero test count before believing any clean falsification.
- A stale `.rumdl_cache` gives a **false clean**. Delete it and re-run.
- Cached notebook exports (`.source_hash`) make a docs build **vacuous**. Clear
  `docs/examples/<stem>/` first — but never `rm -rf docs/examples`, which deletes a tracked
  `.gitkeep`.
- `git check-ignore` is silent for **tracked** files; use `--no-index` to test a rule.
- zsh does not word-split unquoted expansions — several "all clean" sweeps were empty-set
  bugs. Prefer Python over shell for any sweep whose result you intend to trust.
- **`grep -r --include=*.html` with the glob UNQUOTED returns 0 for everything.** zsh expands
  it against the *current directory* before grep sees it, so the filter matches nothing and
  every count comes back a confident zero. **Three separate agents hit this same line in the
  v0.28.1 round**, each on a different repo, each initially reporting a clean pass. All three
  caught it only from a stray "no matches found" on stderr. Quote the glob, or use Python.
  This is the single most repeated checker bug in the fleet's history — if a sweep reports
  zero, reproduce the zero against a deliberately injected instance before believing it.
- **Other sweep scoping traps from the same round**, all producing false all-clears: walking
  the whole repo and counting hits inside `.nox/` or `.venv/` site-packages (scope to
  `git ls-files`); comparing heading text without stripping Material's appended `¶`
  permalink; and an index-coverage check blind to a `<!-- SUBPAGES -->` marker the hook
  expands at build time, which read 0/5 on a page that is 5/5 in rendered HTML.

## 5. Verification discipline

**Falsify every check before trusting it.** In this fleet the checker is likelier to be
wrong than the code. Real examples, all of them a confident number over an empty set:
a See Also audit grepping `<h2>` when the markup is `<h3 id="see-also">`; a card counter
matching `gallery-card` when Material emits `grid cards`; a `tee | head` that SIGPIPE'd and
truncated the log *before the build ran*; a `pgrep` matching its own command line; a
readback that diffed an empty file because `gh` errored outside the repo.

**Measure the artifact that ships, not the one you edited.** A template defect lives in the
*rendered* file; the source can be correct and the render still wrong. v0.28.0 shipped four
overrides whose rendered form ended in a blank line, failing every generated project's
`end-of-file-fixer` and turning all seven repos red on one commit. It passed a 347-test
suite and my own pre-release verification, because every check read the source — which was
correctly one newline the whole time. I then "verified the fix" the same way and reported it
working when it was not in the tree at all.

The rule that would have caught it: **whenever a fix is about how something renders, the
check must open the rendered file.** And prefer a check that sweeps the whole rendered tree
over one that names the files you already suspect — the next instance will be elsewhere.
`tests/test_template.py::test_no_rendered_file_ends_in_a_blank_line` is that shape.

**A selector, glob, or guard that matches nothing is silent.** Three separate v0.28.0 defects
were of this kind: `h5.doc-section-heading` matched 0 elements after the class moved to an
inner span, so Material's default styling reasserted on 40 headings; `exclude_docs` had no
pattern for `.jinja`, so template source was served at 200; a `Methods` guard tested
`obj.members`, the pre-filter set, so 12 of 25 class pages got a heading introducing nothing.
None produced a warning and `--strict` saw none of them. **For anything expressed as a
pattern, count the matches on both sides** — how many elements have the class, how many files
the glob catches — and treat a zero as a failing measurement until proven otherwise.

**Copier renders a local template repo at its latest *tag*, not your working tree.** So
`copier copy /path/to/template` verifying an unreleased edit renders the *last release* and
reports, convincingly, that your change did nothing. This cost two wrong diagnoses in one
release: the fix was correct both times and the render was answering a different question.
`tests/conftest.py` passes `vcs_ref="HEAD"` for exactly this reason, and that form *does*
pick up uncommitted changes (that is what `DirtyLocalWarning` means — which the test suite
filters, so you will not see it). Pin `--vcs-ref` explicitly whenever you render.

**"Untouched" is not evidence.** If the template's render of a file is unchanged across the
version pair, it would have been untouched either way. Diff the pristine renders first
(§2.3); if identical, you have tested nothing.

**`copier update` does not recreate a locally-deleted file — *except* a skip-listed one,
which it recreates on every release.** `_skip_if_exists` means exactly what it says: skip
if it *exists*. Absent, copier copies it. v0.25.2 skip-listed `troubleshooting.md` to stop
it clobbering curated pages, and resurrected it in the three repos that had deleted or
renamed theirs — every update, forever, and where the stub's link target did not exist it
failed `--strict`. Three agents hit it independently; the control that settles it is same
baseline, same command, only the ref differs (v0.25.1 → not created, v0.25.2 → created).
An earlier version of this file stated the opposite, flatly, and it was wrong.

So skip-listing cuts both ways, and there is no copier setting that both protects a
curated page and respects its absence. When a page is wanted by some projects and unwanted
by others, the template should not ship it at all.

**Copier DELETES what the template removes.** Verified end to end: a customised 182-line
page was destroyed outright by a release that dropped it from the template. That is the
price of un-shipping something, and it is a one-time cost — a project restores its page
from git once, and the template then knows nothing about it, so no later update touches it
(also verified, on a run proven to have actually landed).

Because of the above, the delete-half of a two-way control **cannot** discriminate a
firing skip from a blind check. What does:
1. diff the pristine renders across the pair; identical ⇒ vacuous, and
2. **fork the template**, make a deliberate change to the file, update onto the fork, and
   confirm the customised file survives.
Binaries are the exception: copier rewrites them regardless of delta, so "the old version
overwrote it, the new one didn't" *is* a valid A/B on identical inputs.

**A deliberately narrow behaviour looks exactly like an incomplete fix.** Before reporting
a residue as a defect, read the function's docstring — in this repo the narrowness is
usually stated there. `_strip_redundant_section_titles` removes only the five section
titles the dispatcher maps to headings; `Yields`, `Warns` and friends keep theirs *on
purpose*, because that title is their only label. I briefed the v0.28.1 round with
"0 leftover `doc-section-title` spans" as a pass criterion, which is wrong: yohou correctly
keeps 10 and kedro-azureml keeps one (`Lifecycle`). Both agents refused to force the
number to zero and said why — the right call, and it means **a brief's acceptance criteria
are themselves claims to be checked**, not instructions to satisfy. Tell agents that
explicitly.

**A raw grep for any multi-token command against rendered HTML returns zero, always.**
Pygments wraps every space in `<span class="w"> </span>`, so `prek install -f` is never
contiguous in the source of a page that displays it perfectly. **Four agents reproduced
this independently in one round.** Strip tags or use `get_text()` before matching, and
assert non-zero — a bare zero here reads as "the bad form is absent, pass".

**Checking that N known patterns survived cannot detect loss of content you never
catalogued.** An agent verified five specific local `justfile` lines and reported them
intact; that proves nothing about a sixth it had not thought to list. The whole-file
pre→post diff is strictly stronger, metric-independent, and cheaper: if the only hunk is
the template's intended one, nothing local was lost regardless of how drift is counted.

**An anchored conflict-marker regex is a false-clean generator.**
`^(<<<<<<<|>>>>>>>|=======)$` matches only a bare `=======` and **misses**
`<<<<<<< HEAD` and `>>>>>>> theirs` — one of three injected markers caught. It fails in
the direction that matters: real conflicts slip through while the check reports clean.
Use `^(<<<<<<<|>>>>>>>|=======)( |$)`. This matters more since copier started delivering
conflicts inline rather than as `.rej` files. And when a sweep does hit a marker, check
whether the file is *documentation about* conflicts before reporting it — one repo's own
`update-from-template` skill contains marker examples in a prose table.

**Never falsify against a live working file.** An agent appended a synthetic conflict
marker to a real `pyproject.toml` to test its detector, then ran `git checkout` to clean
up — reverting the release's actual change along with the marker, and only noticing
because it grepped for the new content afterwards. Falsify against a scratch copy.

**`INFO -` is not a liveness probe for an mkdocs build log.** mkdocs emits nothing below
WARNING at default verbosity, so "I found INFO lines, therefore my grep works" proves
nothing about a WARNING pattern. Prove the format by injecting a real broken link and
resting the result on the demonstrated non-zero exit.

**A byte-identity comparison of built trees is coincidentally true before you commit.**
Generated member pages embed the commit SHA in their "View on GitHub" permalink, so a
tree diff taken pre-commit compares two builds at the same SHA and reads clean; after
committing, every generated page differs. Two agents hit this independently in one round
and both had to correct a "byte-identical" claim. Normalise every 40-hex SHA before
diffing — and falsify the normaliser against an injected content change, so it is not
just masking everything.

**A correct measurement does not validate the remedy you inferred from it.** A second
instance, from the v0.41.2 round, because it is the cleanest one yet. An agent correctly
diagnosed that the shipped path gate's `if "site" not in text` guard admitted a
`.readthedocs.yml` that publishes via a tarball, and proposed keying on the module's own
`_pattern_for("site/")` instead. The diagnosis was exactly right. The remedy was worse than
the bug: `(?<![\w./-])site/` cannot match `.artifacts/site/`, because the preceding slash is
in the lookbehind class -- so a *correct* file would have been skipped too and the assertion
would never have run on a healthy repo. It was validated against the skip case and never
against the pass case. **Test the remedy against the outcome it is supposed to preserve, not
only the one it is supposed to fix.**

**A correct measurement does not validate the remedy you inferred from it.** Two agents
measured, accurately, that declaring `griffe` pulls two extra distributions, and both
proposed `griffelib` instead. Neither checked what `griffelib` does in a project whose
mkdocstrings still resolves to griffe 1.x: that distribution *owns* the `griffe/` import
path which griffelib also provides, so the "fix" risks two distributions owning one path.
The diagnosis was right and the prescription was worse than the disease. **Test the
alternative's failure mode before recommending it**, and say which half you measured.

**Verify by rendering, not by reading.** Count in the built HTML, scoped to `<article>` —
the ToC sidebar inflates counts ~3×.
Do not derive See Also counts by splitting final HTML on newlines: mkdocstrings emits
multi-line `title=` attributes and the split cuts inside the tag, silently dropping entries.
**Never key a See Also audit on `<details class="see-also">`.** As of v0.28.0 there are
**zero** of them anywhere in a built site: the `admonition.html.jinja` override emits
`<div class="doc-section-item doc-admonition-see-also">` instead, and the See Also
cross-refs are now linked by the `_see_also.py` Griffe extension. Zero hits reads as a
clean pass and is total blindness.

**And `id="see-also"` is not the stable anchor either — this file said it was, and it
fails in the same silent direction.** Keyed on that heading alone, an agent measured a
confident 9 sections / 23 entries / 0 unlinked on sklearn-optuna and read it as a clean
pass. It finds only the *curated-page* form. Generated API pages render See Also as
`<div class="doc-admonition-see-also">` with no `id="see-also"` anywhere: 4 more sections
and 9 more entries, invisible. Counting both shapes gives 13 / 32 / 0, which is the
recorded baseline. Two agents hit this independently in one round -- the second on
kedro-dagster's `pages/reference/datasets.md`, where an id-keyed count reads zero.

This line has been wrong in both directions across three releases: first "no container
survives" stated unconditionally (false — curated pages kept theirs); then "three shapes,
one of them `details.see-also`" (true when written, falsified by v0.28.0 changing the
markup out from under it). kedro-dagster's curated `pages/reference/datasets.md` was the
example cited for the surviving container and is now the example of the new `div` form.
**Do not encode the current markup here again, and do not key on one anchor.** Discover
every shape: the two that exist today are an `id="see-also"` heading on curated pages and a
`doc-admonition-see-also` div on generated API pages, and a counter that knows only one of
them reports a clean pass over the half it cannot see. This is the same instruction the
paragraph below already gives -- write the audit shape-agnostic and abort on zero -- which
the deleted "stable anchor" sentence had been quietly contradicting.

The shapes still differ in ways a single-shape counter gets wrong — `<ul><li>` lists,
bare `<p>` for single-entry sections, and a wrapping `div` — so a naive counter collapses
each list to one entry or misses whole sections. Three agents in one release each reported
a confident false count (15, 17, 15 "unlinked") before going shape-agnostic. **Write the
audit shape-agnostic and make it abort on zero rather than report all-clear.**

One more vacuous-check trap, found four times independently in one release: **testing
`T201` against a `docs_build` module that holds no `print()` proves nothing** — the ignore
is scoped `docs_build/*.py`, but only the build-step modules (`_api_pages.py`,
`_markdown_export.py`, and the example-gated `_notebooks.py`) actually call `print()`; the
extensions like `_markers.py` contain zero, so against them the rule cannot fire and every
configuration looks clean. Test a rule that actually fires in the file you are checking, and
confirm with `--isolated` that the ignore suppresses a real finding.

**Do NOT drive a headless browser for the DataTables filter.** An earlier version of this
file said to, and every agent that read it dutifully installed one — seven browsers per
release, to re-verify the same code. DataTables is **pinned at 2.2.2** and jQuery at 3.7.1
in `mkdocs.yml`, the init script is emitted by `docs_build/_markers.py`, and `_markers.py`
is Tier 1 and already verified byte-identical everywhere. So the JS is pinned, template-owned and
identical in all seven repos. The `.dt-search` vs 1.x `#api-table_filter` incident that
produced that advice was agents using **1.x selectors against a 2.x pin** — a checker bug,
not a drift risk; the pin is the guard. Check it statically instead: `<table id="api-table">`
present, the init script emitted, the pinned CDN URLs returning 200 — and say plainly that
this does **not** prove the JS executes. That is the honest limit, and the right trade.
If the pin is ever bumped, that is when a real browser check earns its cost.

**`max_python_version` is not the interpreter constraint — `requires-python` is.** An
unpinned nox session takes the ambient interpreter, and whether that fails depends on the
project's `requires-python`, not on the answers file. yohou-nixtla (`>=3.11,<3.14`) failed
on a 3.14 machine; kedro-azureml-pipeline caps at `max_python_version: 3.13` in its answers
but has `>=3.11` with **no upper bound**, so the identical session ran fine on 3.14. Same
cap, opposite outcomes. `max_python_version` constrains `ALL_VERSIONS` and the classifiers;
it never reaches `uv sync`. Predicting one from the other produced a wrong brief once —
check the actual `requires-python` before claiming a session will fail.

**Prefer a no-op to churn.** If a repo already satisfies the change, say so plainly and
push nothing.

**A fan-out is the cheapest audit this fleet gets, and its findings are the point.** One
release's fan-out found four factual errors in *this file* — every one a claim an agent was
handed as fact and checked anyway. It also caught a bug in the release being shipped early
enough to fix upstream and fold into the same open PRs, so no repo ever carried a
workaround. **When an agent reports that this file is wrong, fix this file** — the next
release reads it.

## 6. Reporting

Require from each agent: the `docs/assets` diff **verbatim**; what each `.rej` held and how
it was resolved; per-page before→after with counts measured from rendered output; every
`check_docs` warning and its disposition; **how many CI checks RAN** and whether
"Docs build (strict)" passed; RTD state fetched with curl; and anything they could not
verify, flagged rather than asserted.

Tell them explicitly: **if a warning reveals a template bug rather than a repo bug, report
it and do not work around it locally** — a local patch to a Tier 1 file drifts forever and
undoes the fork elimination. Collect those, and cut a template release instead.

That instruction works, and it costs something. In the v0.28.0 round it split the fleet:
two repos left CI red and reported the bug; four normalised locally to go green and
disclosed it; the honest red ones were the more useful signal, and every local fix then had
to be reverted when v0.28.1 landed. **Say which you want.** Leaving it red is right when the
defect is fleet-wide and a fix is coming in the same session; patching locally is only worth
it when the repo would otherwise block on something unrelated.

## 7. Git hygiene for agents

- **`git add -A` FIRST, then run prek, then `git add -A` again.** prek only sees git-tracked
  files, so running it before staging silently skips every new file a release introduces —
  lint passes locally, and CI goes red on the exact files the release added. This fired in
  the v0.28.0 round; one agent caught it only from `gh pr create`'s "uncommitted changes"
  warning, after committing the pre-fix copies.
- **Never amend a pushed commit and never force-push.** An agent in the v0.28.0 round
  amended and `--force-with-lease`'d its own PR branch to correct the mistake above. The
  result was fine and the reasoning was sound, but it rewrote history other people and other
  agents may already have fetched, without anyone authorising it. Add a new commit instead;
  a slightly messy branch is cheaper than rewritten shared history.
- **Never `git stash` to park work.** `git stash --keep-index && git stash drop` destroyed a
  set of edits in this repo — the drop is unrecoverable and there is no confirmation. Commit
  to a scratch branch, or copy files aside.
- **Title the PR after the CHANGE, never after the mechanism.** "chore: update from
  template v0.41.1" tells a reviewer nothing about what is landing in their repo, and it
  is what every one of these PRs was called for years. Say what actually changes there:
  "refactor(layout): move build output to .artifacts/ and CODEOWNERS to .github/". Two
  reasons it is not cosmetic. A reviewer decides whether to read the diff from the title
  alone, and on a fan-out the diff is large and mostly mechanical. And **the title reaches
  the downstream changelog**: GitHub takes the squash title from the PR title on any
  multi-commit PR, so a repo whose release notes say "update from template" has lost the
  only record of what the release did to it. Update the title when you fold a later
  release into an open PR, for the same reason.
- **Push to the existing branch; do not open a second PR.** These are long-lived
  `template-update/*` PRs that advance across releases.
- **Open the PR ready-for-review, never draft.** "Held for review" means *do-not-merge*,
  stated in the body and left to the user — it does NOT mean draft. Draft PRs skip every
  `pull_request.draft == false` job (the full matrix, compat, `tests-versions`), which are
  the jobs a fan-out most needs to see green; a CI-touching change (e.g. pinning
  `tests-versions.yml`) is then verified by nothing but the YAML walker while the PR sits
  draft. Create with `gh pr create` WITHOUT `--draft`; if a PR already exists as a draft,
  `gh pr ready <N>` before reporting it done. Leave the actual merge to the user.
