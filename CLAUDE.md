# Project instructions

These are standing, pre-authorised rules. Follow them every time without being asked.
They are also enforced by a `UserPromptSubmit` reminder hook in `.claude/settings.json`.

## 1. Web development: always use the Hallmark skill

The [Hallmark](https://github.com/Nutlope/hallmark) design skill is installed at
`.claude/skills/hallmark`. For **any** web development or web design work in this
repo (new pages, landing pages, dashboards, UI components, HTML/CSS/JS front ends,
styling changes), invoke the skill first via the Skill tool (`hallmark`) before
writing code, and follow its Floor rules and run its `sloplint` check before
handing work back.

- New builds: `/hallmark <prompt>`
- Rework an existing page (only when asked): `/hallmark redesign <path>`
- Report only: `/hallmark audit <path>`
- Lint a page: `node .claude/skills/hallmark/scripts/sloplint.mjs <file-or-dir> --render`
  (browser checks need `puppeteer-core` and Chrome; static checks run without them)
- A `PostToolUse` hook already runs Hallmark's Floor check on edited HTML/CSS/component files.

## 2. After building any tool or software: always run the security audit

The [Cloudflare security-audit](https://github.com/cloudflare/security-audit-skill) skill is
installed at `.claude/skills/security-audit`. **Automatically, once a build is finished** (a new
app, tool, script, scraper, API, or a significant change to one), and before reporting it as done:

1. Invoke the `security-audit` skill via the Skill tool. The user has explicitly requested the
   audit after every build, so run it in **full audit mode**, not guidance mode.
2. Run the project's existing tests / a smoke run to stress the software (bad input, empty
   input, network failures, large inputs) and fix what breaks.
3. Fix every `confirmed` finding, re-validate, and summarise the findings (and anything left
   as `needs_validation`) in the hand-off message.

Keep audit artifacts out of version control unless asked (write them to a scratch dir).

## 3. Citing sources: always use Academic Research Skills (ARS)

[Academic Research Skills](https://github.com/Imbad0202/academic-research-skills) is vendored at
`.claude/academic-research-skills/` (pinned commit in its `VENDORED.md`), and its five skills are
linked into `.claude/skills/`. **Whenever work cites resources**, invoke the matching ARS skill via
the Skill tool before writing. That covers any answer, report, doc, README, code comment or other
deliverable that cites, quotes or lists sources; finding or recommending sources; building a
bibliography or reference list; fact-checking claims against sources; and checking or reformatting
existing citations. Pick the lightest mode that fits (modes: `MODE_REGISTRY.md` in the ARS folder):

| Task | Skill → mode |
|---|---|
| Find sources for a question, or a short cited answer | `deep-research` → `quick` (`full` for a full report) |
| Verify claims against sources | `deep-research` → `fact-check` |
| Literature review / annotated bibliography | `deep-research` → `lit-review` (`academic-paper` → `lit-review` for paper format) |
| Check, verify or fix a reference list | `academic-paper` → `citation-check` |
| Convert citation style or document format | `academic-paper` → `format-convert` |
| Write a paper / review a paper / run the full pipeline | `academic-paper` / `academic-paper-reviewer` / `academic-pipeline` |
| Screen studies for a systematic review | `sr-screener` |

- Never invent or guess a citation. Confirm each cited work exists (DOI, URL or index lookup)
  before giving it; label anything you could not confirm as unverified.
- Default to APA 7 unless the user or venue names another style.
- `deep-research` here means the ARS skill, not the account-level `anthropic-skills:deep-research`.
- Paths inside ARS files (`shared/…`, `scripts/…`, `docs/…`, `MODE_REGISTRY.md`) are relative to
  `.claude/academic-research-skills/`, not this repo's root.
- Don't hand-edit the vendored files. To update, run
  `.claude/scripts/sync-academic-research-skills.sh <commit-sha>`, review the diff, and run the
  rule 2 audit on it.
- ARS is licensed CC BY-NC 4.0: non-commercial use only, keep the attribution.
