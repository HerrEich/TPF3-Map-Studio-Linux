from dataclasses import dataclass, field


@dataclass(slots=True)
class Node:
    """
    OpenStreetMap-Knoten.
    """

    id: int

    lat: float

    lon: float

    tags: dict[str, str] = field(default_factory=dict)