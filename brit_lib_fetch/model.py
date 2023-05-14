from dataclasses import dataclass


@dataclass(frozen=True)
class ManuscriptMetadata:
    page_id_list: list[str]
    magnification_indices: list[int]

    @property
    def max_magnification_index(self) -> int:
        return max(self.magnification_indices)


@dataclass(frozen=True)
class ManuscriptPageMetadata:
    id: str
    width: int
    height: int
    tile_size: int
    format: str
    tile_overlap: int

    @property
    def last_tile_x(self) -> int:
        return self.width // self.tile_size

    @property
    def last_tile_y(self) -> int:
        return self.height // self.tile_size
