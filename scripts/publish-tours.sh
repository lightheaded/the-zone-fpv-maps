#!/usr/bin/env bash
# Publish the tour videos and the wiki gallery page.
#
# The tour video of a map is 30 to 100 MB, so it never goes into git. It goes to the
# release as an asset. The wiki page links the pictures from the repository and the
# videos from the newest release.
#
# The renderer needs an OpenGL 3.3 context, which a build agent does not have, so this
# script runs on a workstation after the release workflow finished.
#
#   scripts/publish-tours.sh v0.4.0            # videos and the wiki page
#   scripts/publish-tours.sh v0.4.0 --no-wiki  # videos only
#
# The wiki must exist before the first run. Open the Wiki tab of the repository and
# create the first page, then run this script.
set -euo pipefail

cd "$(dirname "$0")/.."

tag="${1:-}"
wiki=1
for arg in "$@"; do
  [ "$arg" = "--no-wiki" ] && wiki=0
done

if [ -z "$tag" ] || [ "$tag" = "--no-wiki" ]; then
  echo "usage: scripts/publish-tours.sh <tag> [--no-wiki]" >&2
  exit 2
fi

echo "==> render a tour for every map that has none"
for cfg in maps/*.toml; do
  name=$(grep -m1 '^name = ' "$cfg" | sed -E 's/name = "(.*)"/\1/')
  if [ ! -s "dist/$name/tour/$name-tour.mp4" ]; then
    uv run fpv-maps tour "$cfg" --publish
  fi
done

echo "==> upload the videos to the release $tag"
videos=(dist/*/tour/*-tour.mp4)
if [ ! -s "${videos[0]}" ]; then
  echo "no tour video was found. Run 'uv run fpv-maps tour maps/<name>.toml' first." >&2
  exit 1
fi
gh release upload "$tag" "${videos[@]}" --clobber

if [ "$wiki" -eq 0 ]; then
  echo "==> the wiki page is skipped"
  exit 0
fi

echo "==> write and push the wiki page"
uv run fpv-maps gallery
remote=$(git remote get-url origin)
wiki_remote="${remote%.git}.wiki.git"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

if ! git clone --quiet --depth 1 "$wiki_remote" "$work/wiki"; then
  echo "the wiki of this repository does not exist yet." >&2
  echo "Open the Wiki tab, create the first page, then run this script again." >&2
  exit 1
fi

cp dist/wiki/*.md "$work/wiki/"
git -C "$work/wiki" add -A
if git -C "$work/wiki" diff --cached --quiet; then
  echo "the wiki page did not change"
  exit 0
fi
git -C "$work/wiki" commit -q -m "Update the map tours for $tag"
git -C "$work/wiki" push -q
echo "the wiki page is published"
