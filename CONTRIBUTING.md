# Contributing

## Licenses

- Code is [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0), see `LICENSE`.
- Assets (maps, textures, hero models) are [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), see `LICENSE-ASSETS`.
- Third party attributions are in `NOTICE`. See `docs/licensing.md` for the reasoning.

## Sign off

Every commit needs a [Developer Certificate of Origin](https://developercertificate.org/) sign off:

```
git commit -s
```

The sign off states that you have the right to submit the work under the licenses above. See https://developercertificate.org/.

## Data sources

Say in the pull request which data you used. Allowed sources:

- [Maa- ja Ruumiamet](https://geoportaal.maaruum.ee/) open data.
- Your own photos and measurements. Blur faces and license plates first.
- [Maa-amet](https://geoportaal.maaruum.ee/) oblique photos, only after the project has written access. Ask first.

Not allowed:

- Files from [The Zone](https://store.steampowered.com/app/3491280/) game folder, including the [Blender](https://www.blender.org/) template and its textures.
- [Google Street View](https://www.google.com/streetview/), Google Maps or Google 3D content.
- [Mapillary](https://www.mapillary.com/) or other CC BY-SA imagery.

## Hero assets

Each hero model in `assets/hero/` needs a `.md` file next to it with the source: lidar, own photos, or [Fotoladu](https://fotoladu.maaamet.ee/) photos, and the [ETAK](https://geoportaal.maaamet.ee/est/ruumiandmed/eesti-topograafia-andmekogu-p79.html) building ID that it replaces.
