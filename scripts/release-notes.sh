#!/bin/bash
# Write the GitHub release body for a tag to stdout.
#
# Usage: scripts/release-notes.sh v0.1.0 [previous-tag]
#        scripts/release-notes.sh              # preview the pending release from HEAD
#
# The notes come from git history. Commit subjects since the previous release tag
# become the TL;DR, and commit bodies become the "What changed" section. There is
# no separate release-notes step: the commit message is the release note. See
# AGENTS.md, Releases.
#
# The maps section names the maps that the release adds, because a release page is
# a change list. The inventory of every map is docs/maps.md. The release assets
# hold every map, new or not.
#
# The `Release X.Y.Z` commit is not a change. Its body is the headline of the
# release, and it stays out of the two lists.
#
# Preview the notes before you tag. Every commit body goes onto a public page.
# The release workflow runs scripts/check-privacy.sh over the result.
set -euo pipefail
cd "$(dirname "$0")/.."

version=$(grep -m1 '^version = ' pyproject.toml | sed -E 's/version = "(.*)"/\1/')
tag="${1:-v$version}"
repo_url="https://github.com/lightheaded/the-zone-fpv-maps"

# Preview from HEAD before the tag exists, and from the tag after it does.
if git rev-parse -q --verify "refs/tags/$tag" >/dev/null; then
  ref="refs/tags/$tag"
else
  ref=HEAD
fi
# Peeled to the commit. A signed tag is an object of its own, and its hash is not
# a commit hash.
ref=$(git rev-parse "$ref^{commit}")

# The previous release tag, taken from the parent so that the tag cannot describe
# itself. Without one, the last 30 commits stand in. The whole history is not a
# release note.
prev="${2:-$(git describe --tags --abbrev=0 --match 'v[0-9]*' "$ref^" 2>/dev/null || true)}"
if [ -n "$prev" ]; then
  range=("$prev..$ref")
  echo "release-notes: describing $prev..$tag" >&2
else
  range=(--max-count=30 "$ref")
  echo "release-notes: no earlier v* tag is reachable. Describing the last 30 commits." >&2
fi

# Useful in git history, not useful to somebody who reads a release page.
strip_trailers() {
  grep -vE '^(Co-[Aa]uthored-[Bb]y|Claude-Session|Signed-off-by|Signed-Off-By):' |
    awk '{ if ($0 ~ /^[[:space:]]*$/) { blank++ } else { while (blank-- > 0) print ""; blank = 0; print } }'
}

sha=$(git rev-parse --short "$ref")

# The release commit says what the release is for. Nothing else in the history
# does, because every other commit describes one change.
headline=""
if git log -1 --format='%s' "$ref" | grep -qE '^Release [0-9]'; then
  headline=$(git log -1 --format='%b' "$ref" | strip_trailers)
fi

# A `Release X.Y.Z` subject is a version bump and reads as noise in a change list.
changes=$(git log --no-merges --format='%H' "${range[@]}" | while read -r c; do
  git log -1 --format='%s' "$c" | grep -qE '^Release [0-9]' || echo "$c"
done)

tldr=""
details=""
for c in $changes; do
  subject=$(git log -1 --format='%s' "$c")
  body=$(git log -1 --format='%b' "$c" | strip_trailers)
  # A body that opens with a bullet is a squash body that nobody reworded.
  case "$body" in
    '* '*) echo "release-notes: WARNING: $(git rev-parse --short "$c") has a squash bullet list as its body. Reword it before you tag." >&2 ;;
  esac
  tldr+="- $subject"$'\n'
  details+="### $subject"$'\n\n'
  if [ -n "$body" ]; then
    details+="$body"$'\n\n'
  else
    details+="No description was written for this change."$'\n\n'
  fi
done

# The API caps a release body at 125000 characters. The TL;DR stays whole, because
# it names every change. The detail is what gets cut, and the note says so.
detail_cap=90000
if [ "$(printf '%s' "$details" | wc -c)" -gt "$detail_cap" ]; then
  details="$(printf '%s' "$details" | head -c "$detail_cap")

The detail is cut here, because it passed the size that a release page holds.
Every change is named in the TL;DR above. \`git log $prev..$tag\` holds the rest."
fi

echo "The Zone FPV maps $tag, built from \`$sha\`."
if [ -n "$headline" ]; then
  echo
  echo "$headline"
fi

# One section per map that this release adds, with its preview image at this tag.
# A release page is a change list, so it names the new maps only. `docs/maps.md`
# is the inventory of every map. The assets below hold every map in either case,
# because a reader who wants one map must not need to find an older release.
if [ -n "$prev" ]; then
  new_maps=$(git diff --name-only --diff-filter=A "$prev" "$ref" -- 'maps/*.toml' || true)
else
  new_maps=$(git ls-tree --name-only "$ref" maps/ | grep '\.toml$' || true)
fi

echo
if [ -n "$new_maps" ]; then
  echo "## New maps in this release"
else
  echo "## Maps"
  echo
  echo "This release adds no map. It rebuilds every map of the repository from the"
  echo "open data, so the assets below are current."
fi
echo
for cfg in $new_maps; do
  # A map that the release adds and a later commit deletes is not in the tree.
  [ -f "$cfg" ] || continue
  name=$(grep -m1 '^name = ' "$cfg" | sed -E 's/name = "(.*)"/\1/')
  description=$(grep -m1 '^description = ' "$cfg" | sed -E 's/description = "(.*)"/\1/')
  echo "### $name"
  echo
  echo "$description"
  echo
  echo "Download \`$name.glb\` below. The map folder in the game is \`custom_maps/$name/\`."
  echo
  if [ -f "docs/screenshots/$name-preview.jpg" ]; then
    echo "![$name from above]($repo_url/raw/$tag/docs/screenshots/$name-preview.jpg)"
    echo
  fi
  # The tour of the map: the first rendered shot, and the video asset of this release.
  tour_shot=$(ls docs/screenshots/"$name"-tour-*.jpg 2>/dev/null | head -1 || true)
  if [ -n "$tour_shot" ]; then
    echo "![$name, from the rendered tour]($repo_url/raw/$tag/$tour_shot)"
    echo
    echo "The tour video is \`$name-tour.mp4\` in the assets below. Every shot of it is on"
    echo "the [wiki gallery]($repo_url/wiki/Map-tours)."
    echo
  fi
  for shot in docs/screenshots/"$name"-ingame-*.jpg; do
    [ -f "$shot" ] || continue
    echo "![$name in the game]($repo_url/raw/$tag/$shot)"
    echo
  done
done

echo "The assets below hold every map of the repository, not only the new ones."
echo "\`docs/maps.md\` lists them all with their size, their area and their source data."
echo

if [ -n "$tldr" ]; then
  echo "## TL;DR"
  echo
  printf '%s' "$tldr"
  echo
  echo "## What changed"
  echo
  printf '%s' "$details"
else
  echo "No change landed since $prev. This release republishes the same maps."
  echo
fi

cat <<'INSTALL'
## Install

1. Download the `.glb` file of a map from the assets below.
2. Open the game folder. Steam: right click The Zone, Manage, Browse local files.
3. Create the folder `custom_maps/<name>/` and put `<name>.glb` in it. The folder name
   and the file name must be equal. Example: `custom_maps/annelinn-test/annelinn-test.glb`.
4. Start the game, open Play Offline and pick the map from the custom maps.

Each `<name>-build-report.json` lists the source data files and their dates.

## Attribution

The maps are CC BY 4.0. They contain data from the Republic of Estonia Land and Spatial
Development Board (Maa- ja Ruumiamet), open data license 2025-01-01:
https://geoportaal.maaruum.ee/opendata-licence. See NOTICE in the repository for the
data sets and years. If you share a map, keep this attribution with it.
INSTALL
