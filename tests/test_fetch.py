import httpx
import pytest

from fpv_maps.crs import BBox
from fpv_maps.fetch import (
    BUILDINGS_LOD2,
    DTM_1M,
    ORTHO_CITY_RGB,
    ORTHO_PRODUCTS,
    check_is_file,
    download_url,
    list_files,
    newest_geotiff,
    sheet_2000,
    sheet_10000,
    sheets_for,
)

# Sheet numbers and bounds checked against the Maa-amet grid files epk2T and epk10T.
SHEETS_2000 = [
    ("473662", 662000, 6473000),
    ("374643", 643000, 6374000),
    ("640636", 636000, 6640000),
]
SHEETS_10000 = [
    ("54761", 660000, 6470000),
    ("44742", 645000, 6370000),
    ("62032", 435000, 6500000),
    ("75031", 730000, 6600000),
]


@pytest.mark.parametrize(("sheet", "east", "north"), SHEETS_2000)
def test_sheet_2000(sheet, east, north):
    assert sheet_2000(east + 500, north + 500) == sheet


@pytest.mark.parametrize(("sheet", "east", "north"), SHEETS_10000)
def test_sheet_10000(sheet, east, north):
    assert sheet_10000(east + 100, north + 100) == sheet
    assert sheet_10000(east + 4999, north + 4999) == sheet


def test_sheets_for_box_on_sheet_edges():
    # A box that equals one 1:2000 sheet lists only that sheet.
    assert sheets_for(BBox(662000, 6473000, 663000, 6474000), 2000) == ["473662"]
    # A 2 x 2 km box centered on a corner touches four sheets.
    assert sheets_for(BBox(661500, 6472500, 663500, 6474500), 2000) == [
        "472661",
        "472662",
        "472663",
        "473661",
        "473662",
        "473663",
        "474661",
        "474662",
        "474663",
    ]
    assert sheets_for(BBox(662000, 6473000, 663000, 6474000), 10000) == ["54761"]


def test_download_url():
    url = download_url(DTM_1M, "54761_dtm_1m.tif", "54761")
    assert url.startswith("https://geoportaal.maaamet.ee/index.php?")
    for part in (
        "kaardiruut=54761",
        "andmetyyp=dem_1m_geotiff",
        "dl=1",
        "f=54761_dtm_1m.tif",
        "page_id=614",
    ):
        assert part in url


def test_newest_geotiff():
    files = [
        "473662_OF_RGB_ECW_2024_04_27.zip",
        "473662_OF_RGB_GeoTIFF_2023_05_01.zip",
        "473662_OF_RGB_GeoTIFF_2024_04_27.zip",
    ]
    assert newest_geotiff(files) == "473662_OF_RGB_GeoTIFF_2024_04_27.zip"
    assert newest_geotiff(["x.laz"]) is None


def test_list_files_parses_search_fragment():
    html = (
        '<a href="index.php?lang_id=1&amp;plugin_act=otsing&amp;kaardiruut=473662'
        "&amp;andmetyyp=ortofoto_asulad_rgb&amp;dl=1&amp;f=473662_OF_RGB_GeoTIFF_2024_04_27.zip"
        '&amp;page_id=610">a</a> <a href="?f=473662_OF_RGB_ECW_2024_04_27.zip&amp;x=1">b</a>'
    )
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=html))
    with httpx.Client(transport=transport) as client:
        assert list_files(client, ORTHO_CITY_RGB, "473662") == [
            "473662_OF_RGB_ECW_2024_04_27.zip",
            "473662_OF_RGB_GeoTIFF_2024_04_27.zip",
        ]


def test_check_is_file_rejects_a_web_page():
    # The portal answers a wrong file name with status 200 and an HTML page.
    with pytest.raises(FileNotFoundError, match="no such file"):
        check_is_file("text/html;charset=utf-8", "https://example.invalid/x")
    check_is_file("application/zip", "https://example.invalid/x")
    check_is_file("application/octet-stream", "https://example.invalid/x")


def test_ortho_products_use_different_grids():
    assert ORTHO_PRODUCTS["city"].grid == 2000
    assert ORTHO_PRODUCTS["estonia"].grid == 10000


def test_the_base_map_box_needs_few_estonia_sheets():
    # 9 x 9 km over Tartu: 81 sheets of the city product, 6 of the Estonia product.
    box = BBox(656000, 6468500, 665000, 6477500)
    assert len(sheets_for(box, 2000)) == 90
    assert sheets_for(box, 10000) == ["54654", "54663", "54752", "54754", "54761", "54763"]


def test_urlencode_keeps_an_estonian_letter():
    # Noo vald is written with the letter o with a tilde in the Maa-amet file name.
    url = download_url(BUILDINGS_LOD2, "hooned_lod2-Nõo_vald-obj.zip")
    assert "hooned_lod2-N%C3%B5o_vald-obj.zip" in url
