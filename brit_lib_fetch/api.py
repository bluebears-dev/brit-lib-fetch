from loguru import logger
from brit_lib_fetch.model import ManuscriptPageMetadata
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from lxml import etree
import xmltodict

VIEWER_BL_UK_URL = "https://www.bl.uk/manuscripts/Viewer.aspx?ref={manuscript_page_id}"
PROXY_BL_UK_URL = "https://www.bl.uk/manuscripts/Proxy.ashx?view={manuscript_page_id}_files/{zoom_index}/{x}_{y}.jpg"
PROXY_BL_UK_METADATA_URL = (
    "https://www.bl.uk/manuscripts/Proxy.ashx?view={manuscript_page_id}.xml"
)


def _retry_session(retries=5, backoff_factor=0.2):
    session = requests.Session()

    retries = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[500, 502, 503, 504, 429],
        allowed_methods=frozenset(["GET", "POST"]),
    )

    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.mount("http://", HTTPAdapter(max_retries=retries))

    return session


async def get_manuscript_page_list(manuscript_page_id: str) -> list[str]:
    url = VIEWER_BL_UK_URL.format(manuscript_page_id=manuscript_page_id)

    logger.debug(f"GET {url} (page list)")
    viewer_page_response = _retry_session(3, backoff_factor=0.1).get(url)

    logger.debug("Fetching page list from HTML")
    page_tree = etree.fromstring(viewer_page_response.content, etree.HTMLParser())
    # NOTE(bluebears) - List of all possible pages of the manuscript is put into the HTML source
    page_list = page_tree.xpath("//input[@id='PageList']")[0]

    return [page for page in page_list.get("value").split("||") if page != "##"]


async def get_manuscript_page_info(manuscript_page_id: str) -> ManuscriptPageMetadata:
    url = PROXY_BL_UK_METADATA_URL.format(manuscript_page_id=manuscript_page_id)
    logger.debug(f"GET {url} (page info)")

    response = _retry_session(5).get(url)
    response = response.content.decode("utf-8")

    logger.debug(f"Parsing {manuscript_page_id} page info XML")
    response = xmltodict.parse(response)

    image_info = response["Image"]
    size_info = image_info["Size"]

    return ManuscriptPageMetadata(
        id=manuscript_page_id,
        width=int(size_info["@Width"]),
        height=int(size_info["@Height"]),
        tile_size=int(image_info["@TileSize"]),
        tile_overlap=int(image_info["@Overlap"]),
        format=image_info["@Format"],
    )


async def get_manuscript_page_tile(
    manuscript_page_id: str, zoom_index: int, x: int, y: int
) -> bytes:
    url = PROXY_BL_UK_URL.format(
        manuscript_page_id=manuscript_page_id,
        zoom_index=zoom_index,
        x=x,
        y=y,
    )
    logger.debug(f"GET {url} (page tile)")
    response = _retry_session(8, backoff_factor=0.2).get(url)
    response.raise_for_status()

    return response.content
