# Licenses, contributions and legality

Status: proposal. The maintainer decides the items in section 1 before the first public push.

The document has four parts. Section 1 lists the decisions that we must make, with a recommendation for each. Section 2 lists the licenses that come with the inputs, where we have no choice. Section 3 is a reference with one entry per license, and each entry says what it pertains to in this project. Sections 4 to 7 cover attribution, contributions, content legality and drone rules.

## 1. Decisions to make

### D1. License for our code

Pertains to: `pipeline/`, `docker/`, scripts, configuration.

- Recommendation: Apache-2.0.
- Rationale: the pipeline is useful to other cities and other simulators, and some of those are closed products. Apache-2.0 allows that. It adds a patent grant from every contributor and a built in contribution clause, so no separate agreement is needed. It is compatible with the CC BY assets and with the Maa-amet inputs.
- Alternatives: MIT is equal in practice but has no patent or contribution clause. GPL-3.0 keeps derived tools open but blocks embedding in closed simulators and adds friction for a hobby project.

### D2. License for our assets

Pertains to: published `.glb` maps, textures we make, hero models in `assets/hero/`.

- Recommendation: CC BY 4.0.
- Rationale: the Maa-amet inputs need attribution and nothing else, so CC BY passes the same single rule downstream. One `NOTICE` covers both. The game developer can adopt a map as official in a sold game. Other pilots can remix.
- Alternatives: CC BY-SA keeps remixes open, but blocks closed simulators and is the only option if Mapillary content enters the map. CC BY-NC blocks commercial use, is not an open license, and would block adoption in a paid game. CC0 drops our attribution but cannot drop the Maa-amet attribution, so the map can never be fully CC0.

### D3. Contribution model

Pertains to: pull requests from collaborators.

- Recommendation: Developer Certificate of Origin, `git commit -s`, plus a pull request template that asks for the data sources of the change.
- Rationale: no paperwork, and the sign off is a statement that the contributor may license the work under D1 and D2. Apache-2.0 section 5 already covers the code side.
- Alternatives: a contributor license agreement allows relicensing later, but scares hobby contributors away. No sign off at all leaves the asset rights unclear.

### D4. Mapillary photos as texture source

Pertains to: facade textures.

- Recommendation: no.
- Rationale: Mapillary is CC BY-SA. One derived texture forces the map to CC BY-SA and conflicts with D2.
- Alternatives: own photos, Fotoladu after access is granted, procedural facades. If a single facade truly needs it, keep those textures in a separate folder with a CC BY-SA license file, and mark the map as mixed.

### D5. Distribution channel for the maps

Pertains to: where players get the `.glb` files.

- Recommendation: GitHub Releases as the primary channel, with the attribution in the release notes. Upload to The Zone server as well, after the developer confirms what rights an upload grants.
- Rationale: the game states no terms for uploads. CC BY already permits hosting and adoption with attribution, so the risk is small, but the question must be asked once.
- Alternatives: GitHub Releases only, until the terms are clear.

### D6. Oblique aerial photos from Fotoladu

Pertains to: facade textures in the second release.

- Recommendation: write to fotoladu@maaruum.ee and ask for bulk access with orientation data for a named photo list. Do not scrape the viewer.
- Rationale: the photos are open data with attribution, but the viewer offers no export, and the Chancellor of Justice review of 2025 makes access uncertain. A written yes protects the project.
- Alternatives: own drone photos, procedural facades.

## 2. Licenses that come with the inputs

No choice here. Each entry says what we can do, what we cannot do, and what it means for the project.

### Maa-amet geodata: Maa- ja Ruumiamet open data license

Buildings, lidar, elevation, orthophotos, ETAK vectors, trees.

- Can: use, change, combine, sell, redistribute. Publish the maps, the textures cut from orthophotos, the raw tiles.
- Cannot: drop the attribution. Cannot claim endorsement.
- Means: one attribution line per data set with the data year in every map description, in `NOTICE` and in the README, plus the license link.

### Fotoladu oblique photos: Maa-amet open data, attribution "Foto: Maa- ja Ruumiamet"

- Can: use as textures with the attribution line.
- Cannot: bulk download today. See D6.
- Means: second release material, after written access.

### OpenStreetMap: ODbL

- Can: use names and features. Publish the map as a produced work with "© OpenStreetMap contributors".
- Cannot: publish a database that mixes OSM with other data under a non ODbL license.
- Means: prefer ETAK. Use OSM only for lookups that do not enter the published data files. The `.glb` is a produced work and stays CC BY.

### The Zone Blender template and texture library: proprietary, part of the game

- Can: use the material names so that the game applies its own textures. Use the template on each contributor's own machine.
- Cannot: commit any file from the game folder. Cannot redistribute textures in a map file.
- Means: `.gitignore` blocks the template folder. A contributor needs the game.

### Google Street View and Google 3D: Google Maps Platform terms

- Can: look at it as a human for reference.
- Cannot: download, cache, trace or derive textures or geometry. The terms forbid scraping, caching and creating content from Google content.
- Means: never in the pipeline.

### Mapillary: CC BY-SA 4.0

- Can: use with attribution.
- Cannot: license derived textures under CC BY.
- Means: see D4, recommendation no.

### Own drone and ground photos: ours

- Can: publish as textures under D2.
- Cannot: publish faces, license plates, interiors.
- Means: a blur step before commit. Drone rules in section 7.

## 3. License reference

One entry per license. The first line says what the license pertains to in this project.

### Maa- ja Ruumiamet open data license, 2025-01-01

In this project: comes with all Maa-amet geodata and the Fotoladu photos. Not a choice.

- Can: copy, change, combine, distribute, sell the data and works made from it.
- Must: name the licensor, the data set and the data date. Ship the license text or link with redistributed data.
- Cannot: claim endorsement. Cannot hold the licensor liable.
- Note: in effect CC BY 4.0 with an extra rule on the data date.

### Apache-2.0

In this project: recommended for our code, D1.

- Can: use, change, distribute, sublicense, sell. Closed derivatives allowed.
- Must: keep the license text, copyright and `NOTICE` lines. Mark changed files.
- Cannot: use project trademarks. A patent suit against the project ends the patent license.
- Note: contributors grant a patent license by contributing. Compatible with GPL-3.0, not with GPL-2.0.

### MIT

In this project: alternative for our code, D1.

- Can: everything Apache-2.0 allows.
- Must: keep the license text and copyright line.
- Cannot: nothing more. No patent clause, no trademark clause.
- Note: shortest option, no protection if a contributor later claims a patent.

### GPL-3.0

In this project: alternative for our code, D1, not recommended.

- Can: use, change, sell.
- Must: publish the full source of any distributed derivative under GPL-3.0.
- Cannot: link into a closed product and distribute.
- Note: blocks a simulator vendor from embedding the pipeline.

### CC BY 4.0

In this project: recommended for our assets, D2.

- Can: copy, remix, distribute, sell, in any medium.
- Must: credit the author, link the license, note changes.
- Cannot: apply technical measures that block the rights. Cannot imply endorsement.
- Note: not meant for software. Matches the Maa-amet inputs.

### CC BY-SA 4.0

In this project: comes with Mapillary photos, D4. Alternative for our assets, D2.

- Can: as CC BY.
- Must: as CC BY, and license every adaptation under CC BY-SA.
- Cannot: license a remix under CC BY. Cannot bundle into a closed asset pack.
- Note: one CC BY-SA texture forces the whole map to CC BY-SA.

### CC BY-NC 4.0

In this project: alternative for our assets, D2, not recommended.

- Can: copy, remix, distribute for non commercial purposes.
- Must: as CC BY.
- Cannot: use commercially. "Commercial" is vague for a paid simulator or a sponsored channel.
- Note: not an open license by the Open Definition.

### CC0 1.0

In this project: alternative for our assets, D2, not recommended.

- Can: everything, no conditions.
- Must: nothing.
- Cannot: remove the attribution that upstream licenses demand.
- Note: the Maa-amet attribution stays required, so the map can never be fully CC0.

### ODbL 1.0

In this project: comes with OpenStreetMap data. Not a choice.

- Can: use, change, distribute the database. Make produced works such as maps and game levels under any license.
- Must: attribute. Publish any derived database under ODbL and offer it when a produced work is published.
- Cannot: publish the database under another license. Cannot use technical measures that block the rights.
- Note: the `.glb` map is a produced work. A GeoPackage with OSM data inside is a derived database.

### Google Maps Platform terms

In this project: comes with Google Street View and Google 3D. Not a choice.

- Can: view.
- Must: nothing, because no use is allowed.
- Cannot: scrape, cache, create content from Google content.

### Developer Certificate of Origin, DCO 1.1

In this project: recommended for contributions, D3.

- Can: accept contributions with a `Signed-off-by` line per commit.
- Must: the contributor states the right to submit under the project licenses.
- Cannot: transfer copyright. A later license change needs every contributor.
- Note: light process. A contributor license agreement is the heavier alternative.

## 4. Attribution and NOTICE

- `NOTICE` at the repository root lists every third party attribution: one line per Maa-amet data set with the data year, the Fotoladu line if used, the OpenStreetMap line if used.
- The README repeats the Maa-amet lines and links the license.
- Every map upload and every GitHub release repeats the Maa-amet lines in its description.
- Example line: "Elevation data 2024: Republic of Estonia Land and Spatial Development Board".

## 5. Contributions

- Contributors sign off commits with the Developer Certificate of Origin, `git commit -s`.
- The pull request template asks: which data sources did you use, and can you license the result under Apache-2.0 for code and CC BY 4.0 for assets.
- Hero assets need a source note: modeled from lidar, from own photos, or from Fotoladu photos.
- Nothing from the game folder enters a pull request.

## 6. Legality of the content

- Buildings: the Estonian Copyright Act allows reproduction of architectural works that stand permanently in public places, with the limit that the work is not the main subject of a commercial use. A free fan map is fine. A paid version needs a check for signature buildings such as ERM.
- Logos and signs: reproduce them as they appear in photos, at low resolution. Do not invent brand usage. Replace a logo if the owner asks.
- Personal data: faces and license plates never reach the repository. Orthophotos at 10 cm show no faces. Facades of private homes at low resolution are not personal data in practice, but a resident can ask for a blurred wall.
- Security sites: the prison, the military area at Raadi and the airport are in the public geodata and in the orthophoto. Build them from the same data. Do not add drone photos of them.

## 7. Drone flights

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
