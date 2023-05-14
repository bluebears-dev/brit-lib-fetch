import asyncio
import dataclasses
import json
import pathlib
import random
from io import BytesIO

import requests
from loguru import logger
from PIL import Image, UnidentifiedImageError

from brit_lib_fetch.api import (
    get_manuscript_page_info,
    get_manuscript_page_list,
    get_manuscript_page_tile,
)
from brit_lib_fetch.model import ManuscriptMetadata, ManuscriptPageMetadata

_PAGE_INFO_SEMAPHORE = asyncio.Semaphore(8)
_DOWNLOAD_SEMAPHORE = asyncio.Semaphore(30)

BASE_DIR = pathlib.Path("downloaded_manuscript")
PAGE_METADATA_FILENAME = ".metadata"
MANUSCRIPT_METADATA_FILENAME = ".manuscript_metadata"


def get_manuscript_page_id_from_url(url: str) -> str:
    search_text = "Viewer.aspx?ref="
    index = url.rfind(search_text)

    if index < 0:
        logger.error(f"Invalid URL {url}, manuscript page ID not found")

    id_pos = index + len(search_text)
    return url[id_pos:]


async def _check_magnification_index(manuscript_page_id: str, magnification_index: int) -> bool:
    try:
        result = await get_manuscript_page_tile(manuscript_page_id, magnification_index, 0, 0)
    except requests.Timeout as e:
        logger.warning(f"Timeout, skipping: {e}")
        return False
    except requests.ConnectionError as e:
        logger.warning(f"Conncetion error, skipping: {e}")
        return False

    if not result:
        logger.warning("Failed GET, skipping")
        return False

    try:
        content_io = BytesIO(result)
        img = Image.open(content_io)
    except UnidentifiedImageError:
        logger.warning("Fetched data is not an image, skipping")
        return False

    is_correct = img.width > 0
    if is_correct:
        logger.info("Found correct magnification index")
    return is_correct


async def get_magnification_indices(manuscript_page_id: str) -> set[int]:
    tasks = {}
    async with asyncio.TaskGroup() as group:
        for magnification_index in reversed(range(12, 20)):
            with logger.contextualize(
                manuscript_page_id=manuscript_page_id,
                magnification_index=magnification_index,
            ):
                tasks[magnification_index] = group.create_task(
                    _check_magnification_index(manuscript_page_id, magnification_index)
                )

    indices = set()
    for magnification_index, task in tasks.items():
        if task.result():
            logger.debug(f"Magnification index found: {magnification_index}")
            indices.add(int(magnification_index))

    return indices


async def _fetch_with_max_concurrent(
    manuscript_page_id: str,
    magnification_index: int,
    x: int,
    y: int,
) -> None:
    path = BASE_DIR.joinpath(manuscript_page_id, f"{x}-{y}.jpg")

    if path.exists():
        logger.info(f"Already fetched - {path} is present")
        return

    async with _DOWNLOAD_SEMAPHORE:
        await asyncio.sleep(random.randint(0, 10))
        logger.info(f"Starting tile fetch - {manuscript_page_id} {x, y}")
        image_data = await get_manuscript_page_tile(manuscript_page_id, magnification_index, x, y)

    if not image_data:
        return

    with path.open("wb") as file:
        logger.info(f"Writing file {path}")
        file.write(image_data)


async def fetch_and_save_tiles(manuscript: ManuscriptMetadata, manuscript_page: ManuscriptPageMetadata) -> None:
    logger.info(
        f"Fetching all parts of the image for {manuscript_page.id} with magnification {manuscript.max_magnification_index}"  # noqa: E501
    )

    async with asyncio.TaskGroup() as group:
        for x in range(manuscript_page.last_tile_x):
            for y in range(manuscript_page.last_tile_y):
                group.create_task(
                    _fetch_with_max_concurrent(manuscript_page.id, manuscript.max_magnification_index, x, y)
                )


async def load_manuscript_metadata(url: str) -> ManuscriptMetadata:
    manuscript_page_id = get_manuscript_page_id_from_url(url)

    metadata_path = BASE_DIR.joinpath(manuscript_page_id, MANUSCRIPT_METADATA_FILENAME)

    if metadata_path.exists():
        logger.warning(f"Manuscript metadata exists, loading from file: {metadata_path}")

        with metadata_path.open("r") as file:
            data = json.load(file)
            return ManuscriptMetadata(**data)

    page_list = await get_manuscript_page_list(manuscript_page_id)
    magnification_indices = await get_magnification_indices(manuscript_page_id)
    logger.info("Fetched manuscript metadata")

    return ManuscriptMetadata(magnification_indices=list(magnification_indices), page_id_list=page_list)


async def load_page_metadata(
    manuscript_page_id: str,
) -> ManuscriptPageMetadata:
    page_metadata_path = BASE_DIR.joinpath(manuscript_page_id, PAGE_METADATA_FILENAME)

    if page_metadata_path.exists():
        logger.warning(f"Page metadata exists, loading from file: {page_metadata_path}")

        with page_metadata_path.open("r") as file:
            data = json.load(file)
            return ManuscriptPageMetadata(**data)

    async with _PAGE_INFO_SEMAPHORE:
        manuscript_page_info = await get_manuscript_page_info(manuscript_page_id)

    with page_metadata_path.open("w") as file:
        file.write(json.dumps(dataclasses.asdict(manuscript_page_info)))

    return manuscript_page_info
