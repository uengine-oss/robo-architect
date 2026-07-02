# Stage Artifact Contracts

Every stage artifact must include `stage`.

Top-level keys:

- `DiscoverArtifact`: `events`, `pivotalEvents`, `hotspots`
- `DecomposeArtifact`: `subDomains`, `couplingNotes`
- `StrategizeArtifact`: `classifications`, `ubiquitousLanguage`, `businessDecisions`
- `ConnectArtifact`: `interactions`, `couplingWarnings`, `messagingChannel`
- `DefineArtifact`: `contexts`
- `TacticalArtifact`: `aggregates`

`TACTICAL` aggregates should include commands, events, state transitions, and at least two invariants when the domain provides enough signal.
