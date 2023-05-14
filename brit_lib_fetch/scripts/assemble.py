import json
import pathlib
from loguru import logger
from brit_lib_fetch.model import ManuscriptMetadata, ManuscriptPageMetadata
from PIL import Image

BASE_DIRECTORY = pathlib.Path("downloaded_manuscript")


def assemble_page(page_metadata: ManuscriptPageMetadata) -> None:
    page_dir = BASE_DIRECTORY.joinpath(page_metadata.id)

    result_path = BASE_DIRECTORY.joinpath(
        f"assembled-{page_metadata.id}.{page_metadata.format}"
    )

    if result_path.exists():
        logger.warning(f"Assembled result already present, skipping: {result_path}")
        return

    assembled_page = Image.new("RGB", (page_metadata.width, page_metadata.height))

    for x in range(page_metadata.last_tile_x):
        for y in range(page_metadata.last_tile_y):
            part = Image.open(page_dir.joinpath(f"{x}-{y}.{page_metadata.format}"))

            if x == 0 and y == 0:
                assembled_page.paste(part, (0, 0))
                continue

            assembled_page.paste(
                part,
                (
                    x * page_metadata.tile_size - page_metadata.tile_overlap,
                    y * page_metadata.tile_size - page_metadata.tile_overlap,
                ),
            )

    assembled_page.save(result_path)


def main() -> None:
    with BASE_DIRECTORY.joinpath(".manuscript_metadata").open("r") as file:
        json_data = json.load(file)
    manuscript_data = ManuscriptMetadata(**json_data)

    for page_id in manuscript_data.page_id_list:
        page_dir = BASE_DIRECTORY.joinpath(page_id)

        with page_dir.joinpath(".metadata").open("r") as file:
            json_data = json.load(file)

        manuscript_page = ManuscriptPageMetadata(**json_data)

        try:
            assemble_page(manuscript_page)
        except Exception as e:
            logger.exception("Failed assembling a page", exc_info=e)


if __name__ == "__main__":
    main()
