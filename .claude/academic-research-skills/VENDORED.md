# Vendored: Academic Research Skills (ARS)

| | |
|---|---|
| Upstream | https://github.com/Imbad0202/academic-research-skills |
| Commit | `2e02041a3b821a160d98c9398f173c484ac759a8` (2026-11-02T15:27:50+08:00) |
| License | CC BY-NC 4.0 (see `LICENSE`); author: Cheng-I Wu. Non-commercial use only. |
| Synced with | `.claude/scripts/sync-academic-research-skills.sh 2e02041a3b821a160d98c9398f173c484ac759a8` |

This directory mirrors the upstream repository root (a runtime subset), so the
repo-relative paths the skills use (`shared/...`, `scripts/...`, `docs/...`,
`MODE_REGISTRY.md`) resolve from here. The five skills are linked into
`.claude/skills/` so Claude Code discovers them.

Not vendored: `evals/`, `tests/`, `scripts/test_*`, `scripts/fixtures/`,
`docs/design/`, `docs/changelog-archive/`, `examples/showcase/`, `audits/`,
`plugin-evals*/`, `pi/`, `tools/`, translations and `CHANGELOG.md`. Upstream's
`.claude/CLAUDE.md` is kept as `UPSTREAM_CLAUDE.md` (reference only, not auto-loaded).
The plugin hooks in `hooks/` and the `/ars-*` commands in `commands/` are kept for
reference but not wired in: they assume a plugin install (`${CLAUDE_PLUGIN_ROOT}`).
Do not edit files here by hand; re-run the sync script instead.
