# Tartu locations and map tiles

Coordinates are WGS84 (latitude, longitude) from [OpenStreetMap](https://www.openstreetmap.org/), September 2026.
At this latitude 0.01 degrees of latitude is 1.11 km and 0.01 degrees of longitude is 0.58 km.

## Clusters

Each cluster is one candidate for a detailed map. The size is the bounding box of the landmarks plus a margin.

| # | Cluster | Landmarks | Size | Build difficulty |
|---|---------|-----------|------|------------------|
| 1 | [Kesklinn](https://et.wikipedia.org/wiki/Kesklinn_%28Tartu%29) ja [Emajõgi](https://et.wikipedia.org/wiki/Emaj%C3%B5gi) (downtown and river) | Raekoja plats, Toomkirik, Jaani kirik, Pauluse kirik, Tähetorn, Tigutorn, Kvartal, Emajõe alajaam, bridges Kroonuaia, Vabadussild, Kaarsild, Võidu sild, Turusild, Sõpruse sild | 2.2 x 1.8 km, 4 km² | High. Dense old town, spires and the arch bridge need hand work. |
| 2 | [Ülejõe](https://et.wikipedia.org/wiki/%C3%9Clej%C3%B5e) ja [Supilinn](https://et.wikipedia.org/wiki/Supilinn) | [Lodjakoda](https://lodi.ee/), Kroonuaia sild, Peetri kirik, [Tartu](https://en.wikipedia.org/wiki/Tartu) Ülikooli staadion, the [Haine Paelavabrik](https://www.haine.ee/) block at Puiestee 13b between Puiestee, Lubja and Staadioni (long factory wings around a courtyard, SädeTERA school in the same block), Meltsiveski park | 1.8 x 1.3 km, 2.3 km² | Medium. Overlaps cluster 1 at Kroonuaia. |
| 3 | [Tähtvere](https://et.wikipedia.org/wiki/T%C3%A4htvere) ja Vaksali põhjaots | [Tartu laululava](https://et.wikipedia.org/wiki/Tartu_laululava), Tähtvere park, EMÜ campus, [Tartu Näitused](https://tartunaitused.ee/), Tartu 330/110 kV alajaam with the 330 kV and 110 kV lines, the industrial block at the north end of Vaksali (name to verify) | 1.7 x 1.8 km, 3 km² | Medium. Wires and lattice towers are generated, laululava shell is hand made. |
| 4 | Vaksali, Maarjamõisa ja Tammelinn | Tartu raudteejaam and freight yard, [Tartu Mill](https://tartumill.ee/) elevator (Väike kaar 33), [Tartu Ülikooli Kliinikum](https://www.kliinikum.ee/), [Aparaaditehas](https://aparaaditehas.ee/), Tartu veetorn, [Tamme staadion](https://et.wikipedia.org/wiki/Tamme_staadion), Tartu telemast (186 m) | 1.5 x 1.9 km, 2.8 km² | Medium. Telemast lattice is generated. Hospital heliport is a drone no-fly zone. |
| 5 | [Annelinn](https://et.wikipedia.org/wiki/Annelinn) ja [Lohkva](https://et.wikipedia.org/wiki/Lohkva) | Anne kanal, Annelinn panel houses, [A. Le Coq spordimaja](https://et.wikipedia.org/wiki/A._Le_Coq_Sport_spordimaja), Anne alajaam 110 kV, [Gren](https://gren.com/ee/) (former Fortum) Tartu power plant, [Grüne Fee](https://grynefee.ee/) greenhouses | 2.9 x 1.9 km, 5.5 km² | Low. Box geometry. [Maa-amet](https://geoportaal.maaruum.ee/) LOD2 fits well. |
| 6 | [Raadi](https://et.wikipedia.org/wiki/Raadi_lennuv%C3%A4li) | [Eesti Rahva Muuseum](https://www.erm.ee/), Raadi mõisa park, Raadi airfield runway, Ülejõe alajaam, the 90 m mast at Puiestee | 2.6 x 2.8 km, 7 km² | Low. Mostly open ground. Kaitsevägi area to the north is a drone no-fly zone. |
| 7 | Ropka, [Ihaste](https://et.wikipedia.org/wiki/Ihaste) ja [Aardlapalu](https://et.wikipedia.org/wiki/Aardlapalu) | Ihaste sild (Idaringtee), Emajõgi meanders, Aardlapalu liivakarjäär, Tartu Veevärk plant, Tööstuse alajaam, [Tartu vangla](https://www.vangla.ee/et/asutused-kontaktid/tartu-vangla) | 3 x 3 km, 9 km² | Low. Few buildings. Prison and airport zones limit drone flights. |
| 8 | [Lõunakeskus](https://lounakeskus.com/) | Lõunakeskus, Lääneringtee, Lemmatsi alajaam | 1 x 1 km, 1 km² | Low. Low priority. |

## Landmark coordinates

| Landmark | Lat | Lon | Note |
|----------|-----|-----|------|
| Raekoja plats | 58.38021 | 26.72241 | |
| Tartu toomkirik | 58.38026 | 26.71541 | ruin, LOD2 will be rough |
| Jaani kirik | 58.38266 | 26.72005 | spire |
| Pauluse kirik | 58.37177 | 26.71566 | |
| Peetri kirik | 58.38984 | 26.72778 | two spires |
| Tartu tähetorn | 58.37882 | 26.72009 | |
| Tigutorn | 58.37654 | 26.73585 | tallest building in centre |
| Kvartal | 58.37692 | 26.72899 | |
| Kroonuaia sild | 58.38643 | 26.72203 | |
| Vabadussild | 58.38517 | 26.72388 | |
| Kaarsild | 58.38078 | 26.72586 | arch, hand made |
| Võidu sild | 58.37932 | 26.73044 | |
| Turusild | 58.37847 | 26.73736 | |
| Sõpruse sild | 58.37205 | 26.74463 | |
| Lodjakoda | 58.39132 | 26.71418 | |
| Tartu Ülikooli staadion | 58.38991 | 26.72501 | |
| Haine Paelavabrik block | 58.39255 | 26.71963 | Puiestee 13b, old factory wings around a courtyard |
| Tartu laululava | 58.38806 | 26.70257 | open shell, hand made |
| Tartu Näitused | 58.39066 | 26.69100 | |
| Tartu alajaam 330/110 kV | 58.37938 | 26.69099 | [Elering](https://elering.ee/) |
| Tartu raudteejaam | 58.37370 | 26.70646 | |
| Tartu Mill | 58.37049 | 26.70551 | grain elevator, 1941 |
| Tartu Ülikooli Kliinikum | 58.36944 | 26.70010 | heliport |
| Aparaaditehas | 58.37056 | 26.71608 | |
| Tartu veetorn | 58.37483 | 26.71643 | 33 m |
| Tamme staadion | 58.36662 | 26.71360 | |
| Tartu telemast | 58.36204 | 26.70207 | 186 m lattice |
| Anne kanal | 58.37542 | 26.74317 | |
| Annelinn centre | 58.37473 | 26.77263 | |
| A. Le Coq spordimaja | 58.37134 | 26.75205 | |
| Anne alajaam 110 kV | 58.37689 | 26.78427 | |
| Gren Tartu power plant | 58.36983 | 26.79106 | 25 MW CHP, 2009 |
| Grüne Fee greenhouses | 58.36802 | 26.79030 | 13 greenhouse buildings in OSM |
| Eesti Rahva Muuseum | 58.39580 | 26.74641 | |
| Raadi mõisa park | 58.39945 | 26.74112 | |
| Ülejõe alajaam 110 kV | 58.39280 | 26.74148 | |
| Mast, Puiestee | 58.38764 | 26.74542 | 90 m |
| Ihaste sild | 58.34653 | 26.76049 | |
| Aardlapalu liivakarjäär | 58.33054 | 26.75997 | |
| Tartu vangla | 58.34429 | 26.74632 | no-fly zone |
| Tööstuse alajaam 110 kV | 58.34600 | 26.73238 | |
| Lõunakeskus | 58.35815 | 26.67563 | |
| [Tartu lennujaam](https://www.tartu-airport.ee/) | 58.30868 | 26.68411 | 6 km south of centre |

## Power lines in the city (OpenStreetMap names)

- 330 kV: Balti - Tartu, Tartu - Sindi, Tartu - Valmiera, Tartu - Pihkva. All end at Tartu alajaam.
- 110 kV: Tartu - Anne, Tartu - Tööstuse, Tartu - Emajõe, Tartu - Saare, Tartu - Elva, Tartu - Puhja, Tartu - Maaritsa, Anne - Alatskivi, Anne - Kuuste.

The Maa-amet [ETAK](https://geoportaal.maaamet.ee/est/ruumiandmed/eesti-topograafia-andmekogu-p79.html) layer `E_601_elektriliin_j` has the same lines with tower positions in `E_602_tehnopaigaldis_p`.
