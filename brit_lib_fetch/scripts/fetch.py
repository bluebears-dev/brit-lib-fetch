import asyncio

from brit_lib_fetch.manuscript import (
    BASE_DIR,
    load_page_metadata,
    fetch_and_save_tiles,
    load_manuscript_metadata,
)
from loguru import logger
import requests_cache

USER_AGENT = "Mozilla/5.0 (Linux; Android 13; ONEPLUS A5010) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Mobile Safari/537.36"  # noqa: E501


async def _run():
    url = "https://www.bl.uk/manuscripts/Viewer.aspx?ref=royal_ms_2_a_xvi_fs001r"
    manuscript_data = await load_manuscript_metadata(url)

    logger.info(
        f"Manuscript has {len(manuscript_data.page_id_list)} pages and {manuscript_data.max_magnification_index} is the largest magnification index"  # noqa: E501
    )

    async with asyncio.TaskGroup() as group:
        for manuscript_page_id in manuscript_data.page_id_list:
            page_dir = BASE_DIR.joinpath(manuscript_page_id)
            if not page_dir.exists():
                logger.info(f"Creating directory '{manuscript_page_id}'")
                page_dir.mkdir()

            manuscript_page_info = await load_page_metadata(manuscript_page_id)

            logger.info(f"Spawning task for fetching {manuscript_page_info}")
            group.create_task(
                fetch_and_save_tiles(manuscript_data, manuscript_page_info)
            )


def main() -> None:
    requests_cache.install_cache(cache_name="bl_uk_cache", expire_after=360)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(_run())


if __name__ == "__main__":
    main()
