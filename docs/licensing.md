# Licenses, contributions and legality

Status: proposal. The maintainer decides before the first public push.

## Inputs

| Source | License | What we must do |
|--------|---------|-----------------|
| Maa- ja Ruumiamet geodata (buildings, lidar, elevation, orthophotos, ETAK, trees) | Maa- ja Ruumiamet open data license, 2025-01-01. Commercial use, derivatives and redistribution allowed. | Name the licensor, the data set and the data date in the map description, in `NOTICE` and in the README. Ship the license link with every distributed map. Example: "Elevation data 2024: Republic of Estonia Land and Spatial Development Board". |
| Maa-amet oblique aerial photos (Fotoladu) | Open data, attribution "Foto: Maa- ja Ruumiamet". Bulk access to verify. | Same attribution. Do not scrape the viewer without a written yes. |
| OpenStreetMap | ODbL. | Prefer ETAK. If OSM names or features are used, add "© OpenStreetMap contributors" and keep the produced map, which ODbL allows, but publish any derived database under ODbL. |
| The Zone Blender template and texture library | Proprietary, part of the game. | Never commit. Reference material names only. Collaborators copy the template from their own Steam install. |
| Google Street View, Google Maps 3D | Google terms forbid extraction and use as textures. | Reference viewing only by a human. Never in the pipeline. |
| Mapillary | CC BY-SA 4.0. | Textures derived from it must stay CC BY-SA. Keep them in a separate folder with their own license, or do not use them. |
| Own drone photos | Ours. | Blur faces and license plates before commit. |

## Outputs

Proposal, two licenses in one repository:

- Code (`pipeline/`, `docker/`, scripts): Apache-2.0. It has an explicit patent grant and a contribution clause.
- Assets (`assets/hero/`, textures, published `.glb` maps): CC BY 4.0, plus the Maa-amet attribution line. CC BY matches the Maa-amet license, which needs attribution only.
- `NOTICE` lists all third party attributions. The map description that the upload form in the game asks for repeats the Maa-amet line.

## Contributions

- Contributors sign off commits with the Developer Certificate of Origin (`git commit -s`). No contributor license agreement.
- A pull request template asks: which data sources did you use, and are you allowed to license the result under CC BY 4.0.
- Hero assets need a source note: modeled from lidar, from own photos, or from Fotoladu photos.

## Legality of the content

- Buildings: the Estonian Copyright Act allows reproduction of architectural works that stand permanently in public places, with the limit that the work is not the main subject of a commercial use. A free fan map is fine. A paid version needs a check for signature buildings such as ERM.
- Logos and signs: reproduce them as they appear in photos, at low resolution. Do not invent brand usage. Replace a logo if the owner asks.
- Personal data: faces and license plates never reach the repository. Orthophotos at 10 cm show no faces. Facades of private homes at low resolution are not personal data in practice, but a resident can ask for a blurred wall.
- Security sites: the prison, the military area at Raadi and the airport are in the public geodata and in the orthophoto. Build them from the same data. Do not add drone photos of them.

## Drone flights

Rules of the Estonian Transport Administration (Transpordiamet) for the EU open category, checked in September 2026.

- The Mavic 2 Pro has no class label and weighs 907 g. Since 2024-01-01 such a drone flies only in A3: 150 m from residential, commercial, industrial and recreational areas. It cannot do photogrammetry over the city. It can fly the Aardlapalu quarry, the river meanders and parts of the Raadi field.
- For the city, rent a C2 drone and fly in A2: 30 m from uninvolved people, 5 m in low speed mode. C2 drones with RTK: DJI Mavic 3 Enterprise EU. Other C2: Mavic 3 Pro, Mavic 4 Pro, Matrice 4E. C3: Matrice 350 RTK, which allows lidar payloads but flies only in A3.
- STS-01 needs a C5 drone. C5 kits exist for the Mavic 3 and Matrice 4. STS-01 permits flight over a controlled ground area in a populated environment, which fits a closed off site such as the laululava on a quiet morning.

Geographical zones near the clusters, from the open GeoJSON at https://utm.eans.ee/avm/utm/uas.geojson:

| Zone | Where | Effect | Contact |
|------|-------|--------|---------|
| EEGZ7, EEGZ8, EEGZ9 | Tartu airport FIZ, south of about 58.34 N | No open category flight over the airport. Below 30 m in EEGZ8, below 50 m in EEGZ9. Aardlapalu and the Ihaste bridge are inside EEGZ8 or EEGZ9. | Transpordiamet, LOIS |
| ZONE8 | The whole city, 58.37 to 58.46 N | Manned training area. Fly with caution. No permit. | |
| EER31 | Raatuse 110, Raadi | Defence Forces permit | lennuluba@mil.ee |
| EERZ107 | Turu 56 | Tartu prison, no flight | tartuv.info@just.ee |
| EERZ69 | Jaani tn | Internal Security Service, no flight. This is inside the old town, next to Jaani kirik. | kapo@kapo.ee |
| EERZ84 | Riia 132 | Police | ppa@politsei.ee |
| EER25, EER2610 | Sirgu, Luunja, east of Lohkva | Defence Forces, temporary until 2026-11-25 | lennuluba@mil.ee |

The Tartu Kliinikum heliport has no UAS zone in the current list. The general rule to stay away from helicopter operations still applies.

Permits: written application to the zone owner with the eleven data points that the general order lists. Decision within five working days. Airport zone flights above the limits need a special category authorization from Transpordiamet, which takes months. Operator registration costs 10 euros.

Effect on the plan:

- Annelinn and Lohkva: A2 with a rented C2 drone, no zone conflicts west of Sirgu. Good first scan site.
- Tähtvere and the laululava: A2, or STS-01 for the shell. The 330 kV substation is not a zone, but keep the distance that the operator Elering asks.
- Kesklinn: A2 is possible in most of the old town, but the Jaani tn zone cuts out the Jaani kirik block. Photogrammetry of the center is a summer morning job with many battery swaps and crowd management.
- Raadi: the ERM side is free, the Raatuse 110 side needs the Defence Forces permit.
- Aardlapalu and Ihaste: A3 with the Mavic 2 Pro is allowed, but only below 30 or 50 m.
