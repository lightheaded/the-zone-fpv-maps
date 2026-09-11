# Instructions for coding agents and contributors

This file tells an AI coding agent, and a new contributor, how to work in this
repository. Read it before you change anything. `CLAUDE.md` points here.

## What this project is

Maps of real places for the FPV drone simulator [The Zone](https://store.steampowered.com/app/3491280/). One Python
pipeline turns open geodata into one glTF binary file per map. The first maps are of Tartu, Estonia, from
[Maa- ja Ruumiamet](https://geoportaal.maaruum.ee/) open geodata. The maintainer builds it as a long term hobby
project. Collaborators are welcome.

Read in this order: `README.md`, `docs/the-zone-format.md`, `docs/analysis.md`,
`docs/decisions.md`. `docs/locations.md` names the map tiles. `docs/licensing.md`
holds the license decisions.

## Four pillars

1. **Privacy of the maintainers.** Nothing in this repository identifies a maintainer
   beyond a GitHub handle. No real names, e-mail addresses, home addresses, phone
   numbers, employer names, device names, or local file paths that contain a user
   name. Write `$HOME/...` or `<game folder>` instead of an absolute path. This rule
   covers code, comments, docs, commit messages, issues, pull requests and build
   reports. Drone license details and flight logs of a person stay out too.
2. **Openness in everything else.** Decisions, sources, data dates, failed attempts
   and open questions go into `docs/`. Link the first mention of an external name in
   a document to its home page. Every published map carries the attribution from
   `NOTICE`.
3. **Sustainable code.** One pipeline for every map, driven by a TOML file in `maps/`.
   No manual steps that only one machine can repeat. The build must run on macOS,
   Windows and Linux, natively with `uv` and inside Docker. Prefer boring, well
   maintained libraries. Pin versions in `uv.lock`. The pictures follow the same rule:
   the pipeline renders the preview and the tour. Only an in-game screenshot needs a
   person, because the game has no free camera.
4. **High quality.** Tests for every module, and they run without network access.
   [ruff](https://docs.astral.sh/ruff/) clean. Small functions with docstrings that state units and axis order.
   Verify a claim about the game or the data before you write it down as a fact.

## Hard rules

- Never commit files from the game folder: no `template.blend`, no texture library,
  no official map files. Material names from the template are facts and are fine.
- Never commit `data/`, `dist/` or `tmp/`. They are in `.gitignore`.
- Never use Google Street View, Google 3D or Mapillary content. See `CONTRIBUTING.md`.
- Every commit needs a Developer Certificate of Origin sign off: `git commit -s`.
- Write prose in ASD-STE100 Simplified Technical English: short sentences, one
  instruction per sentence, no "should", no contractions. Code is exempt.
- Do not bypass git hooks.

## Conventions

- Coordinates: L-EST97 (EPSG:3301) in (east, north) order, heights in EH2000 meters.
  Game axes: X east, Y up, Z south. The map origin is the spawn point. `crs.py` is the
  only place that converts between them.
- Paths: `pathlib.Path` everywhere. Line endings are LF, enforced by `.gitattributes`.
- Configuration: one `maps/<name>.toml` per map. The map name is also the folder and
  file name in the game, so it is letters, digits, `-` and `_` only.
- Map names: every name starts with its city. `<city>` is the map of the whole city and
  `<city>-<place>` is a tile in it, for example `tartu` and `tartu-vaksali`. See
  `docs/decisions.md`.
- Data cache: `data/raw/<product>/<file>`. Downloads are skipped when the file exists.
- Output: `dist/<name>/<name>.glb` and `dist/<name>/build-report.json`. The report
  lists the source files and their dates for attribution.
- Logging: `rich` console in the CLI, plain return values in the library modules.

## Commands

```
uv sync                                        # install, first time and after pyproject changes
uv sync --extra tour                           # add the offscreen renderer of "tour"
uv run pytest                                  # tests, no network needed
uv run ruff check src tests && uv run ruff format src tests
uv run fpv-maps area maps/tartu-annelinn-test.toml   # bounding box and map sheets
uv run fpv-maps fetch maps/tartu-annelinn-test.toml  # download source data into data/raw
uv run fpv-maps build maps/tartu-annelinn-test.toml --install
uv run fpv-maps inspect dist/tartu-annelinn-test/tartu-annelinn-test.glb
uv run fpv-maps tour maps/tartu-annelinn-test.toml --publish   # tour pictures and a video
uv run fpv-maps shots maps/tartu-annelinn-test.toml <folder>   # import in-game screenshots
uv run fpv-maps gallery                        # the wiki index and map pages
docker compose run --rm pipeline build maps/tartu-annelinn-test.toml
```

## Releases: the commit message is the release note

A tag `vX.Y.Z` runs `.github/workflows/release.yml`. It builds every map in `maps/`
from the open data, writes the release notes from git history, runs the privacy gate
and publishes the GitHub release with the map files, previews and build reports.

`scripts/release-notes.sh` writes the release body. There is no separate notes step.

- The body of the `Release X.Y.Z` commit is the headline of the release.
- Every commit subject since the previous tag is one line of the TL;DR.
- Every commit body is one section of "What changed". An empty body prints
  "No description was written for this change." Do not let that happen.
- `Co-Authored-By` and `Signed-off-by` trailers are removed.
- Each map that the release **adds** gets a section with its preview and its first
  tour picture from `docs/screenshots/`, a link to its tour video in the assets, then
  the install steps and the attribution. A release page is
  a change list, so it does not repeat the maps of earlier releases. The assets hold
  every map in every release, and `docs/maps.md` is the inventory of them all.
- A new map needs a row in `docs/maps.md`, a preview and at least one tour picture in
  `docs/screenshots/` before the tag. The workflow refuses a map without them.
- The tour videos are not in git. `scripts/publish-tours.sh <tag>` uploads them to the
  release and pushes the wiki pages, after the workflow finished.

So every commit on `main` needs a subject that stands alone as a change list line,
and a body that explains the change to a reader who was not there. Reword `fix bug`
and squash bullet lists before they reach `main`.

Cut a release:

1. Build every map and copy `dist/<name>/<name>-preview.jpg` to `docs/screenshots/`.
   Render the tours: `uv run fpv-maps tour maps/<name>.toml --publish`.
   Add in-game screenshots with `uv run fpv-maps shots maps/<name>.toml <folder>`.
2. Set the version in `pyproject.toml` and `src/fpv_maps/__init__.py`, run `uv lock`.
3. Commit with the subject `Release X.Y.Z` and a body that says what the release is for.
4. Run `scripts/release-notes.sh` and read the result. It is the public page.
5. Tag with a signature, `git tag -s vX.Y.Z -m "Release X.Y.Z"`, and push the tag.
6. Watch the workflow. If the privacy gate stops it, delete the tag, reword, tag again.
7. Run `scripts/publish-tours.sh vX.Y.Z`. It uploads the tour videos to the release and
   pushes the wiki pages. The renderer needs a GPU, so a build agent cannot do it.
   The wiki must hold one page before the first run, and only a person can create it.

`scripts/check-privacy.sh` runs in CI over the tracked files and in the release over
the notes. It finds home paths, personal addresses, private network addresses and
internal host names. Public agency addresses are allowed.

## When you finish a change

1. Run the linter and the tests.
2. If you learned a fact about the game or the data, record it in `docs/`.
3. If you made a design decision, add it to `docs/decisions.md`.
4. Commit with `git commit -s`. Explain why in the message body.
