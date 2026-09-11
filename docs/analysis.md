# Tartu for The Zone: feasibility and plan

Date: 2026-09-11. Status: proposal, before the first test tile.

## Summary

- The Zone loads a custom map as one glTF binary file (`.glb`) that Blender exported. The game runs on Godot 4.4 or later. There is no SDK and there are no documented size limits. Custom map support is marked experimental.
- Maa-amet publishes everything that a low fidelity city model needs: LOD2 buildings for all of Tartu (22,466 objects, 11 MB), 18 points per m² lidar, 1 m elevation models, 10 cm orthophotos, 350,792 tree points, and vector data for roads, rails, water, power lines and towers. The license permits redistribution with attribution.
- The buildings have no textures. The orthophoto gives roofs and ground. Walls need a generated facade or a projection from oblique aerial photos.
- Recommendation: build one low fidelity base map of the whole city, and a set of detailed maps of 2 to 6 km² each. One large detailed map is not practical because the game loads the whole file at once and has no streaming.
- Build order: a 1 km² test tile first, then the base map, then Annelinn and Lohkva as the first detailed map.

## 1. What The Zone accepts

Verified facts from the wiki and the Steam patch notes (see `docs/sources.md`):

- Engine: Godot 4.3 in March 2025, upgraded to 4.4, later versions not named.
- Map file: `custom_maps/<name>/<name>.glb` inside the game folder. The folder name and the file name must be equal.
- Authoring: the game ships a Blender template with a texture library. Textures show wrong in Blender and the game replaces them at load time. This means that material names in the `.glb` map to in-game materials.
- Sharing: an upload button in the game. The first uploader owns the map name. Other players enter the name in a custom lobby. Since February 2026 a map browser lists community maps.
- Official maps are single flying spots at 1:1 scale, for example one abandoned building. Nobody published a city scale map. We will be the first, so nothing about limits is known.

Unknown, and the first test tile must answer these:

1. Does the game show image textures that are embedded in the `.glb`? Graffiti textures in official maps suggest yes.
2. How does the game build collision? Godot editors use name suffixes like `-col`, but a runtime glTF loader does not apply them. The game must generate a collision shape from the visual mesh. A thin cylinder for a wire tests this.
3. How long does a 200 MB file take to load, and does the upload server accept it?
4. How many separate meshes does the game tolerate? Each mesh is one draw call. The pipeline must merge buildings into chunks.
5. Does the game set a maximum flight distance or a world boundary?

Godot itself is not the limit. Godot uses 32-bit floats. At 5 km from the origin the position step is 0.5 mm. A 10 by 10 km map is fine for rendering and physics. Problems start at about 50 km.

## 2. What Maa-amet gives us

All data is under the Maa- ja Ruumiamet open data license of 2025-01-01. Commercial use, derivatives and redistribution are allowed. Attribution must name the licensor, the data set and the data date, and the license text or link must travel with redistributed data.

| Data | Detail | Format | Tartu size | Use in the map |
|------|--------|--------|------------|----------------|
| 3D buildings LOD2 | Roof shapes from lidar, footprints from ETAK. No textures. | OBJ, CityGML, GDB | 22,466 objects, 11.2 MB OBJ | All buildings in the base map, background buildings in detailed maps |
| 3D buildings LOD1 | Flat roofs | same | 22,928 objects | Fallback |
| LOD1 bridges, roofed structures, greenhouses | Slabs and boxes | same | small | Bridges as placeholders, Lohkva greenhouses |
| Trees LOD0 | Points with height, crown diameter, conifer or deciduous | GPKG, GDB | 350,792 trees, 39 MB | Billboard or low poly trees |
| Lidar point cloud | 18 points per m² in cities, RGB and NIR, classes ground, building, water, noise | LAZ per 1 km² sheet | about 90 sheets for the city | Hero building shapes, wire sag check, terrain detail near the river |
| DTM 1 m, DSM 1 m | Elevation | GeoTIFF per sheet | about 90 sheets | Terrain mesh |
| Orthophoto | 10 cm in cities 2022 to 2024, 20 cm in 2025 | GeoTIFF or ECW per sheet | 90 sheets, several GB | Ground and roof texture |
| Oblique aerial photos | Fotoladu archive, viewing service | JPEG | millions of photos | Facade texture source, see section 4 |
| ETAK vectors | Roads, rails, bridges, power lines over 1 kV with tower points, water, forest, single trees, fences, buildings | SHP, GPKG, WFS | 1.3 GB for all Estonia, small for Tartu | Roads as flat decals, wires, towers, water plane, fences |

Download is by map sheet with a plain URL pattern, and Maa-amet states that there is no limit on the number of sheets. A script can fetch all Tartu sheets. The LOD2 download for Tartu was tested on 2026-09-11: 11.8 MB zip, OBJ file of 64 MB, exported with FME on 2026-09-05. The OBJ has no object groups. Each building is one `usemtl` block with a generated name, so the ETAK building ID is only in the CityGML and GDB variants. Coordinates are L-EST97 with a local offset that the `.fwt` sidecar file stores (easting 654513.288, northing 6475676.235, height 62.645), Z is up.

What Maa-amet does not have: textured meshes of Tartu, a bulk export of oblique photos with camera orientation (to verify, section 4), and a power line class in the lidar.

## 3. How large can a map be

Two budgets matter: texture memory and triangles. Both scale with area and with resolution.

### Texture budget

Assume that the game keeps textures uncompressed in video memory, 4 bytes per pixel plus one third for mipmaps. This is the worst case for a runtime glTF loader.

| Map | Area | Ground pixel | Pixels | Video memory |
|-----|------|--------------|--------|--------------|
| Base map, whole city | 9 x 8 km, 72 km² | 1.0 m | 72 Mpx | 0.4 GB |
| Base map, whole city | 72 km² | 0.5 m | 288 Mpx | 1.5 GB |
| Detailed tile | 2 x 2 km, 4 km² | 0.25 m | 64 Mpx | 0.35 GB |
| Detailed tile | 4 km² | 0.10 m | 400 Mpx | 2.1 GB |
| Detailed tile | 1 x 1 km, 1 km² | 0.10 m | 100 Mpx | 0.5 GB |

A rule of thumb: one 8192 pixel texture covers 2 x 2 km at 25 cm or 1 x 1 km at 12.5 cm. Godot allows textures up to 16384 pixels.

So the base map can use 0.5 to 1 m ground pixels. A detailed tile of 4 km² can use 25 cm, and the full 10 cm orthophoto only fits on 1 km² or on selected hero buildings.

### Triangle budget

| Content | Count | Triangles |
|---------|-------|-----------|
| LOD2 buildings, whole city, measured in the OBJ file of 2026-09-05 | 22,468 | 1.15 million (625,852 vertices) |
| Terrain, 72 km² at 10 m grid, 2 m near the river | | about 1 million |
| Trees over 8 m as two crossed quads | about 100,000 | 0.4 million |
| All trees as crossed quads | 350,792 | 1.4 million |
| Power lines, towers, bridges, fences | | 0.3 million |

A base map of about 4 million triangles in a few hundred merged meshes is normal for Godot 4 on a mid range GPU. The file will be 50 to 150 MB. Load time is the open question.

### Conclusion on size

- One detailed map of the whole city is not possible. It would need more than 10 GB of textures and a game with streaming.
- One low fidelity base map of the whole city is possible: 72 km², 1 m ground pixel, LOD2 buildings, trees over 8 m, all high voltage lines, bridges as slabs. It is good for long cruises, for orientation and for the "recognizable from the air" goal.
- Detailed maps of 2 to 6 km² are the right unit for freestyle and rehearsal. Each has 20 to 25 cm ground texture, all trees, facades, fences and lamp posts, and hand made hero assets. Photogrammetry patches come later inside these tiles.
- Both types share one pipeline and one configuration format. Only the bounding box and the quality settings differ.

## 4. Textures for walls

The orthophoto covers roofs and ground. Nothing in the open data covers walls directly. Options, in order of automation:

| Source | Automation | License | Verdict |
|--------|------------|---------|---------|
| Procedural facades from building attributes | Full | Ours | First release |
| Maa-amet oblique aerial photos (Fotoladu) | Partial, after written access | Open data, "Foto: Maa- ja Ruumiamet" | Second release, for hero buildings and the biggest facades |
| Own ground and drone photos | Manual per building | Ours | Hero buildings |
| Mapillary | Partial | CC BY-SA 4.0, share-alike taints the asset license | Avoid |
| Google Street View, Google 3D | None allowed | Terms forbid extraction and derived content | Human reference only |

Procedural facades for the first release. The GDB and CityGML variants of the LOD2 data carry the EHR code (Ehitisregister). The register gives the use of the building, the year and the number of floors. The pipeline picks one of a few facade sets by these attributes: panel house, brick, plaster, glass office, industrial sheet, wooden house. Floor height is about 3 m. Roof color comes from the orthophoto. Walls get a window grid and a base color per set. This is the "generic up close, Tartu from the air" look. Material names can reuse The Zone texture library so that the walls match the official maps.

Fotoladu for the second release. The viewer page embeds, for each photo, the file name, the camera position, the flight height (about 1300 m in Tartu), the image size of 7952 x 5304 pixels, and the four ground corners of the footprint. It does not publish the camera angles or the focal length. From the camera position, the four corners and the known sensor, a resection solves the camera pose well enough to project the photo onto the LOD2 walls. Expected ground pixel is 10 to 20 cm, so a 30 m wide facade gets about 200 pixels, enough for color and window rhythm, not for detail. The newest photos of Tartu are from April 2024.

Two conditions. First, there is no bulk download, only the viewer tiles. Write to fotoladu@maaruum.ee and ask for bulk access with orientation data for a named list of photos before any script touches the viewer. Second, the Chancellor of Justice wrote to the ministry in November 2025 about privacy in the high resolution 2025 photos. Access can tighten. Do not build the plan on Fotoladu alone.

Tartu city had two 3D models, a lidar volume model by CafaTech and a Unity model of the extended center. The page is offline now and no reuse license was stated. Ask rlo@tartu.ee if the Unity model source is available, but do not wait for it.

## 5. Clusters and priority

See `docs/locations.md` for coordinates and the corrected grouping, and `docs/licensing.md` for the drone zones that limit photogrammetry in each cluster. Recommended order:

1. Annelinn ja Lohkva. Box shaped panel houses, greenhouses, the power plant, the Anne kanal. LOD2 data fits well. This is the first detailed map.
2. Tähtvere ja Vaksali põhjaots. The laululava, the 330 kV substation with lines in four directions, Tartu Näitused. Best wire content. The laululava shell is the first hand made hero asset.
3. Kesklinn ja Emajõgi. The most recognizable and the hardest. Spires and the Kaarsild need hand work.
4. Raadi. ERM and the runway, cheap to build, good for speed.
5. Vaksali, Maarjamõisa ja Tammelinn. Station, Tartu Mill, hospital, telemast.
6. Ülejõe ja Supilinn. Lodjakoda and the Haine Paelavabrik block. Can merge with Kesklinn later as one 6 km² map if the game handles it.
7. Ropka, Ihaste ja Aardlapalu. Quarry and river meanders.
8. Lõunakeskus.

The laululava shows a general limit of the Maa-amet model. The lidar sees the roof, and the LOD2 algorithm closes it into a solid block. Every open structure needs a hand made replacement: the laululava, the Kaarsild arch, the telemast and transmission towers, church spires, the ERM roof edge, bridges with their piers. The pipeline must support a replacement list: for a given ETAK building ID, drop the LOD2 mesh and insert a hero `.glb` at the same position.

## 6. Pipeline design

Goal: a reproducible build from a configuration file to a `.glb`, and both machines can run it.

- Python does all geometry work and writes the `.glb` directly with `trimesh` and `pygltflib`. Blender is not in the automated path. Blender is the authoring tool for hero assets, which are separate `.glb` files that the build merges in.
- Reason: official Blender containers exist only for Linux x86_64. On the Mac they would run under emulation. A pure Python container runs native on both machines.
- Docker image with GDAL, PDAL, Python 3.12, geopandas, shapely, rasterio, laspy, trimesh, pygltflib.
- Steps: fetch (Maa-amet sheets for the bounding box, cached under `data/`), terrain (DTM to an adaptive mesh), ground texture (orthophoto to resampled tiles), buildings (LOD2 OBJ to merged chunks with facade UVs and hero replacements), vegetation (tree points to billboards), lines (ETAK power lines and tower points to catenary wires and lattice towers), water (water polygons to a plane at the water level), roads (flat decals in the base map), merge and export.
- Configuration per map: name, bounding box in L-EST97, ground pixel size, tree height cut, features to include, hero asset list.
- Coordinate system: L-EST97 (EPSG:3301) is already metric. The map origin is the center of the bounding box, Y is up, and heights use the EH2000 datum as they come.

## 7. Effort

Hours are for Claude Code work plus testing by the maintainer. Drone work is extra.

| Step | Hours | Result |
|------|-------|--------|
| Test tile: 1 km² of Annelinn, terrain, ortho, LOD2, loaded in the game | 6 to 10 | Answers the five unknowns |
| Pipeline v0: fetch, terrain, ground texture, buildings, water, export, Docker | 30 to 40 | Any bounding box builds |
| Base map v0.1: whole city, tuned to load and run | 10 to 15 | First public map |
| Trees, power lines, towers, bridges, fences | 15 to 20 | Base map v0.2 |
| Facade generator and oblique photo projection | 20 to 40 | Walls stop being gray |
| Hero assets per detailed map | 8 to 20 each | Laululava, spires, Kaarsild, telemast, ERM |
| Photogrammetry per site, capture plus processing plus cleanup | 25 to 40 each | Photo real patch |

First public release with the base map and two detailed maps: about 120 to 160 hours.

## 8. Roadmap

1. Week 1: repository, Docker image, fetch script, test tile in the game. Ask in the Discord channel `#custom-map-help` about texture support, collision and file size.
2. Weeks 2 to 4: pipeline v0 and the base map.
3. Weeks 5 to 6: Annelinn ja Lohkva detailed map, tree and wire generators.
4. Weeks 7 to 10: Tähtvere ja Vaksali with the laululava and the substation. Facade work.
5. Later: Kesklinn, Raadi, drone scans of the most played spots.
