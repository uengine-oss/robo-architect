"""Neo4j database connection and operations."""
from contextlib import asynccontextmanager
from typing import Optional
from neo4j import AsyncGraphDatabase, AsyncDriver
from ..config import get_settings
from ..models.session import (
    Session, SessionCreate, SessionPhase,
    Sticker, StickerCreate, StickerUpdate, StickerType,
    Connection, ConnectionCreate, Position
)
from datetime import datetime


class Neo4jDB:
    """Neo4j database manager."""
    
    def __init__(self):
        self._driver: Optional[AsyncDriver] = None
    
    async def connect(self):
        """Establish connection to Neo4j."""
        settings = get_settings()
        self._driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password)
        )
        # Verify connectivity
        await self._driver.verify_connectivity()
        # Initialize schema
        await self._init_schema()
    
    async def disconnect(self):
        """Close Neo4j connection."""
        if self._driver:
            await self._driver.close()
    
    async def _init_schema(self):
        """Initialize database schema with constraints and indexes."""
        async with self._driver.session() as session:
            # Create constraints
            await session.run("""
                CREATE CONSTRAINT session_id IF NOT EXISTS
                FOR (s:Session) REQUIRE s.id IS UNIQUE
            """)
            await session.run("""
                CREATE CONSTRAINT sticker_id IF NOT EXISTS
                FOR (st:Sticker) REQUIRE st.id IS UNIQUE
            """)
            # Create indexes for performance
            await session.run("""
                CREATE INDEX session_created IF NOT EXISTS
                FOR (s:Session) ON (s.created_at)
            """)
    
    # Session operations
    async def create_session(self, data: SessionCreate) -> Session:
        """Create a new event storming session."""
        session_obj = Session(
            title=data.title,
            description=data.description,
            duration_minutes=data.duration_minutes
        )
        
        async with self._driver.session() as session:
            await session.run("""
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
            """, {
                "id": session_obj.id,
                "title": session_obj.title,
                "description": session_obj.description,
                "phase": session_obj.phase.value,
                "duration_minutes": session_obj.duration_minutes,
                "created_at": session_obj.created_at.isoformat()
            })
        
        return session_obj
    
    async def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        async with self._driver.session() as session:
            result = await session.run("""
                MATCH (s:Session {id: $id})
                RETURN s
            """, {"id": session_id})
            record = await result.single()
            
            if not record:
                return None
            
            node = record["s"]
            return Session(
                id=node["id"],
                title=node["title"],
                description=node.get("description"),
                phase=SessionPhase(node["phase"]),
                duration_minutes=node["duration_minutes"],
                created_at=node["created_at"].to_native() if node.get("created_at") else datetime.utcnow(),
                started_at=node["started_at"].to_native() if node.get("started_at") else None,
                ended_at=node["ended_at"].to_native() if node.get("ended_at") else None
            )
    
    async def update_session_phase(self, session_id: str, phase) -> bool:
        """Update session phase."""
        # Handle both SessionPhase enum and string
        phase_value = phase.value if hasattr(phase, 'value') else str(phase)
        
        async with self._driver.session() as session:
            result = await session.run("""
                MATCH (s:Session {id: $id})
                SET s.phase = $phase
                RETURN s
            """, {"id": session_id, "phase": phase_value})
            record = await result.single()
            return record is not None
    
    async def start_session(self, session_id: str) -> bool:
        """Mark session as started."""
        async with self._driver.session() as session:
            result = await session.run("""
                MATCH (s:Session {id: $id})
                SET s.started_at = datetime()
                RETURN s
            """, {"id": session_id})
            record = await result.single()
            return record is not None
    
    # Sticker operations
    async def create_sticker(self, session_id: str, data: StickerCreate) -> Sticker:
        """Create a new sticker in session."""
        sticker = Sticker(
            type=data.type,
            text=data.text,
            position=data.position,
            author=data.author
        )
        
        async with self._driver.session() as session:
            await session.run("""
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
            """, {
                "session_id": session_id,
                "id": sticker.id,
                "type": sticker.type.value,
                "text": sticker.text,
                "x": sticker.position.x,
                "y": sticker.position.y,
                "author": sticker.author,
                "created_at": sticker.created_at.isoformat(),
                "updated_at": sticker.updated_at.isoformat()
            })
        
        return sticker
    
    async def get_stickers(self, session_id: str) -> list[Sticker]:
        """Get all stickers in a session."""
        async with self._driver.session() as session:
            result = await session.run("""
                MATCH (s:Session {id: $session_id})-[:HAS_STICKER]->(st:Sticker)
                RETURN st
                ORDER BY st.created_at
            """, {"session_id": session_id})
            
            stickers = []
            async for record in result:
                node = record["st"]
                stickers.append(Sticker(
                    id=node["id"],
                    type=StickerType(node["type"]),
                    text=node["text"],
                    position=Position(x=node["x"], y=node["y"]),
                    author=node["author"],
                    created_at=node["created_at"].to_native(),
                    updated_at=node["updated_at"].to_native()
                ))
            
            return stickers
    
    async def update_sticker(self, sticker_id: str, data: StickerUpdate) -> Optional[Sticker]:
        """Update a sticker."""
        updates = ["st.updated_at = datetime()"]
        params = {"id": sticker_id}
        
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
        
        async with self._driver.session() as session:
            result = await session.run(query, params)
            record = await result.single()
            
            if not record:
                return None
            
            node = record["st"]
            return Sticker(
                id=node["id"],
                type=StickerType(node["type"]),
                text=node["text"],
                position=Position(x=node["x"], y=node["y"]),
                author=node["author"],
                created_at=node["created_at"].to_native(),
                updated_at=node["updated_at"].to_native()
            )
    
    async def delete_sticker(self, sticker_id: str) -> bool:
        """Delete a sticker and its connections."""
        async with self._driver.session() as session:
            result = await session.run("""
                MATCH (st:Sticker {id: $id})
                DETACH DELETE st
                RETURN count(st) as deleted
            """, {"id": sticker_id})
            record = await result.single()
            return record["deleted"] > 0
    
    # Connection operations
    async def create_connection(self, data: ConnectionCreate) -> Connection:
        """Create a connection between stickers."""
        connection = Connection(
            source_id=data.source_id,
            target_id=data.target_id,
            label=data.label
        )
        
        async with self._driver.session() as session:
            await session.run("""
                MATCH (source:Sticker {id: $source_id})
                MATCH (target:Sticker {id: $target_id})
                CREATE (source)-[:TRIGGERS {
                    id: $id,
                    label: $label,
                    created_at: datetime($created_at)
                }]->(target)
            """, {
                "source_id": connection.source_id,
                "target_id": connection.target_id,
                "id": connection.id,
                "label": connection.label,
                "created_at": connection.created_at.isoformat()
            })
        
        return connection
    
    async def get_connections(self, session_id: str) -> list[Connection]:
        """Get all connections in a session."""
        async with self._driver.session() as session:
            result = await session.run("""
                MATCH (s:Session {id: $session_id})-[:HAS_STICKER]->(source:Sticker)
                MATCH (source)-[r:TRIGGERS]->(target:Sticker)
                RETURN r, source.id as source_id, target.id as target_id
            """, {"session_id": session_id})
            
            connections = []
            async for record in result:
                rel = record["r"]
                connections.append(Connection(
                    id=rel["id"],
                    source_id=record["source_id"],
                    target_id=record["target_id"],
                    label=rel.get("label"),
                    created_at=rel["created_at"].to_native()
                ))
            
            return connections
    
    async def delete_connection(self, connection_id: str) -> bool:
        """Delete a connection."""
        async with self._driver.session() as session:
            result = await session.run("""
                MATCH ()-[r:TRIGGERS {id: $id}]->()
                DELETE r
                RETURN count(r) as deleted
            """, {"id": connection_id})
            record = await result.single()
            return record["deleted"] > 0


# Global database instance
db = Neo4jDB()

