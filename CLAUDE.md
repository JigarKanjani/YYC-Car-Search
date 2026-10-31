# Project instructions

## Web development: always use the Hallmark skill

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
