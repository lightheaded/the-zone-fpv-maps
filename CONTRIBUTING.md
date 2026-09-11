# Contributing

## Licenses

- Code is Apache-2.0, see `LICENSE`.
- Assets (maps, textures, hero models) are CC BY 4.0, see `LICENSE-ASSETS`.
- Third party attributions are in `NOTICE`. See `docs/licensing.md` for the reasoning.

## Sign off

Every commit needs a Developer Certificate of Origin sign off:

```
git commit -s
```

The sign off states that you have the right to submit the work under the licenses above. See https://developercertificate.org/.

## Data sources

Say in the pull request which data you used. Allowed sources:

- Maa- ja Ruumiamet open data.
- Your own photos and measurements. Blur faces and license plates first.
- Maa-amet oblique photos, only after the project has written access. Ask first.

Not allowed:

- Files from The Zone game folder, including the Blender template and its textures.
- Google Street View, Google Maps or Google 3D content.
- Mapillary or other CC BY-SA imagery.

## Hero assets

Each hero model in `assets/hero/` needs a `.md` file next to it with the source: lidar, own photos, or Fotoladu photos, and the ETAK building ID that it replaces.
