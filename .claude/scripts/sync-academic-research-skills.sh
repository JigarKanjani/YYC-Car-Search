#!/usr/bin/env bash
# Vendor Academic Research Skills (ARS) into this repo at a pinned upstream ref.
#
#   Upstream: https://github.com/Imbad0202/academic-research-skills  (CC BY-NC 4.0)
#   Usage:    .claude/scripts/sync-academic-research-skills.sh <40-hex-commit-sha>
#
# What it does:
#   1. Shallow-fetches exactly one upstream commit into a temp dir (no code is run from it).
#   2. Extracts only the runtime subset (the 5 skills plus the shared/, scripts/, docs/
#      files they reference) with `git archive`, so only tracked upstream files land here.
#   3. Refuses symlinks and any other non-regular entry, so upstream content can never pull
#      a host file into the repo.
#   4. Applies the local fixes in .claude/scripts/ars-patches/*.patch (fails if one no longer
#      applies: then check whether upstream fixed it and delete that patch).
#   5. Replaces .claude/academic-research-skills/ with that tree and records the commit.
#   6. Links each skill into .claude/skills/<name> and installs the sr-screener subagent.
#
# Review the resulting diff before committing: this is third-party content that Claude
# will follow as instructions and whose scripts it may run.
set -euo pipefail

REPO_URL="https://github.com/Imbad0202/academic-research-skills.git"
REF="${1:-}"

if [[ -z "$REF" ]]; then
  echo "usage: $0 <40-hex-commit-sha>" >&2
  exit 64
fi
# Only a full commit SHA pins the content: branches and tags move, and a short hex string
# can collide with an upstream branch name.
if [[ ! "$REF" =~ ^[0-9a-f]{40}$ ]]; then
  echo "error: ref must be a full 40-character lowercase commit SHA: $REF" >&2
  exit 64
fi

ROOT="$(git rev-parse --show-toplevel)"
CLAUDE_DIR="$ROOT/.claude"
DEST="$CLAUDE_DIR/academic-research-skills"
SKILLS_DIR="$CLAUDE_DIR/skills"
AGENTS_DIR="$CLAUDE_DIR/agents"
PATCH_DIR="$CLAUDE_DIR/scripts/ars-patches"
SKILLS=(academic-paper academic-paper-reviewer academic-pipeline deep-research sr-screener)

TMP="$(mktemp -d)"
trap 'rm -rf -- "$TMP"' EXIT

git -C "$TMP" init --quiet src
git -C "$TMP/src" fetch --quiet --depth 1 "$REPO_URL" "$REF"
SHA="$(git -C "$TMP/src" rev-parse --verify 'FETCH_HEAD^{commit}')"
[[ "$SHA" == "$REF" ]] || { echo "error: fetched $SHA, expected $REF" >&2; exit 1; }
COMMIT_DATE="$(git -C "$TMP/src" show -s --format=%cI "$SHA")"

# Runtime subset. Excluded: evals/tests/fixtures (17MB+ of CI data), design-spec archive,
# translations, the 840KB changelog, and the Pi/Codex/plugin-eval packaging.
INCLUDE=(
  "${SKILLS[@]}" shared agents commands hooks scripts docs examples .claude-plugin
  .claude/CLAUDE.md MODE_REGISTRY.md README.md QUICKSTART.md LICENSE NOTICE.md SECURITY.md
  GOVERNANCE.md POSITIONING.md CITATION.cff THIRD_PARTY.md
  requirements-dev.txt requirements-pdf-content-classifier.txt pyproject.toml
)
EXCLUDE=(
  ':(exclude)scripts/test_*' ':(exclude)scripts/fixtures' ':(exclude)scripts/**/tests'
  ':(exclude)scripts/adapters/examples' ':(exclude)docs/design' ':(exclude)docs/changelog-archive'
  ':(exclude)docs/*.zh-TW.md' ':(exclude)examples/showcase' ':(exclude)examples/pi'
)

mkdir "$TMP/out"
git -C "$TMP/src" archive --format=tar "$SHA" -- "${INCLUDE[@]}" "${EXCLUDE[@]}" \
  | tar -x --no-same-owner --no-same-permissions -C "$TMP/out"

# Upstream content is data. A symlink (or any other non-regular entry) could point at a host
# file, which the cp below or a later read would pull into the repo, so refuse the sync.
bad="$(find "$TMP/out" ! -type f ! -type d -print -quit)"
if [[ -n "$bad" ]]; then
  echo "error: upstream tree contains a non-regular entry: ${bad#"$TMP/out/"}" >&2
  exit 1
fi

# Local fixes for upstream defects found by the security audit. Each must apply cleanly.
PATCHES=()
if [[ -d "$PATCH_DIR" ]]; then
  command -v patch >/dev/null || { echo "error: 'patch' is required to apply $PATCH_DIR" >&2; exit 1; }
  for p in "$PATCH_DIR"/*.patch; do
    [[ -e "$p" ]] || continue
    patch -p1 --batch --forward --silent --no-backup-if-mismatch -d "$TMP/out" -i "$p" \
      || { echo "error: $(basename "$p") no longer applies at $SHA; check whether upstream fixed it" >&2; exit 1; }
    PATCHES+=("$(basename "$p")")
  done
fi

# Upstream's 88KB .claude/CLAUDE.md is kept for reference only, under a name Claude Code
# does not auto-load: each SKILL.md already repeats the routing core it needs.
mv "$TMP/out/.claude/CLAUDE.md" "$TMP/out/UPSTREAM_CLAUDE.md"
rmdir "$TMP/out/.claude"

for s in "${SKILLS[@]}"; do
  [[ -f "$TMP/out/$s/SKILL.md" ]] || { echo "error: $s/SKILL.md missing at $SHA" >&2; exit 1; }
done

cat > "$TMP/out/VENDORED.md" <<EOF
# Vendored: Academic Research Skills (ARS)

| | |
|---|---|
| Upstream | https://github.com/Imbad0202/academic-research-skills |
| Commit | \`$SHA\` ($COMMIT_DATE) |
| License | CC BY-NC 4.0 (see \`LICENSE\`); author: Cheng-I Wu. Non-commercial use only. |
| Synced with | \`.claude/scripts/sync-academic-research-skills.sh $SHA\` |
| Local patches | ${PATCHES[*]:-none} (from \`.claude/scripts/ars-patches/\`) |

This directory mirrors the upstream repository root (a runtime subset), so the
repo-relative paths the skills use (\`shared/...\`, \`scripts/...\`, \`docs/...\`,
\`MODE_REGISTRY.md\`) resolve from here. The five skills are linked into
\`.claude/skills/\` so Claude Code discovers them.

Not vendored: \`evals/\`, \`tests/\`, \`scripts/test_*\`, \`scripts/fixtures/\`,
\`docs/design/\`, \`docs/changelog-archive/\`, \`examples/showcase/\`, \`audits/\`,
\`plugin-evals*/\`, \`pi/\`, \`tools/\`, translations and \`CHANGELOG.md\`. Upstream's
\`.claude/CLAUDE.md\` is kept as \`UPSTREAM_CLAUDE.md\` (reference only, not auto-loaded).
The plugin hooks in \`hooks/\` and the \`/ars-*\` commands in \`commands/\` are kept for
reference but not wired in: they assume a plugin install (\`\${CLAUDE_PLUGIN_ROOT}\`).
Do not edit files here by hand; re-run the sync script instead. Fixes for upstream defects
live as patches in \`.claude/scripts/ars-patches/\` and are applied on every sync.
EOF

rm -rf -- "$DEST"
mv "$TMP/out" "$DEST"

mkdir -p "$SKILLS_DIR" "$AGENTS_DIR"
for s in "${SKILLS[@]}"; do
  rm -rf -- "${SKILLS_DIR:?}/$s"
  ln -s "../academic-research-skills/$s" "$SKILLS_DIR/$s"
done
agent_src="$DEST/sr-screener/agents/screening_reviewer_agent.md"
[[ -f "$agent_src" && ! -L "$agent_src" ]] || { echo "error: $agent_src is not a regular file" >&2; exit 1; }
cp --no-dereference -- "$agent_src" "$AGENTS_DIR/screening_reviewer_agent.md"

echo "ARS vendored at $SHA ($COMMIT_DATE) -> ${DEST#"$ROOT/"}"
