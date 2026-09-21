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

    def test_selected_project_graph_wins_over_connection_default(self) -> None:
        override = Neo4jOverride.from_headers({
            "x-neo4j-uri": "bolt://selected:7687",
            "x-neo4j-user": "neo4j",
            "x-neo4j-password": "secret",
            "x-neo4j-database": "connection_default",
            "x-project-graph": "prj_current",
        })

        self.assertIsNotNone(override)
        self.assertEqual(override.database, "prj_current")

    def test_connection_default_is_used_without_selected_project(self) -> None:
        override = Neo4jOverride.from_headers({
            "x-neo4j-uri": "bolt://selected:7687",
            "x-neo4j-database": "connection_default",
        })

        self.assertIsNotNone(override)
        self.assertEqual(override.database, "connection_default")


if __name__ == "__main__":
    unittest.main()
