#!/usr/bin/env bash
# Publish the tour videos and the wiki pages.
#
# The tour video of a map is 30 to 100 MB, so it never goes into git. It goes to the
# release as an asset. The wiki pages link the pictures from the repository and the
# videos from the newest release.
#
# The renderer needs an OpenGL 3.3 context, which a build agent does not have, so this
# script runs on a workstation after the release workflow finished.
#
#   scripts/publish-tours.sh v0.4.0              # videos and wiki pages
#   scripts/publish-tours.sh v0.4.0 --no-wiki    # videos only
#   scripts/publish-tours.sh v0.4.0 --wiki-only  # wiki pages only
#
# The wiki must exist before the first run. GitHub creates the wiki repository when a
# person saves the first page. Open the Wiki tab, save any page, then run this script.
set -euo pipefail

cd "$(dirname "$0")/.."

tag="${1:-}"
wiki=1
videos=1
for arg in "$@"; do
  case "$arg" in
    --no-wiki) wiki=0 ;;
    --wiki-only) videos=0 ;;
  esac
done

case "$tag" in
  "" | --*)
    echo "usage: scripts/publish-tours.sh <tag> [--no-wiki | --wiki-only]" >&2
    exit 2
    ;;
esac

if [ "$videos" -eq 0 ]; then
  echo "==> the videos are skipped"
fi

echo "==> render a tour for every map that has none"
for cfg in maps/*.toml; do
  # A private map is never published, so it gets no tour on the wiki and no video
  # in the release. A tour of it is a picture of an input that may not be
  # redistributed, or of a place that is not ours to show. See docs/licensing.md.
  if grep -q '^private = true' "$cfg"; then
    echo "==> $cfg is private, skipped"
    continue
  fi
  name=$(grep -m1 '^name = ' "$cfg" | sed -E 's/name = "(.*)"/\1/')
  if [ ! -s "dist/$name/tour/$name-tour.mp4" ]; then
    uv run fpv-maps tour "$cfg" --publish
  fi
done

if [ "$videos" -eq 1 ]; then
  echo "==> upload the videos to the release $tag"
  files=(dist/*/tour/*-tour.mp4)
  if [ ! -s "${files[0]}" ]; then
    echo "no tour video was found. Run 'uv run fpv-maps tour maps/<name>.toml' first." >&2
    exit 1
  fi
  gh release upload "$tag" "${files[@]}" --clobber
fi

if [ "$wiki" -eq 0 ]; then
  echo "==> the wiki pages are skipped"
  exit 0
fi

echo "==> write and push the wiki pages"
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

# The wiki is a second repository, and a fresh clone of it reads the global git
# identity. That can be another identity than the one of this repository, and a wiki
# commit is public. Copy the identity and the signing settings of this repository.
for key in user.name user.email user.signingkey gpg.format commit.gpgsign; do
  value=$(git config --get "$key" || true)
  if [ -n "$value" ]; then
    git -C "$work/wiki" config "$key" "$value"
  fi
done

# Every page is generated, so the wiki holds what the generator writes and nothing
# else. Without this, a renamed map keeps its old page in the wiki forever.
find "$work/wiki" -maxdepth 1 -name '*.md' -delete
cp dist/wiki/*.md "$work/wiki/"
git -C "$work/wiki" add -A
if git -C "$work/wiki" diff --cached --quiet; then
  echo "the wiki did not change"
  exit 0
fi
git -C "$work/wiki" commit -q -m "Update the map pages for $tag"
git -C "$work/wiki" push -q
echo "the wiki is published"
