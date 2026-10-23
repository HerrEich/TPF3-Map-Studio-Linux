import unittest

from src.osm.osm_parser import OSMParser
from src.osm.objects.node import Node
from src.osm.objects.way import Way


def _tile(*nodes, ways=()):
    elements = [
        {"type": "node", "id": i, "lat": 48.0 + i, "lon": 8.0, **({"tags": t} if t else {})}
        for i, t in nodes
    ]
    elements += [{"type": "way", "id": i, "nodes": n, "tags": {"highway": "path"}} for i, n in ways]
    return {"elements": elements}


class ParserStreamingTest(unittest.TestCase):

    def test_kacheln_nacheinander_einlesen(self):
        parser = OSMParser()
        osm = parser.new_data()
        parser.parse_into(osm, _tile((1, None), (2, {"a": "b"}), ways=[(10, [1, 2])]))
        parser.parse_into(osm, _tile((2, {"a": "b"}), (3, None), ways=[(10, [1, 2]), (11, [2, 3])]))
        self.assertEqual(sorted(osm.nodes), [1, 2, 3])      # Doppelte nur einmal
        self.assertEqual(sorted(osm.ways), [10, 11])
        self.assertEqual(osm.nodes[2].tags, {"a": "b"})

    def test_gleiches_ergebnis_wie_parse(self):
        data = _tile((1, None), (2, {"x": "y"}), ways=[(5, [1, 2])])
        a = OSMParser().parse(data)
        parser = OSMParser()
        b = parser.new_data()
        parser.parse_into(b, data)
        self.assertEqual(a.nodes, b.nodes)
        self.assertEqual(a.ways, b.ways)

    def test_knoten_ohne_tags_haben_leere_tags(self):
        osm = OSMParser().parse(_tile((1, None)))
        self.assertEqual(osm.nodes[1].tags, {})

    def test_node_und_way_ohne_instanz_dict(self):
        self.assertFalse(hasattr(Node(id=1, lat=0.0, lon=0.0), "__dict__"))
        self.assertFalse(hasattr(Way(id=1), "__dict__"))


if __name__ == "__main__":
    unittest.main()
