# the-zone-fpv-maps

Maps of real places for the FPV drone simulator The Zone. One reproducible pipeline turns open geodata into a map file that the game loads. The first maps are of Tartu, Estonia, built from Maa- ja Ruumiamet open geodata.

Status: planning. See `docs/analysis.md` for the feasibility study and `docs/locations.md` for the map tiles.

## Planned products

### Tartu

- `tartu-base`: the whole city at low fidelity, about 9 x 8 km. For orientation and long cruises.
- Detailed maps of 2 to 6 km² each: `annelinn-lohkva`, `tahtvere-vaksali`, `kesklinn`, `raadi`, and more. For freestyle and rehearsal.

## Data and attribution

Geodata: Republic of Estonia Land and Spatial Development Board (Maa- ja Ruumiamet), open data license 2025-01-01, https://geoportaal.maaruum.ee/opendata-licence. Full attribution lines are in `NOTICE`. Every published map carries them.

## Licenses

Code: Apache-2.0 (`LICENSE`). Assets: CC BY 4.0 (`LICENSE-ASSETS`). Reasoning in `docs/licensing.md`.

## Contributing

See `CONTRIBUTING.md`. Commits need a Developer Certificate of Origin sign off.
