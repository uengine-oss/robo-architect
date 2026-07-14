import unittest

from api.platform.neo4j_context import Neo4jOverride, get_override, set_override


class Neo4jContextTest(unittest.TestCase):
    def tearDown(self) -> None:
        set_override(None)

    def test_missing_uri_means_environment_fallback(self) -> None:
        self.assertIsNone(Neo4jOverride.from_headers({}))

    def test_request_override_is_explicitly_cleared(self) -> None:
        override = Neo4jOverride.from_headers({
            "x-neo4j-uri": "bolt://selected:7687",
            "x-neo4j-user": "neo4j",
            "x-neo4j-password": "secret",
            "x-neo4j-database": "selected",
        })
        set_override(override)
        self.assertEqual(get_override(), override)
        set_override(None)
        self.assertIsNone(get_override())


if __name__ == "__main__":
    unittest.main()
