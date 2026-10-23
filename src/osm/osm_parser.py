from src.osm.objects.node import Node
from src.osm.objects.way import Way
from src.osm.objects.relation import Relation
from src.osm.objects.osm_data import OSMData
from src.osm.objects.relation_member import RelationMember

# Gemeinsames leeres Tag-Dict fuer Knoten ohne Tags (spart bei zig Millionen
# Knoten viel Arbeitsspeicher). Wird nirgends veraendert.
_NO_TAGS: dict = {}


class OSMParser:
    """
    Wandelt Overpass-JSON in OSMData um.
    """

    def parse(
        self,
        data: dict
    ) -> OSMData:

        osm = OSMData()

        self.parse_into(osm, data)

        print("OSM Parser:")
        print(f"  Nodes     : {osm.node_count}")
        print(f"  Ways      : {osm.way_count}")
        print(f"  Relations : {osm.relation_count}")

        return osm

    def new_data(self) -> OSMData:
        """Leerer Container fuer parse_into."""

        return OSMData()

    def parse_into(
        self,
        osm: OSMData,
        data: dict
    ) -> OSMData:
        """
        Fuegt die Elemente aus `data` zu `osm` hinzu (gleiche ID = ersetzt).
        So lassen sich Kacheln nacheinander einlesen und danach freigeben.
        """

        for element in data.get("elements", []):

            element_type = element.get("type")

            # -----------------------------------------
            # Node
            # -----------------------------------------

            if element_type == "node":

                node = Node(
                    id=element["id"],
                    lat=element["lat"],
                    lon=element["lon"],
                    tags=element.get("tags") or _NO_TAGS
                )

                osm.add_node(node)

            # -----------------------------------------
            # Way
            # -----------------------------------------

            elif element_type == "way":

                way = Way(
                    id=element["id"],
                    nodes=element.get("nodes", []),
                    tags=element.get("tags", {})
                )

                osm.add_way(way)

            # -----------------------------------------
            # Relation
            # -----------------------------------------

            elif element_type == "relation":

                members = []

                for member in element.get("members", []):

                    members.append(
                        RelationMember(
                            type=member["type"],
                            ref=member["ref"],
                            role=member.get("role", "")
                        )
                    )

                relation = Relation(
                    id=element["id"],
                    members=members,
                    tags=element.get("tags", {})
                )

                osm.add_relation(relation)

        return osm