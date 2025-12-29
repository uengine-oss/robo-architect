"""Neo4j-backed store for the Event Storming workshop graph.

This is intentionally owned by the `event_storming` capability, rather than a generic `db/` layer.
"""

from datetime import datetime
from typing import Optional

from neo4j import AsyncGraphDatabase, AsyncDriver

from ...config import get_settings
from ...platform.observability.request_logging import RequestTimer, get_request_id, summarize_for_log
from ...platform.observability.smart_logger import SmartLogger
from .models import (
    Session,
    SessionCreate,
    SessionPhase,
    Sticker,
    StickerCreate,
    StickerUpdate,
    StickerType,
    Connection,
    ConnectionCreate,
    Position,
)


class EventStormingGraphStore:
    """Neo4j database manager for Event Storming sessions."""

    def __init__(self):
        self._driver: Optional[AsyncDriver] = None
        self._database: Optional[str] = None

    def _ctx(self) -> dict:
        rid = get_request_id()
        return {"request_id": rid} if rid else {}

    async def connect(self):
        """Establish connection to Neo4j."""
        t = RequestTimer()
        settings = get_settings()
        # Empty string should behave like "use Neo4j server default database".
        self._database = settings.neo4j_database.strip() or None
        SmartLogger.log(
            "INFO",
            "neo4j.connect.start",
            category="event_storming.graph_store",
            params={
                **self._ctx(),
                "neo4j_uri": settings.neo4j_uri,
                "neo4j_user": settings.neo4j_user,
                "database": self._database,
            },
        )
        self._driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
        )
        # Verify connectivity
        await self._driver.verify_connectivity()
        # Initialize schema
        await self._init_schema()
        SmartLogger.log(
            "INFO",
            "neo4j.connect.ok",
            category="event_storming.graph_store",
            params={**self._ctx(), "database": self._database, "duration_ms": t.ms()},
        )

    async def disconnect(self):
        """Close Neo4j connection."""
        t = RequestTimer()
        if self._driver:
            await self._driver.close()
        self._driver = None
        self._database = None
        SmartLogger.log(
            "INFO",
            "neo4j.disconnect.ok",
            category="event_storming.graph_store",
            params={**self._ctx(), "duration_ms": t.ms()},
        )

    async def _init_schema(self):
        """Initialize database schema with constraints and indexes."""
        t = RequestTimer()
        async with self._driver.session(database=self._database) as session:
            # Create constraints
            await session.run(
                """
                CREATE CONSTRAINT session_id IF NOT EXISTS
                FOR (s:Session) REQUIRE s.id IS UNIQUE
            """
            )
            await session.run(
                """
                CREATE CONSTRAINT sticker_id IF NOT EXISTS
                FOR (st:Sticker) REQUIRE st.id IS UNIQUE
            """
            )
            # Create indexes for performance
            await session.run(
                """
                CREATE INDEX session_created IF NOT EXISTS
                FOR (s:Session) ON (s.created_at)
            """
            )
        SmartLogger.log(
            "INFO",
            "neo4j.schema.init.ok",
            category="event_storming.graph_store",
            params={**self._ctx(), "database": self._database, "duration_ms": t.ms()},
        )

    # Session operations
    async def create_session(self, data: SessionCreate) -> Session:
        """Create a new event storming session."""
        t = RequestTimer()
        SmartLogger.log(
            "INFO",
            "graph.session.create.start",
            category="event_storming.graph_store",
            params={**self._ctx(), "data": summarize_for_log(data.model_dump(mode="json"))},
        )
        session_obj = Session(
            title=data.title,
            description=data.description,
            duration_minutes=data.duration_minutes,
        )

        async with self._driver.session(database=self._database) as session:
            await session.run(
                """
                CREATE (s:Session {
                    id: $id,
                    title: $title,
                    description: $description,
                    phase: $phase,
                    duration_minutes: $duration_minutes,
                    created_at: datetime($created_at),
                    started_at: null,
                    ended_at: null
                })
            """,
                {
                    "id": session_obj.id,
                    "title": session_obj.title,
                    "description": session_obj.description,
                    "phase": session_obj.phase.value,
                    "duration_minutes": session_obj.duration_minutes,
                    "created_at": session_obj.created_at.isoformat(),
                },
            )

        SmartLogger.log(
            "INFO",
            "graph.session.create.ok",
            category="event_storming.graph_store",
            params={**self._ctx(), "session_id": session_obj.id, "duration_ms": t.ms()},
        )
        return session_obj

    async def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        t = RequestTimer()
        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                """
                MATCH (s:Session {id: $id})
                RETURN s
            """,
                {"id": session_id},
            )
            record = await result.single()

            if not record:
                SmartLogger.log(
                    "DEBUG",
                    "graph.session.get.not_found",
                    category="event_storming.graph_store",
                    params={**self._ctx(), "session_id": session_id, "duration_ms": t.ms()},
                )
                return None

            node = record["s"]
            out = Session(
                id=node["id"],
                title=node["title"],
                description=node.get("description"),
                phase=SessionPhase(node["phase"]),
                duration_minutes=node["duration_minutes"],
                created_at=node["created_at"].to_native()
                if node.get("created_at")
                else datetime.utcnow(),
                started_at=node["started_at"].to_native() if node.get("started_at") else None,
                ended_at=node["ended_at"].to_native() if node.get("ended_at") else None,
            )
            SmartLogger.log(
                "DEBUG",
                "graph.session.get.ok",
                category="event_storming.graph_store",
                params={
                    **self._ctx(),
                    "session_id": session_id,
                    "phase": out.phase.value,
                    "duration_minutes": out.duration_minutes,
                    "duration_ms": t.ms(),
                },
            )
            return out

    async def update_session_phase(self, session_id: str, phase) -> bool:
        """Update session phase."""
        t = RequestTimer()
        # Handle both SessionPhase enum and string
        phase_value = phase.value if hasattr(phase, "value") else str(phase)

        SmartLogger.log(
            "INFO",
            "graph.session.phase.update.start",
            category="event_storming.graph_store",
            params={**self._ctx(), "session_id": session_id, "phase": phase_value},
        )
        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                """
                MATCH (s:Session {id: $id})
                SET s.phase = $phase
                RETURN s
            """,
                {"id": session_id, "phase": phase_value},
            )
            record = await result.single()
            ok = record is not None
            SmartLogger.log(
                "INFO",
                "graph.session.phase.update.ok" if ok else "graph.session.phase.update.not_found",
                category="event_storming.graph_store",
                params={**self._ctx(), "session_id": session_id, "phase": phase_value, "duration_ms": t.ms(), "ok": ok},
            )
            return ok

    async def start_session(self, session_id: str) -> bool:
        """Mark session as started."""
        t = RequestTimer()
        SmartLogger.log(
            "INFO",
            "graph.session.start.start",
            category="event_storming.graph_store",
            params={**self._ctx(), "session_id": session_id},
        )
        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                """
                MATCH (s:Session {id: $id})
                SET s.started_at = datetime()
                RETURN s
            """,
                {"id": session_id},
            )
            record = await result.single()
            ok = record is not None
            SmartLogger.log(
                "INFO",
                "graph.session.start.ok" if ok else "graph.session.start.not_found",
                category="event_storming.graph_store",
                params={**self._ctx(), "session_id": session_id, "duration_ms": t.ms(), "ok": ok},
            )
            return ok

    async def end_session(self, session_id: str) -> bool:
        """Mark session as ended."""
        t = RequestTimer()
        SmartLogger.log(
            "INFO",
            "graph.session.end.start",
            category="event_storming.graph_store",
            params={**self._ctx(), "session_id": session_id},
        )
        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                """
                MATCH (s:Session {id: $id})
                SET s.ended_at = datetime()
                RETURN s
            """,
                {"id": session_id},
            )
            record = await result.single()
            ok = record is not None
            SmartLogger.log(
                "INFO",
                "graph.session.end.ok" if ok else "graph.session.end.not_found",
                category="event_storming.graph_store",
                params={**self._ctx(), "session_id": session_id, "duration_ms": t.ms(), "ok": ok},
            )
            return ok

    # Sticker operations
    async def create_sticker(self, session_id: str, data: StickerCreate) -> Sticker:
        """Create a new sticker in session."""
        t = RequestTimer()
        SmartLogger.log(
            "INFO",
            "graph.sticker.create.start",
            category="event_storming.graph_store",
            params={**self._ctx(), "session_id": session_id, "data": summarize_for_log(data.model_dump(mode="json"))},
        )
        sticker = Sticker(type=data.type, text=data.text, position=data.position, author=data.author)

        async with self._driver.session(database=self._database) as session:
            await session.run(
                """
                MATCH (s:Session {id: $session_id})
                CREATE (st:Sticker {
                    id: $id,
                    type: $type,
                    text: $text,
                    x: $x,
                    y: $y,
                    author: $author,
                    created_at: datetime($created_at),
                    updated_at: datetime($updated_at)
                })
                CREATE (s)-[:HAS_STICKER]->(st)
            """,
                {
                    "session_id": session_id,
                    "id": sticker.id,
                    "type": sticker.type.value,
                    "text": sticker.text,
                    "x": sticker.position.x,
                    "y": sticker.position.y,
                    "author": sticker.author,
                    "created_at": sticker.created_at.isoformat(),
                    "updated_at": sticker.updated_at.isoformat(),
                },
            )

        SmartLogger.log(
            "INFO",
            "graph.sticker.create.ok",
            category="event_storming.graph_store",
            params={**self._ctx(), "session_id": session_id, "sticker_id": sticker.id, "type": sticker.type.value, "duration_ms": t.ms()},
        )
        return sticker

    async def get_stickers(self, session_id: str) -> list[Sticker]:
        """Get all stickers in a session."""
        t = RequestTimer()
        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                """
                MATCH (s:Session {id: $session_id})-[:HAS_STICKER]->(st:Sticker)
                RETURN st
                ORDER BY st.created_at
            """,
                {"session_id": session_id},
            )

            stickers: list[Sticker] = []
            async for record in result:
                node = record["st"]
                stickers.append(
                    Sticker(
                        id=node["id"],
                        type=StickerType(node["type"]),
                        text=node["text"],
                        position=Position(x=node["x"], y=node["y"]),
                        author=node["author"],
                        created_at=node["created_at"].to_native(),
                        updated_at=node["updated_at"].to_native(),
                    )
                )

            SmartLogger.log(
                "DEBUG",
                "graph.sticker.list.ok",
                category="event_storming.graph_store",
                params={
                    **self._ctx(),
                    "session_id": session_id,
                    "stickers": summarize_for_log(
                        [{"id": s.id, "type": s.type.value} for s in stickers]
                    ),
                    "duration_ms": t.ms(),
                },
            )
            return stickers

    async def update_sticker(self, sticker_id: str, data: StickerUpdate) -> Optional[Sticker]:
        """Update a sticker."""
        t = RequestTimer()
        SmartLogger.log(
            "INFO",
            "graph.sticker.update.start",
            category="event_storming.graph_store",
            params={**self._ctx(), "sticker_id": sticker_id, "data": summarize_for_log(data.model_dump(mode="json"))},
        )
        updates = ["st.updated_at = datetime()"]
        params: dict = {"id": sticker_id}

        if data.text is not None:
            updates.append("st.text = $text")
            params["text"] = data.text

        if data.position is not None:
            updates.append("st.x = $x, st.y = $y")
            params["x"] = data.position.x
            params["y"] = data.position.y

        query = f"""
            MATCH (st:Sticker {{id: $id}})
            SET {', '.join(updates)}
            RETURN st
        """

        async with self._driver.session(database=self._database) as session:
            result = await session.run(query, params)
            record = await result.single()

            if not record:
                SmartLogger.log(
                    "INFO",
                    "graph.sticker.update.not_found",
                    category="event_storming.graph_store",
                    params={**self._ctx(), "sticker_id": sticker_id, "duration_ms": t.ms()},
                )
                return None

            node = record["st"]
            out = Sticker(
                id=node["id"],
                type=StickerType(node["type"]),
                text=node["text"],
                position=Position(x=node["x"], y=node["y"]),
                author=node["author"],
                created_at=node["created_at"].to_native(),
                updated_at=node["updated_at"].to_native(),
            )
            SmartLogger.log(
                "INFO",
                "graph.sticker.update.ok",
                category="event_storming.graph_store",
                params={**self._ctx(), "sticker_id": sticker_id, "duration_ms": t.ms()},
            )
            return out

    async def delete_sticker(self, sticker_id: str) -> bool:
        """Delete a sticker and its connections."""
        t = RequestTimer()
        SmartLogger.log(
            "INFO",
            "graph.sticker.delete.start",
            category="event_storming.graph_store",
            params={**self._ctx(), "sticker_id": sticker_id},
        )
        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                """
                MATCH (st:Sticker {id: $id})
                DETACH DELETE st
                RETURN count(st) as deleted
            """,
                {"id": sticker_id},
            )
            record = await result.single()
            ok = record["deleted"] > 0
            SmartLogger.log(
                "INFO",
                "graph.sticker.delete.ok" if ok else "graph.sticker.delete.not_found",
                category="event_storming.graph_store",
                params={**self._ctx(), "sticker_id": sticker_id, "deleted": record["deleted"], "duration_ms": t.ms(), "ok": ok},
            )
            return ok

    # Connection operations
    async def create_connection(self, data: ConnectionCreate) -> Connection:
        """Create a connection between stickers."""
        t = RequestTimer()
        SmartLogger.log(
            "INFO",
            "graph.connection.create.start",
            category="event_storming.graph_store",
            params={**self._ctx(), "data": summarize_for_log(data.model_dump(mode="json"))},
        )
        connection = Connection(source_id=data.source_id, target_id=data.target_id, label=data.label)

        async with self._driver.session(database=self._database) as session:
            await session.run(
                """
                MATCH (source:Sticker {id: $source_id})
                MATCH (target:Sticker {id: $target_id})
                CREATE (source)-[:TRIGGERS {
                    id: $id,
                    label: $label,
                    created_at: datetime($created_at)
                }]->(target)
            """,
                {
                    "source_id": connection.source_id,
                    "target_id": connection.target_id,
                    "id": connection.id,
                    "label": connection.label,
                    "created_at": connection.created_at.isoformat(),
                },
            )

        SmartLogger.log(
            "INFO",
            "graph.connection.create.ok",
            category="event_storming.graph_store",
            params={
                **self._ctx(),
                "connection_id": connection.id,
                "source_id": connection.source_id,
                "target_id": connection.target_id,
                "duration_ms": t.ms(),
            },
        )
        return connection

    async def get_connections(self, session_id: str) -> list[Connection]:
        """Get all connections in a session."""
        t = RequestTimer()
        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                """
                MATCH (s:Session {id: $session_id})-[:HAS_STICKER]->(source:Sticker)
                MATCH (source)-[r:TRIGGERS]->(target:Sticker)
                RETURN r, source.id as source_id, target.id as target_id
            """,
                {"session_id": session_id},
            )

            connections: list[Connection] = []
            async for record in result:
                rel = record["r"]
                connections.append(
                    Connection(
                        id=rel["id"],
                        source_id=record["source_id"],
                        target_id=record["target_id"],
                        label=rel.get("label"),
                        created_at=rel["created_at"].to_native(),
                    )
                )

            SmartLogger.log(
                "DEBUG",
                "graph.connection.list.ok",
                category="event_storming.graph_store",
                params={
                    **self._ctx(),
                    "session_id": session_id,
                    "connections": summarize_for_log(
                        [{"id": c.id, "source_id": c.source_id, "target_id": c.target_id} for c in connections]
                    ),
                    "duration_ms": t.ms(),
                },
            )
            return connections

    async def delete_connection(self, connection_id: str) -> bool:
        """Delete a connection."""
        t = RequestTimer()
        SmartLogger.log(
            "INFO",
            "graph.connection.delete.start",
            category="event_storming.graph_store",
            params={**self._ctx(), "connection_id": connection_id},
        )
        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                """
                MATCH ()-[r:TRIGGERS {id: $id}]->()
                DELETE r
                RETURN count(r) as deleted
            """,
                {"id": connection_id},
            )
            record = await result.single()
            ok = record["deleted"] > 0
            SmartLogger.log(
                "INFO",
                "graph.connection.delete.ok" if ok else "graph.connection.delete.not_found",
                category="event_storming.graph_store",
                params={**self._ctx(), "connection_id": connection_id, "deleted": record["deleted"], "duration_ms": t.ms(), "ok": ok},
            )
            return ok


# Global store instance (owned by this capability)
graph = EventStormingGraphStore()


