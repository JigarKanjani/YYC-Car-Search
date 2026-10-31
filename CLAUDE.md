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
