# Licenses, contributions and legality

Status: proposal. The maintainer decides before the first public push.

## License TL;DR

### Maa-amet geodata (buildings, lidar, elevation, orthophotos, ETAK, trees)

- Can: use, change, combine, sell, and redistribute. Publish the maps, the textures cut from orthophotos, and the raw tiles.
- Cannot: drop the attribution. Cannot present the data as official or endorsed.
- Implications: every map upload, the README and `NOTICE` carry one attribution line per data set with the data year. The license link ships with the data. Nothing else is required. The license is compatible with CC BY and with Apache-2.0 outputs.
- Alternatives: none needed. This is the best source. OpenStreetMap is the fallback for missing features, with its own rules below.

### Maa-amet oblique aerial photos (Fotoladu)

- Can: use the photos as textures with the line "Foto: Maa- ja Ruumiamet".
- Cannot: bulk download today. The viewer has no export. Scraping the tiles is not forbidden by the license, but it is not an offered service, and the Chancellor of Justice review of 2025 makes the future uncertain.
- Implications: ask for bulk access in writing before any script touches the viewer. Plan the first release without these photos.
- Alternatives: own drone and ground photos of hero buildings, procedural facades.

### OpenStreetMap (ODbL)

- Can: use names, positions and features. Publish the map as a "produced work" with the line "© OpenStreetMap contributors".
- Cannot: mix OSM into a database and publish that database under another license. A derived database must be ODbL.
- Implications: the `.glb` map is a produced work and stays CC BY. Any intermediate GeoPackage that merges OSM with ETAK is ODbL if we publish it. Keep OSM out of the published data files, or publish them under ODbL.
- Alternatives: ETAK has the same features under the Maa-amet license. Use ETAK, and OSM only for a name lookup that does not enter the data files.

### The Zone Blender template and texture library

- Can: use the material names so that the game applies its own textures. Use the template on each contributor's own machine.
- Cannot: commit the template, the textures, or any file from the game folder to the repository. Cannot redistribute them in a map file, except as names.
- Implications: the repository holds no game assets. The `.gitignore` blocks the template folder. A contributor needs the game.
- Alternatives: our own texture set under CC BY 4.0 for anything that must live in the repository.

### Google Street View and Google 3D

- Can: look at it as a human for reference.
- Cannot: download, cache, trace, or derive textures or geometry from it. The terms forbid scraping, caching and creating content from Google Maps content.
- Implications: never in the pipeline. A texture "inspired by" a Street View frame that a human paints by hand is fine.
- Alternatives: own photos, Fotoladu, Mapillary with its share-alike cost.

### Mapillary (CC BY-SA 4.0)

- Can: use photos and derive textures with attribution.
- Cannot: license the derived textures under CC BY. Share-alike forces CC BY-SA on the adaptation.
- Implications: a CC BY-SA texture inside a CC BY map makes the map a mixed work and confuses every downstream user.
- Alternatives: skip Mapillary. If a facade needs it, keep those textures in a separate folder with their own CC BY-SA license file.

### Our code: Apache-2.0 (proposed)

- Can: anyone uses, changes, sells, and closes the code. Contributors grant a patent license with their contribution.
- Cannot: remove the license and notices. Cannot sue users over patents in the code without losing the license.
- Implications: the pipeline can be reused by other cities and other simulators, also in closed products. The contribution clause means no separate agreement is needed.
- Alternatives: MIT is shorter and equal in practice, but has no patent clause and no contribution clause. GPL-3.0 forces derived tools to stay open, but blocks use inside closed simulators and adds friction for a small hobby project.

### Our assets: CC BY 4.0 (proposed)

- Can: anyone remixes and reuses the maps, textures and hero models, also commercially, with attribution.
- Cannot: drop the attribution to us and to Maa-amet.
- Implications: the same attribution rule as the input data, so one `NOTICE` covers both. A commercial simulator can ship our map with attribution.
- Alternatives: CC BY-SA keeps remixes open but blocks use in closed simulators, and it would be the only way to include Mapillary content. CC BY-NC blocks commercial use, but is not an open license and blocks the game developer from adopting a map as official if the game is sold. CC0 drops even our attribution, but cannot drop the Maa-amet one.

### Uploading to The Zone servers

- Can: upload the maps. Players download them by name.
- Cannot: verify the rights the game developer takes on uploaded maps. The store page and wiki state no terms for uploads.
- Implications: ask in Discord or by mail what rights an upload grants. A CC BY license on our side already permits the developer to host and adopt the map with attribution, so the risk is small.
- Alternatives: distribute the `.glb` only through GitHub releases until the terms are clear.

### Drone photos and privacy

- Can: photograph buildings from public airspace within the drone rules, and publish the textures.
- Cannot: publish faces, license plates, or interiors. Cannot fly the Mavic 2 Pro over the city.
- Implications: a blur step before commit, and a rented C2 drone for the city.
- Alternatives: photogrammetry from ground photos for single buildings, or a rented drone operator.

## License reference TL;DR

One entry per license that this project touches. "Must" lists the conditions, "cannot" the limits.

### Maa- ja Ruumiamet open data license (2025-01-01)

- Can: copy, change, combine, distribute, and sell the data and works made from it.
- Must: name the licensor, the data set and the data date. Ship the license text or link with redistributed data.
- Cannot: claim endorsement by the licensor. Cannot hold the licensor liable for errors.
- Alternatives: none. It is the only license for this data. It is in effect CC BY 4.0 with an extra rule on the data date.

### Apache-2.0

- Can: use, change, distribute, sublicense, and sell. Closed derivatives are allowed.
- Must: keep the license text, the copyright and `NOTICE` lines. Mark changed files.
- Cannot: use the project trademarks. A patent suit against the project ends your patent license.
- Implication: contributors grant a patent license by contributing, without a separate agreement. Incompatible with GPL-2.0 code, compatible with GPL-3.0 code.
- Alternatives: MIT, GPL-3.0.

### MIT

- Can: everything Apache-2.0 allows.
- Must: keep the license text and copyright line.
- Cannot: nothing more. There is no patent clause and no trademark clause.
- Implication: the shortest option. No protection if a contributor later claims a patent.
- Alternatives: Apache-2.0 when patents or a contribution clause matter.

### GPL-3.0

- Can: use, change, and sell.
- Must: publish the full source of any distributed derivative under GPL-3.0. Keep notices and install information.
- Cannot: link the code into a closed product and distribute it. Cannot add rules that GPL-3.0 does not allow.
- Implication: a simulator vendor could not embed the pipeline in a closed tool. For a small pipeline this cost brings little.
- Alternatives: Apache-2.0 or MIT for a hobby tool that others must be free to adopt.

### CC BY 4.0

- Can: copy, remix, distribute, and sell, in any medium.
- Must: credit the author, link the license, note changes. Attribution can be a line in a credits screen or a file.
- Cannot: apply technical measures that block the rights. Cannot imply endorsement.
- Implication: the right match for the Maa-amet inputs, because both need attribution only. Not meant for software, use it for maps, textures and models.
- Alternatives: CC BY-SA, CC0, CC BY-NC.

### CC BY-SA 4.0

- Can: as CC BY.
- Must: as CC BY, and license every adaptation under CC BY-SA or a compatible license.
- Cannot: license a remix under CC BY, or bundle the work into a closed asset pack.
- Implication: a single CC BY-SA texture forces the whole map that adapts it to CC BY-SA. This is the Mapillary problem.
- Alternatives: CC BY if the sources allow it.

### CC BY-NC 4.0

- Can: copy, remix, distribute for non commercial purposes.
- Must: as CC BY.
- Cannot: use commercially. "Commercial" is undefined in detail and creates doubt for a paid simulator or a sponsored channel.
- Implication: not an open license by the Open Definition. The game developer could not adopt the map as official in a paid game without a separate permission.
- Alternatives: CC BY with a request, not a rule, to ask before commercial use.

### CC0 1.0

- Can: everything, with no conditions. A public domain dedication.
- Must: nothing.
- Cannot: waive moral rights in some countries. Cannot remove the attribution that upstream licenses demand.
- Implication: our own attribution would be gone, the Maa-amet attribution would still be required, so the map could not truly be CC0.
- Alternatives: CC BY.

### ODbL 1.0 (OpenStreetMap)

- Can: use, change, and distribute the database. Make "produced works" such as maps, images and game levels under any license.
- Must: attribute. Publish any derived database under ODbL. Offer the derived database when you publish a produced work that used it.
- Cannot: use technical measures that block the rights. Cannot publish the database itself under another license.
- Implication: a `.glb` map is a produced work and can be CC BY. The GeoPackage that produced it is a derived database if it contains OSM data.
- Alternatives: ETAK under the Maa-amet license, which has no share-alike rule.

### Developer Certificate of Origin (DCO)

- Can: accept contributions with a `Signed-off-by` line in each commit.
- Must: the contributor states that they have the right to submit the work under the project license.
- Cannot: transfer copyright, and cannot change the license later without every contributor.
- Implication: light process, no paperwork. A license change later needs consent from all contributors.
- Alternatives: a contributor license agreement, which allows relicensing but scares away hobby contributors.

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
