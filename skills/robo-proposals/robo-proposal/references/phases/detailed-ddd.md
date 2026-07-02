# Detailed DDD

Use `stage:` to select one stage.

Strategic stages:

- `DISCOVER`: event storming, pivotal events, hotspots, actors, external systems.
- `DECOMPOSE`: subdomain map, responsibilities, coupling notes.
- `STRATEGIZE`: Core/Supporting/Generic classification and strategic memory.

Tactical stages:

- `CONNECT`: Event/Command/Query interactions, sync/pubsub coupling, messaging channel.
- `DEFINE`: Bounded Context Canvas.
- `TACTICAL`: Aggregate Design Canvas, invariants, commands, events, throughput/size.

Output top-level key:

- `DiscoverArtifact`
- `DecomposeArtifact`
- `StrategizeArtifact`
- `ConnectArtifact`
- `DefineArtifact`
- `TacticalArtifact`

Do not output final Strategic or Tactical Diff from these stages. Consolidation happens in the diff phase.
