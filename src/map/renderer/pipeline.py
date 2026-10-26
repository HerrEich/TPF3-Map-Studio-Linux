from collections.abc import Callable

from src.map.layer import GeometryType
from src.map.renderer.render_item import RenderItem


class RenderPipeline:
    """Erzeugt RenderItems aus OSM-Objekten."""

    def __init__(
        self,
        selector: Callable,
        style_resolver,
        geometry_type: GeometryType,
    ):
        self.selector = selector
        self.style_resolver = style_resolver
        self.geometry_type = geometry_type

    def build(
        self,
        osm,
        zoom: int | None = None,
        limit: int | None = None,
        rank: Callable | None = None,
    ) -> list[RenderItem]:
        """Baut RenderItems. Mit limit und rank bleiben bei zu vielen
        Objekten die wichtigsten (kleinster rank) erhalten."""

        items: list[RenderItem] = []

        objects = self.selector(osm)

        if limit is not None and rank is not None:
            objects = list(objects)
            if len(objects) > limit:
                # sorted ist stabil: gleiche Wichtigkeit behaelt OSM-Reihenfolge
                objects = sorted(objects, key=rank)

        for obj in objects:

            if limit is not None and len(items) >= limit:
                break

            geometry = osm.get_geometry(obj.id)

            if geometry is None:
                continue

            style = self.style_resolver.resolve(
                obj,
                zoom=zoom,
            )

            items.append(
                RenderItem(
                    id=obj.id,
                    type=self.geometry_type.value,
                    geometry=geometry,
                    style=style.to_dict(),
                    properties=dict(
                        getattr(obj, "tags", {})
                    ),
                )
            )

        return items