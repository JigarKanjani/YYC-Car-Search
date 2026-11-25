#!/usr/bin/env bash
# Install three third-party web/UI design skills for Claude Code, user-wide (~/.claude/skills),
# at upstream commits that were read and reviewed before being pinned here. Safe to re-run.
#
#   reactbits                hwj23016021425/reactbits-claude-skill  MIT (per its README)
#   motionsites-web-builder  Motionsites-AI/claude-skill            MIT; examples/ and media/ (c) MotionSites
#   unslop                   heydamir/unslop                        CC BY 4.0, credit Damir Sokolovsky
#                            (+ local security patch to scripts/story.mjs, noted in its INSTALLED_FROM)
#
# It also installs the ReactBits MCP server (npm reactbits-dev-mcp-server, pinned version and tarball
# hash), which the reactbits skill drives, into a fixed directory and registers it at user scope by
# absolute path. It is deliberately NOT registered as `npx ...`: npx resolves the package from the
# directory Claude Code starts in (and its parents), so a cloned project could supply its own code.
# GITHUB_TOKEN is not passed to the server (it only reads public files; this keeps tokens out of its logs).
#
# To update a skill: read the new upstream commit first, then change its pin below.
# Env: CLAUDE_SKILLS_DIR (default ~/.claude/skills), SKIP_MCP=1 to skip the MCP step.
set -uo pipefail

DEST="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
MCP_PKG="reactbits-dev-mcp-server@1.1.2"
MCP_SHA512="sha512-OKyzde7WN2Ppm9qnbomw+1zUhufSPb+xxdcb9+M4lcw9YNXotfRk5efb71CIkXh0B7Q4P3Dwu+1+p3bE6uBqCw=="
MCP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/claude-design-skills/reactbits-mcp"
GH="https://github.com"
# name | repository | pinned commit | skill folder inside the repository | license file ("-" = none)
SKILLS=(
  "reactbits|$GH/hwj23016021425/reactbits-claude-skill.git|5534dc92f6dc23e4c7c16351c97a064eef21fb82|.claude/skills/reactbits|-"
  "motionsites-web-builder|$GH/Motionsites-AI/claude-skill.git|a57e6d245ec4982fd804db5ac38711569bdfd094|plugins/motionsites-web-builder/skills/motionsites-web-builder|LICENSE"
  "unslop|$GH/heydamir/unslop.git|620163eedb3529d9cd23a3994ed8d287d06f760d|skills/unslop|LICENSE"
)

command -v git >/dev/null 2>&1 || { echo "git is required" >&2; exit 1; }
export GIT_TERMINAL_PROMPT=0   # fail instead of hanging on a credentials prompt if a repo is unreachable
TMP="$(mktemp -d)" || exit 1
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$DEST" || exit 1
failed=0

# Local security patch for unslop (audit finding: its story.mjs loopback file server answered any
# local process). Adds a per-run token that only the story browser sends; applied after the pin check.
patch_unslop() {
  git -C "$1" apply --unidiff-zero - <<'EOF'
--- a/skills/unslop/scripts/story.mjs
+++ b/skills/unslop/scripts/story.mjs
@@ -6,0 +7 @@
+import { randomBytes } from "node:crypto"; // local patch: per-run token for the story server
@@ -382,0 +384 @@
+const token = randomBytes(16).toString("hex");
@@ -383,0 +386 @@
+  if (request.headers["x-story-token"] !== token || request.headers.host !== `127.0.0.1:${server.address().port}`) { response.writeHead(403); return response.end(); }
@@ -414,0 +418 @@
+  await page.setExtraHTTPHeaders({ "x-story-token": token });
EOF
}

# Fetch one pinned commit, check it, and copy only the skill folder into place.
install_skill() {
  local name="$1" url="$2" sha="$3" path="$4" license="$5"
  local src="$TMP/src-$name" out="$TMP/out-$name" stage="$DEST/.$name.new.$$"
  git init -q "$src" || return 1
  git -C "$src" fetch -q --depth 1 "$url" "$sha" || return 1
  git -C "$src" -c advice.detachedHead=false checkout -q FETCH_HEAD || return 1
  [ "$(git -C "$src" rev-parse HEAD)" = "$sha" ] || { echo "$name: fetched commit is not $sha" >&2; return 1; }
  [ -f "$src/$path/SKILL.md" ] || { echo "$name: no SKILL.md at $path" >&2; return 1; }
  # Symlinks in fetched content could point the copy (or the writes below) outside the skill folder.
  [ -z "$(find "$src/$path" -type l -print -quit)" ] || { echo "$name: skill folder has symlinks" >&2; return 1; }
  if [ "$name" = unslop ]; then patch_unslop "$src" || { echo "unslop: local patch did not apply" >&2; return 1; }; fi
  cp -R "$src/$path" "$out" && rm -f "$out/LICENSE" "$out/INSTALLED_FROM" || return 1
  if [ "$license" != "-" ]; then
    [ -f "$src/$license" ] && [ ! -L "$src/$license" ] && cp "$src/$license" "$out/LICENSE" || return 1
  fi
  printf 'Installed from %s at commit %s\n' "$url" "$sha" > "$out/INSTALLED_FROM" || return 1
  [ "$name" != unslop ] || echo "Local patch: scripts/story.mjs story server requires a per-run token" >> "$out/INSTALLED_FROM"
  # Swap in only a complete copy, so a failed copy never leaves the skill missing or half-written.
  rm -rf "$stage" && cp -R "$out" "$stage" || { rm -rf "$stage"; return 1; }
  rm -rf "${DEST:?}/$name" && mv "$stage" "$DEST/$name"
}

# Install the pinned MCP package into MCP_DIR and check its tarball hash. Returns 2 if skipped.
install_mcp_package() {
  command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1 || return 2
  mkdir -p "$MCP_DIR" || return 1
  # Own package.json: npm treats MCP_DIR as the project root and never walks up to a parent project.
  [ -f "$MCP_DIR/package.json" ] || printf '{"name":"reactbits-mcp-runtime","private":true}\n' > "$MCP_DIR/package.json"
  (cd "$MCP_DIR" && npm install --prefix "$MCP_DIR" --ignore-scripts --no-audit --no-fund --save-exact "$MCP_PKG" >/dev/null) || return 1
  local got
  got=$(node -e 'const p=require(process.argv[1]).packages||{};process.stdout.write((p["node_modules/reactbits-dev-mcp-server"]||{}).integrity||"")' \
    "$MCP_DIR/package-lock.json") || return 1
  [ "$got" = "$MCP_SHA512" ] || { echo "$MCP_PKG: tarball hash mismatch ($got)" >&2; return 1; }
  [ -f "$MCP_DIR/node_modules/reactbits-dev-mcp-server/dist/index.js" ]
}

for entry in "${SKILLS[@]}"; do
  IFS='|' read -r name url sha path license <<< "$entry"
  if install_skill "$name" "$url" "$sha" "$path" "$license"; then
    echo "installed $name -> $DEST/$name"
  else
    echo "FAILED to install $name" >&2
    failed=1
  fi
done

if [ "${SKIP_MCP:-0}" != "1" ]; then
  if ! command -v claude >/dev/null 2>&1; then
    echo "claude CLI not on PATH: skipped the ReactBits MCP server" >&2
  else
    install_mcp_package; rc=$?
    if [ "$rc" = 2 ]; then
      echo "node/npm not on PATH (needs Node.js 18+): skipped the ReactBits MCP server" >&2
    elif [ "$rc" != 0 ]; then
      echo "FAILED to install $MCP_PKG into $MCP_DIR (existing MCP registration left unchanged)" >&2
      failed=1
    else
      entry_js="$MCP_DIR/node_modules/reactbits-dev-mcp-server/dist/index.js"
      claude mcp remove --scope user reactbits >/dev/null 2>&1
      if claude mcp add --scope user reactbits -e GITHUB_TOKEN= -e GITHUB_PERSONAL_ACCESS_TOKEN= \
          -- "$(command -v node)" "$entry_js" >/dev/null; then
        echo "registered MCP server reactbits (node $entry_js, user scope)"
      else
        echo "FAILED to register the ReactBits MCP server" >&2
        failed=1
      fi
    fi
  fi
fi

exit "$failed"
