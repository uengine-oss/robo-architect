from __future__ import annotations

from datetime import datetime

from api.features.prd_generation.prd_api_contracts import Database, Framework, FrontendFramework, TechStackConfig


def generate_main_prd(bcs: list[dict], config: TechStackConfig) -> str:
    prd = f"""# {config.project_name} - Product Requirements Document

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 🚨 CRITICAL: Before Starting Implementation

**When you are asked to "진행해" (proceed) or start implementation, you MUST:**

1. **Read the BC Specification** (`specs/{{bc_name}}_spec.md`) FIRST - This contains ALL implementation details:
   - ✅ **Aggregates**: Complete properties, invariants, enumerations, value objects
   - ✅ **Commands**: Input schemas, properties, actor requirements
   - ✅ **Events**: Schemas, properties, publishing requirements
   - ✅ **ReadModels**: Properties, query patterns, actor filtering
   - ✅ **Policies**: Trigger events, invoke commands, cross-BC relationships
   - ✅ **UI Wireframes**: Template HTML, attached Commands/ReadModels, descriptions
   - ✅ **GWT Tests**: Complete test scenarios with Given/When/Then

2. **Reference Cursor Rules** (use @mention):
   - ✅ `@.cursorrules` - Global DDD principles
   - ✅ `@ddd-principles` - DDD patterns (always applied)
   - ✅ `@eventstorming-implementation` - Sticker-to-code mapping (Command → API, Event → Message, ReadModel → Query API, UI → Component)
   - ✅ `@gwt-test-generation` - GWT test patterns
   - ✅ `@{config.framework.value}` - Tech stack specific guidelines (e.g., `@spring-boot`)
   - ✅ `@{config.frontend_framework.value if config.frontend_framework else "N/A"}` - Frontend guidelines (if frontend included)

3. **Read Frontend PRD** (if frontend included) - **MUST READ TOGETHER WITH THIS PRD**:
   - ✅ `Frontend-PRD.md` - Frontend architecture, implementation strategy, UI guidelines
   - ✅ **Frontend Implementation Strategy**: Start with main landing page, then add BC features incrementally
   - ✅ **Reference both PRD.md and Frontend-PRD.md** when implementing frontend

**DO NOT start coding without reading these files!**

**For Frontend Implementation**:
- **Read PRD.md AND Frontend-PRD.md together** before starting
- **Start with main landing page** (navigation foundation)
- **Add BC features incrementally** (one BC at a time)
- **Reference BC specs** for detailed wireframe templates

## ⚠️ Important: Read All Reference Files

**This PRD provides the high-level architecture and principles. For implementation, you MUST read the following files:**

1. **BC Specifications** (`specs/{{bc_name}}_spec.md`): Complete detailed requirements for each Bounded Context
   - All aggregates with properties, invariants, enumerations, value objects
   - All commands with input schemas and properties
   - All events with schemas and properties
   - All ReadModels with properties
   - All Policies with trigger/invoke relationships
   - **All UI Wireframes with templates and attached Commands/ReadModels**
   - All GWT test cases with scenarios

2. **AI Assistant Guides** (use @mention in Cursor):
   - **Cursor**: `@.cursorrules` (global DDD rules) + `@{{framework}}` (tech stack specific, e.g., `@spring-boot`)
   - **Cursor Rules**: `@ddd-principles`, `@eventstorming-implementation`, `@gwt-test-generation`
   - **Frontend Rules**: `@{{frontend_framework}}` (if frontend included, e.g., `@vue`, `@react`)
   - **Claude**: `.claude/agents/{{bc_name}}_agent.md` (BC-specific agent config)

3. **Frontend PRD** (if frontend included) - **MUST READ TOGETHER WITH THIS PRD**:
   - `Frontend-PRD.md` - Frontend architecture, implementation strategy (main page first, then BC features), UI guidelines
   - **For Frontend**: Always read both PRD.md and Frontend-PRD.md together before starting

4. **Project Context**: `CLAUDE.md` for overall project overview

**When implementing code for a specific BC, always:**
- Start with this PRD for architecture understanding
- **Read the BC spec file (`specs/{{bc_name}}_spec.md`) FIRST** - It contains ALL details (aggregates, commands, events, ReadModels, Policies, UI wireframes, GWT tests)
- **Reference Cursor rules** using @mention (`@ddd-principles`, `@eventstorming-implementation`, `@{config.framework.value}`, etc.)
- **For Frontend**: **Read Frontend-PRD.md TOGETHER with this PRD** - Start with main landing page, then add BC features incrementally
- Follow the AI assistant guide for implementation patterns
- Refer to other BC specs when implementing cross-BC features

## Technology Stack

| Component | Choice |
|-----------|--------|
| **Language** | {config.language.value} |
| **Framework** | {config.framework.value} |
| **Messaging** | {config.messaging.value} |
| **Database** | {config.database.value} |
| **Deployment** | {config.deployment.value} |

## Bounded Contexts
"""

    prd += "\n| BC Name | Aggregates | Commands | Events | ReadModels | Policies | UIs |\n"
    prd += "|---------|------------|----------|--------|------------|----------|-----|\n"
    for bc in bcs:
        aggs = bc.get("aggregates", []) or []
        cmds = sum(len(a.get("commands", []) or []) for a in aggs)
        evts = sum(len(a.get("events", []) or []) for a in aggs)
        rms = len(bc.get("readmodels", []) or [])
        pols = len(bc.get("policies", []) or [])
        uis = len(bc.get("uis", []) or [])
        prd += f"| {bc.get('name', 'Unknown')} | {len(aggs)} | {cmds} | {evts} | {rms} | {pols} | {uis} |\n"

    prd += f"""

## Project Structure & Reference Files

**IMPORTANT**: This PRD is the entry point. When implementing, you MUST read and follow the detailed specifications in the files listed below.

### Core Documentation Files
- **`PRD.md`** (this file): Overall architecture, principles, and guidelines
- **`CLAUDE.md`**: Project context and BC overview for AI assistants
- **`README.md`**: Project overview and BC descriptions

### Bounded Context Specifications
Each BC has a detailed specification file in the `specs/` directory:
"""
    
    for bc in bcs:
        bc_name = bc.get("name", "Unknown")
        bc_name_slug = bc_name.lower().replace(" ", "_")
        prd += f"- **`specs/{bc_name_slug}_spec.md`**: Complete specification for {bc_name} BC\n"
    
    prd += f"""
### AI Assistant Configuration Files

"""
    if config.ai_assistant.value == "cursor":
        prd += f"""**Using Cursor IDE**:
- **`.cursorrules`** (mention: `@.cursorrules`): Global DDD principles and coding standards (read this first)
- **`.cursor/rules/{config.framework.value}.mdc`** (mention: `@{config.framework.value}`): {config.framework.value} ({config.language.value}) tech stack specific implementation guidelines
"""
    else:  # claude
        prd += f"""**Using Claude Code**:
- **`.claude/skills/`**: Common implementation skills (DDD, Event Storming, Tech Stack)
  - `ddd-principles.md` - DDD patterns (always reference)
  - `eventstorming-implementation.md` - Sticker-to-code mapping (Command, Event, Aggregate, ReadModel, Policy, UI)
  - `gwt-test-generation.md` - GWT (Given/When/Then) test patterns
  - `{config.framework.value}.md` - {config.framework.value} implementation guidelines
"""
        if config.include_frontend and config.frontend_framework:
            prd += f"  - `{config.frontend_framework.value}.md` - Frontend framework technical implementation patterns\n"
            prd += f"- **`Frontend-PRD.md`**: Frontend architecture, strategy, and UI overview (read together with this PRD)\n"
        prd += f"- **`.claude/agents/`**: BC-specific agent configurations\n"
        for bc in bcs:
            bc_name = bc.get("name", "Unknown")
            bc_name_slug = bc_name.lower().replace(" ", "_")
            prd += f"  - **`.claude/agents/{bc_name_slug}_agent.md`**: Agent configuration for {bc_name} BC\n"
    
    prd += f"""
### Implementation Workflow

**When starting implementation for a specific BC:**

1. **Read this PRD** (`PRD.md`) to understand overall architecture and principles
2. **Read the BC specification** (`specs/{{bc_name}}_spec.md`) for detailed requirements
3. **Read the AI assistant guide**:
   - For Cursor: `.cursorrules` (global) + `.cursor/rules/{{bc_name}}.mdc` (BC-specific)
   - For Claude: `.claude/agents/{{bc_name}}_agent.md`
4. **Follow the implementation guidelines** in the AI assistant guide
5. **Refer to other BC specs** when implementing cross-BC policies or event contracts

**Key Principle**: Always check the BC specification file (`specs/{{bc_name}}_spec.md`) for:
- Complete aggregate definitions with all properties
- Command and Event schemas
- ReadModel structures
- Policy trigger/invoke relationships
- GWT test case scenarios

## Architecture Principles

### Domain-Driven Design (DDD)
- **Bounded Contexts**: Each BC represents a distinct domain boundary with its own models and language
- **Aggregates**: Enforce business invariants and maintain transactional consistency
- **Commands**: Represent user/system intentions to change state (imperative: CreateOrder, CancelOrder)
- **Events**: Represent immutable facts that happened (past tense: OrderCreated, PaymentProcessed)
- **Policies**: Enable cross-BC communication through event-driven patterns

### Event-Driven Architecture
- **Asynchronous Communication**: BCs communicate via events through {config.messaging.value}
- **Loose Coupling**: BCs are independent and communicate only through well-defined event contracts
- **Event Sourcing Ready**: Events represent the source of truth for state changes
- **CQRS Pattern**: Separate read models (ReadModels) from write models (Aggregates)

### Service Independence & Dependencies
- **Independent Deployment**: Each BC can be deployed independently without affecting others
- **Event-Based Dependencies**: Dependencies are only through event contracts, not direct service calls
- **Backward Compatibility**: Event schema changes must maintain backward compatibility (use versioning)
- **No Direct Service Calls**: BCs must NOT call other BCs' APIs directly - use events only
- **Dependency Direction**: 
  - Event Publisher BC: Independent (no dependency on consumers)
  - Event Consumer BC (Policy): Depends on event contract, not publisher service
  - Consumer can be deployed/updated independently as long as event contract is maintained

### Development Guidelines

#### 1. Command Implementation

**Command Handler:**
- **Naming**: Use imperative verbs (CreateOrder, CancelOrder, ProcessPayment)
- **Validation**: Validate all invariants before executing commands
- **Input Schema**: Use the provided `inputSchema` to define command DTOs
- **Actor Authorization**: Check actor permissions before command execution
- **Execution**: Execute through aggregate root
- **Event Emission**: Emit events after successful command execution
- **Idempotency**: Consider idempotency for commands that may be retried

**REST API Endpoints:**
- **HTTP Method**: POST (all commands change state)
- **Endpoint Pattern**: `POST /api/{{bc_name}}/{{command-name}}`
- **Request Mapping**: Map request body to command DTO using `inputSchema`
- **Response Codes**: 
  - `201 Created` for Create commands
  - `200 OK` for Update/Process commands
  - `204 No Content` for Delete commands
  - `400 Bad Request` for validation errors
  - `403 Forbidden` for authorization failures
- **Response Body**: Include command result or emitted event information

#### 2. Event Implementation

**Event Class:**
- **Naming**: Use past tense (OrderCreated, PaymentProcessed, UserRegistered)
- **Schema**: Use the provided `schema` to define event classes
- **Properties**: Map all properties from spec to event fields
- **Immutability**: Events are immutable once emitted
- **Versioning**: Use semantic versioning for event schema evolution
- **Metadata**: Include eventId, timestamp, version, etc.

**Event Publishing:**
- **Publisher**: Use event publisher service in `infrastructure/messaging/`
- **Platform**: Publish to {config.messaging.value} after successful command execution
- **Async**: Publish asynchronously to avoid blocking command execution
- **Versioning**: Include event version in message headers/topic
  - **Schema Version**: Use semantic versioning (e.g., v1.0.0, v1.1.0 for backward-compatible changes)
  - **Breaking Changes**: Create new version (v2.0.0) and maintain old version for backward compatibility
- **Error Handling**: Handle publishing failures (retry, dead-letter queue)
- **Independence**: Publisher BC has NO dependency on consumer BCs - publish and forget

**Event Consumption (Policies):**
- **Listener**: Implement event listeners for Policies
- **Subscription**: Subscribe to events via {config.messaging.value} consumer
- **Cross-BC**: Handle events from other BCs (deserialize using other BC event schemas)
  - **Reference Other BC Specs**: Check `specs/{{other_bc_name}}_spec.md` for event schemas
  - **Schema Contract**: Use exact event schema from publisher BC spec
  - **Version Handling**: Support multiple event versions if needed (backward compatibility)
- **Idempotency**: Implement idempotency checks for duplicate events
  - **Event ID**: Use eventId to detect duplicates
  - **Idempotency Key**: Store processed event IDs to prevent reprocessing
- **Independence**: Consumer BC depends on event contract, NOT on publisher BC service
  - Consumer can be deployed/updated independently
  - Consumer can be temporarily down without affecting publisher

#### 3. Aggregate Implementation
- **Root Entity**: Use the `rootEntity` as the aggregate root class
- **Invariants**: Enforce all listed invariants in aggregate methods
- **Properties**: Map all properties with correct types (use `isKey` for primary keys, `isForeignKey` for references)
   - **Reference BC Spec**: Check `specs/{{bc_name}}_spec.md` for complete property definitions
- **Enumerations**: Use provided enumerations for state management
- **Value Objects**: Implement value objects for complex domain concepts
- **Persistence**: Persist aggregates using {config.database.value} through repository pattern
   - **Database Schema**: Create tables/collections based on aggregate properties in spec
   - **Reference Database Rules**: Check `@{config.framework.value}` rule for database-specific guidelines
- **Transactions**: Keep database transactions within aggregate boundaries only

#### 4. ReadModel Implementation

**ReadModel Projection:**
- **CQRS Pattern**: ReadModels are updated via event projections
- **Projection Handler**: Implement event projection handlers in `domain/readmodels/`
- **Actor Support**: Filter/authorize based on `actor` field
- **Denormalization**: Denormalize data for query performance
- **Eventual Consistency**: Accept eventual consistency (ReadModels may be slightly stale)

**Query API Endpoints:**
- **HTTP Method**: GET (queries don't change state)
- **Endpoint Patterns**:
  - Single result: `GET /api/{{bc_name}}/{{readmodel-name}}/{{id}}`
  - List: `GET /api/{{bc_name}}/{{readmodel-name}}?filter=value&page=1&size=10`
  - Collection: `GET /api/{{bc_name}}/{{readmodel-name}}`
- **Return Types** (based on `isMultipleResult`):
  - `list`: Return ordered arrays (e.g., `List<OrderSummary>`)
  - `collection`: Return unordered collections (e.g., `Set<Product>`)
  - `single result`: Return single objects (e.g., `OrderDetail`)
- **Features**: Support filtering, pagination, and sorting for list/collection types
- **Authorization**: Apply actor-based filtering
- **Response**: `200 OK` with data or `404 Not Found`

#### 5. Policy Implementation

**Event Listener:**
- **Subscription**: Subscribe to trigger events via {config.messaging.value} consumer
- **Cross-BC Events**: Handle events from other BCs (deserialize using other BC event schemas)
  - **Reference Publisher BC Spec**: Check `specs/{{publisher_bc_name}}_spec.md` for event schema
  - **Schema Contract**: Use exact event schema from publisher BC spec
  - **Version Support**: Support multiple event versions for backward compatibility
- **Idempotency**: Implement idempotency checks to handle duplicate events
  - **Event ID Tracking**: Store processed event IDs to prevent reprocessing
  - **Idempotency Key**: Use eventId + consumerId as idempotency key

**Command Invocation:**
- **Async Invocation**: Invoke target commands asynchronously via {config.messaging.value}
- **Cross-BC Commands**: Handle command invocation in different BCs
  - **Reference Target BC Spec**: Check `specs/{{target_bc_name}}_spec.md` for command schema
  - **Command Contract**: Use exact command inputSchema from target BC spec
- **Data Mapping**: Map event data to command input using event/command schemas
  - **Schema Mapping**: Map event properties to command inputSchema properties
  - **Validation**: Validate mapped command input before invocation
- **Retry Logic**: Implement retry logic for failed invocations
  - **Exponential Backoff**: Use exponential backoff for retries
  - **Max Retries**: Set maximum retry attempts (e.g., 3-5 times)
- **Dead-Letter Queue**: Use dead-letter queues for permanently failed invocations
  - **DLQ Monitoring**: Monitor DLQ for failed invocations
  - **Manual Recovery**: Provide mechanism to reprocess DLQ messages

**Service Dependencies:**
- **No Direct Dependencies**: Policy BC does NOT depend on target BC service
- **Event Contract Dependency**: Only depends on event contract (schema), not service implementation
- **Independent Deployment**: Policy BC can be deployed/updated independently
- **Target BC Availability**: Policy can handle target BC being temporarily unavailable
  - Events are queued in messaging platform
  - Policy retries when target BC becomes available

**Error Handling:**
- **Duplicate Events**: Handle duplicate events with idempotency checks
- **Deserialization**: Handle event deserialization failures gracefully
  - **Schema Mismatch**: Log and send to DLQ if event schema doesn't match
  - **Version Mismatch**: Support multiple event versions or reject unsupported versions
- **Invocation Failures**: Handle command invocation failures with retry logic
  - **Transient Failures**: Retry transient failures (network, timeout)
  - **Permanent Failures**: Send to DLQ for permanent failures (validation errors, etc.)
- **Logging**: Log all policy executions for debugging
  - **Event Received**: Log when event is received
  - **Command Invoked**: Log when command is invoked
  - **Failures**: Log all failures with context

#### 6. UI Wireframe Implementation

**UI Components (from BC Spec):**
- **Reference BC Spec**: Check `specs/{{bc_name}}_spec.md` for UI wireframes section
- **Wireframe Templates**: Use the `template` field (HTML wireframes) from spec
- **Attached Commands**: UI wireframes attached to Commands → Create form components
- **Attached ReadModels**: UI wireframes attached to ReadModels → Create display/list components
- **Frontend PRD**: Check `Frontend-PRD.md` for UI wireframe implementation guidelines
- **API Integration**: Connect UI to backend APIs (Command POST, ReadModel GET)
- **State Management**: Use framework-specific state management (Pinia, Redux, etc.)
- **Reference Frontend Rules**: Use `@{config.frontend_framework.value if config.frontend_framework else "N/A"}` for frontend patterns

**Service Pages:**
- **Command Pages**: Create pages for each Command (form submission)
- **ReadModel Pages**: Create pages for each ReadModel (query results display)
- **Navigation**: Implement routing based on UI wireframes in spec
- **Invocation Failures**: Handle command invocation failures with retry logic
- **Logging**: Log all policy executions for debugging

#### 6. Testing
- **GWT Test Cases**: Implement Given/When/Then tests based on provided scenarios
- **Test Scenarios**: Use `testCases` field values for test data
- **Integration Tests**: Test cross-BC communication via events
- **Unit Tests**: Test aggregate invariants and command validation

### BC-Specific Implementation Notes

"""
    for bc in bcs:
        bc_name = bc.get("name", "Unknown")
        bc_desc = bc.get("description", "No description")
        aggs = bc.get("aggregates", []) or []
        agg_names = [a.get("name", "") for a in aggs if a.get("name")]
        rms = bc.get("readmodels", []) or []
        rm_names = [rm.get("name", "") for rm in rms if rm.get("name")]
        pols = bc.get("policies", []) or []
        
        prd += f"#### {bc_name}\n"
        prd += f"- **Description**: {bc_desc}\n"
        if agg_names:
            prd += f"- **Aggregates**: {', '.join(agg_names)}\n"
        if rm_names:
            prd += f"- **ReadModels**: {', '.join(rm_names)}\n"
        if pols:
            pol_names = [p.get("name", "") for p in pols if p.get("name")]
            if pol_names:
                prd += f"- **Policies**: {', '.join(pol_names)}\n"
        prd += f"- **Spec File**: `specs/{bc_name.lower().replace(' ', '_')}_spec.md`\n"
        prd += "\n"

    prd += f"""
## Implementation Checklist

### For Each Bounded Context:

#### 1. Read BC Spec First (MANDATORY)
- [ ] **Read BC Spec** (`specs/{{bc_name}}_spec.md`) FIRST - Contains ALL implementation details
- [ ] **List ALL Aggregates** - Count and verify all aggregates from spec
- [ ] **List ALL Commands** - Count and verify all commands from spec (every command MUST have an API endpoint)
- [ ] **List ALL Events** - Count and verify all events from spec (every command MUST emit events)
- [ ] **List ALL ReadModels** - Count and verify all ReadModels from spec (every ReadModel MUST have a query API)
- [ ] **List ALL Policies** - Count and verify all policies from spec
- [ ] **List ALL UI Wireframes** - Count and verify all UI wireframes from spec

#### 2. Database Setup (MANDATORY)
- [ ] **Set up database connection** - Configure {config.database.value} connection in application config
- [ ] **Create database schema** - Create tables/collections for ALL aggregates (from spec properties)
- [ ] **Create indexes** - Index foreign keys and frequently queried columns
- [ ] **Test database connection** - Verify connection works before proceeding

#### 3. Implement ALL Aggregates (100% Coverage Required)
For EACH Aggregate in BC spec:
- [ ] **Create aggregate root entity** - With ALL properties from spec (including isKey, isForeignKey)
- [ ] **Implement invariants** - ALL invariants from spec MUST be enforced
- [ ] **Implement enumerations** - ALL enumerations from spec
- [ ] **Implement value objects** - ALL value objects from spec
- [ ] **Create repository** - Repository for aggregate persistence

#### 4. Implement ALL Commands (100% Coverage Required)
For EACH Command in BC spec:
- [ ] **Create command DTO** - Using inputSchema from spec
- [ ] **Create command handler** - Handler with validation
- [ ] **Validate all inputs** - Use inputSchema and properties from spec
- [ ] **Check actor authorization** - Verify actor permissions
- [ ] **Execute through aggregate** - Execute command via aggregate root
- [ ] **Emit events** - Emit ALL events after successful execution
- [ ] **Create REST API endpoint** - `POST /api/{{bc_name}}/{{command-name}}` (MANDATORY)
- [ ] **Return proper response codes** - 201 for Create, 200 for Update, 400 for validation errors, 403 for authorization failures
- [ ] **Handle errors** - Proper error handling and messages

**CRITICAL**: If a Command exists in BC spec, it MUST have:
1. A command handler
2. A REST API endpoint (POST)
3. Event emission after execution
4. Input validation
5. Actor authorization

#### 5. Implement ALL Events (100% Coverage Required)
For EACH Event in BC spec:
- [ ] **Create event class** - With ALL properties from spec
- [ ] **Include event schema** - Use schema from spec
- [ ] **Include version** - Use version from spec
- [ ] **Include metadata** - eventId, timestamp, version
- [ ] **Set up event publishing** - Publish to {config.messaging.value} after command execution
- [ ] **Handle publishing errors** - Retry logic, dead-letter queue

**CRITICAL**: Every Command MUST emit at least one Event. Verify all events are published.

#### 6. Implement ALL ReadModels (100% Coverage Required)
For EACH ReadModel in BC spec:
- [ ] **Create ReadModel class** - With ALL properties from spec
- [ ] **Create projection handler** - Update ReadModel from events
- [ ] **Create query API endpoint** - `GET /api/{{bc_name}}/{{readmodel-name}}` (MANDATORY)
- [ ] **Support pagination** - If isMultipleResult is 'list', support pagination
- [ ] **Support filtering** - Support actor filtering if actor is specified
- [ ] **Return proper format** - Single result, list, or collection based on isMultipleResult

**CRITICAL**: If a ReadModel exists in BC spec, it MUST have:
1. A ReadModel class with all properties
2. A query API endpoint (GET)
3. Event projection handler
4. Proper response format (single/list/collection)

#### 7. Implement ALL Policies (100% Coverage Required)
For EACH Policy in BC spec:
- [ ] **Create event listener** - Subscribe to trigger events from {config.messaging.value}
- [ ] **Handle cross-BC events** - Deserialize events from other BCs
- [ ] **Implement idempotency** - Handle duplicate events
- [ ] **Invoke target commands** - Invoke commands asynchronously via {config.messaging.value}
- [ ] **Handle errors** - Retry logic, dead-letter queue

#### 8. Messaging Setup (MANDATORY)
- [ ] **Configure {config.messaging.value} connection** - Set up connection to messaging platform
- [ ] **Set up event publishers** - Publisher service for all events
- [ ] **Set up event consumers** - Consumer service for policies
- [ ] **Test messaging connection** - Verify events can be published and consumed
- [ ] **Set up dead-letter queues** - For failed event processing

#### 9. Frontend Integration (If frontend included)
- [ ] **Implement UI wireframes** - All wireframes from spec as frontend components/pages
- [ ] **Create service pages** - Pages for Commands (forms) and ReadModels (displays)
- [ ] **Connect UI to APIs** - All UI buttons/forms MUST call backend APIs

#### 10. Testing (MANDATORY)
- [ ] **Implement GWT test cases** - All test scenarios from spec
- [ ] **Test all commands** - Verify all commands work correctly
- [ ] **Test all ReadModels** - Verify all ReadModels return correct data
- [ ] **Test event publishing** - Verify all events are published
- [ ] **Test event consumption** - Verify policies consume events correctly
- [ ] **Test API endpoints** - Verify all REST endpoints work

### Cross-BC Integration:
- [ ] **Verify event contracts** match between BCs (check publisher BC spec for event schema, consumer BC spec for expected schema)
- [ ] **Set up event subscriptions** for Policies (subscribe to trigger events from other BCs)
- [ ] **Implement idempotency** for event consumption (prevent duplicate processing)
- [ ] **Set up dead-letter queues** for failed event processing
- [ ] **Test end-to-end workflows** across BCs (verify event flow from publisher to consumer)
- [ ] **Monitor event flow** and error handling (track event publishing, consumption, failures)
- [ ] **Verify service independence** (each BC can be deployed independently)
- [ ] **Document event contracts** (which BC publishes which events, which BC consumes which events)

## Notes
- This PRD was generated from the Event Storming model stored in Neo4j.
- **Always refer to individual BC spec files** (`specs/{{bc_name}}_spec.md`) FIRST for detailed implementation requirements:
  - ✅ Aggregates, Commands, Events, ReadModels, Policies
  - ✅ **UI Wireframes with templates** (HTML wireframes)
  - ✅ **Database schema requirements** (properties, foreign keys)
  - ✅ GWT test cases
- **Reference Cursor Rules** using @mention:
  - `@.cursorrules`, `@ddd-principles`, `@eventstorming-implementation`, `@gwt-test-generation`
  - `@{config.framework.value}` (tech stack), `@{config.frontend_framework.value if config.frontend_framework else "N/A"}` (frontend, if included)
- **Check Frontend PRD** (`Frontend-PRD.md`) if implementing UI components
- Follow the technology stack choices consistently across all BCs.
- Maintain BC boundaries strictly - no direct database access between BCs.

## File Reference Quick Guide

**When implementing code (e.g., "진행해"), use this file reference in order:**

1. **Architecture & Principles**: `PRD.md` (this file) - High-level overview
2. **BC Details** (MUST READ FIRST): `specs/{{bc_name}}_spec.md` - Contains:
   - ✅ All aggregates with properties, invariants, enumerations
   - ✅ All commands with input schemas → **Implement as REST API endpoints**
   - ✅ All events with schemas → **Implement as message publishing**
   - ✅ All ReadModels with properties → **Implement as query API endpoints**
   - ✅ All Policies with trigger/invoke → **Implement as event listeners**
   - ✅ **All UI Wireframes with templates** → **Implement as frontend components/pages**
   - ✅ All GWT test cases → **Implement as test code**
   - ✅ **Database schema requirements** (properties, foreign keys)
3. **Cursor Rules** (use @mention):
   - `@.cursorrules` - Global DDD principles
   - `@ddd-principles` - DDD patterns
   - `@eventstorming-implementation` - Sticker-to-code mapping
   - `@gwt-test-generation` - GWT test patterns
   - `@{config.framework.value}` - Tech stack guidelines (e.g., `@spring-boot`)
   - `@{config.frontend_framework.value if config.frontend_framework else "N/A"}` - Frontend guidelines (if frontend included)
4. **Frontend PRD** (if frontend included): `Frontend-PRD.md` - UI wireframes, API integration
5. **Project Context**: `CLAUDE.md` - Overview for AI assistants

**Remember**: 
- The spec files (`specs/{{bc_name}}_spec.md`) contain the complete, detailed requirements including UI wireframes, database schemas, and API contracts.
- This PRD provides the high-level architecture and principles.
- **Always read the BC spec file FIRST before implementing any code.**
"""
    return prd


def generate_bc_spec(bc: dict, config: TechStackConfig) -> str:
    name = bc.get("name", "Unknown")
    spec = f"""# {name} Bounded Context Specification

> **Note**: This is a detailed specification for the {name} Bounded Context.  
> For overall architecture and principles, refer to **`PRD.md`** (main PRD document).  
> For implementation guidance, refer to the AI assistant configuration files (use @mention in Cursor):
> - Cursor: `@.cursorrules` + `@{{framework}}` (e.g., `@spring-boot`) + `@ddd-principles`, `@eventstorming-implementation`, `@gwt-test-generation`
> - Claude: `.claude/agents/{{bc_name}}_agent.md`

## Overview
- **BC ID**: {bc.get("id", "")}
- **Description**: {bc.get("description", "No description")}
- **Main PRD**: See `PRD.md` for architecture principles and guidelines

## Aggregates
"""
    for agg in bc.get("aggregates", []) or []:
        spec += f"\n### {agg.get('name', 'Unknown')}\n"
        if agg.get("rootEntity"):
            spec += f"- Root Entity: `{agg['rootEntity']}`\n"
        
        # Aggregate Invariants
        if agg.get("invariants"):
            invariants = agg["invariants"]
            if isinstance(invariants, list) and len(invariants) > 0:
                spec += "- Invariants:\n"
                for inv in invariants:
                    spec += f"  - {inv}\n"
        
        # Aggregate Enumerations
        if agg.get("enumerations"):
            enums = agg["enumerations"]
            if isinstance(enums, list) and len(enums) > 0:
                spec += "- Enumerations:\n"
                for enum in enums:
                    if isinstance(enum, dict):
                        enum_name = enum.get("name", "Unknown")
                        enum_values = enum.get("values", [])
                        spec += f"  - `{enum_name}`: {', '.join(enum_values) if enum_values else 'N/A'}\n"
        
        # Aggregate Value Objects
        if agg.get("valueObjects"):
            vos = agg["valueObjects"]
            if isinstance(vos, list) and len(vos) > 0:
                spec += "- Value Objects:\n"
                for vo in vos:
                    if isinstance(vo, dict):
                        vo_name = vo.get("name", "Unknown")
                        spec += f"  - `{vo_name}`\n"
        
        # Aggregate Properties
        if agg.get("properties"):
            spec += "- Properties:\n"
            for prop in agg["properties"]:
                if prop.get("id"):
                    prop_type = prop.get("type", "String")
                    is_key = " (Key)" if prop.get("isKey") else ""
                    is_fk = f" (FK -> {prop.get('fkTargetHint', '')})" if prop.get("isForeignKey") else ""
                    spec += f"  - `{prop.get('name', '')}`: {prop_type}{is_key}{is_fk}\n"
                    if prop.get("description"):
                        spec += f"    - {prop.get('description')}\n"
        
        # Commands with Properties
        if agg.get("commands"):
            spec += "- Commands:\n"
            for cmd in agg["commands"]:
                if cmd.get("id"):
                    cmd_name = cmd.get("name", "")
                    cmd_actor = cmd.get("actor", "")
                    cmd_category = cmd.get("category", "")
                    cmd_desc = cmd.get("description", "")
                    spec += f"  - `{cmd_name}`"
                    if cmd_actor:
                        spec += f" (actor: {cmd_actor})"
                    if cmd_category:
                        spec += f" [category: {cmd_category}]"
                    spec += "\n"
                    if cmd_desc:
                        spec += f"    - Description: {cmd_desc}\n"
                    if cmd.get("inputSchema"):
                        spec += f"    - Input Schema: {cmd['inputSchema']}\n"
                    if cmd.get("properties"):
                        spec += "    - Properties:\n"
                        for prop in cmd["properties"]:
                            if prop.get("id"):
                                prop_type = prop.get("type", "String")
                                is_required = " (required)" if prop.get("isRequired") else ""
                                spec += f"      - `{prop.get('name', '')}`: {prop_type}{is_required}\n"
        
        # Events with Properties
        if agg.get("events"):
            spec += "- Events:\n"
            for evt in agg["events"]:
                if evt.get("id"):
                    evt_name = evt.get("name", "")
                    evt_version = evt.get("version", "1")
                    evt_desc = evt.get("description", "")
                    spec += f"  - `{evt_name}` (v{evt_version})\n"
                    if evt_desc:
                        spec += f"    - Description: {evt_desc}\n"
                    if evt.get("schema"):
                        spec += f"    - Schema: {evt['schema']}\n"
                    if evt.get("properties"):
                        spec += "    - Properties:\n"
                        for prop in evt["properties"]:
                            if prop.get("id"):
                                prop_type = prop.get("type", "String")
                                spec += f"      - `{prop.get('name', '')}`: {prop_type}\n"

    # ReadModels
    if bc.get("readmodels"):
        spec += "\n## ReadModels\n"
        for rm in bc["readmodels"]:
            if rm.get("id"):
                spec += f"\n### {rm.get('name', 'Unknown')}\n"
                if rm.get("description"):
                    spec += f"- Description: {rm.get('description')}\n"
                if rm.get("provisioningType"):
                    spec += f"- Provisioning Type: {rm.get('provisioningType')}\n"
                if rm.get("actor"):
                    spec += f"- Actor: {rm.get('actor')}\n"
                if rm.get("isMultipleResult"):
                    spec += f"- Result Type: {rm.get('isMultipleResult')}\n"
                if rm.get("properties"):
                    spec += "- Properties:\n"
                    for prop in rm["properties"]:
                        if prop.get("id"):
                            prop_type = prop.get("type", "String")
                            spec += f"  - `{prop.get('name', '')}`: {prop_type}\n"

    # Policies
    if bc.get("policies"):
        spec += "\n## Policies\n"
        for pol in bc["policies"]:
            if pol.get("id"):
                spec += f"- `{pol.get('name','')}`\n"
                if pol.get("description"):
                    spec += f"  - Description: {pol.get('description')}\n"
                trigger_evt_name = pol.get('triggerEventName', 'N/A')
                trigger_evt_bc = pol.get('triggerEventBCName', '')
                if trigger_evt_bc and trigger_evt_bc != bc.get('name', ''):
                    spec += f"  - Triggers: `{trigger_evt_name}` (from BC: {trigger_evt_bc})\n"
                else:
                    spec += f"  - Triggers: `{trigger_evt_name}`\n"
                invoke_cmd_name = pol.get('invokeCommandName', 'N/A')
                invoke_cmd_bc = pol.get('invokeCommandBCName', '')
                if invoke_cmd_bc and invoke_cmd_bc != bc.get('name', ''):
                    spec += f"  - Invokes: `{invoke_cmd_name}` (in BC: {invoke_cmd_bc})\n"
                else:
                    spec += f"  - Invokes: `{invoke_cmd_name}`\n"

    # UI Wireframes
    if bc.get("uis"):
        spec += "\n## UI Wireframes\n"
        for ui in bc["uis"]:
            if ui.get("id"):
                spec += f"- `{ui.get('name', 'Unknown')}`\n"
                if ui.get("description"):
                    spec += f"  - Description: {ui.get('description')}\n"
                if ui.get("attachedToType") and ui.get("attachedToName"):
                    spec += f"  - Attached to: {ui.get('attachedToType')} `{ui.get('attachedToName')}`\n"
                if ui.get("template"):
                    template = ui.get("template", "").strip()
                    if template:
                        spec += f"  - Wireframe Template:\n"
                        spec += f"    ```html\n"
                        # Template을 들여쓰기하여 표시 (각 줄 앞에 4칸 공백 추가)
                        for line in template.split('\n'):
                            spec += f"    {line}\n"
                        spec += f"    ```\n"

    # GWT Test Cases
    if bc.get("gwts"):
        spec += "\n## GWT Test Cases\n"
        for gwt in bc["gwts"]:
            if gwt.get("id"):
                parent_type = gwt.get("parentType", "Unknown")
                spec += f"\n### GWT for {parent_type} `{gwt.get('parentId', '')}`\n"
                if gwt.get("givenRef"):
                    given = gwt["givenRef"]
                    if isinstance(given, dict):
                        spec += f"- **Given**: {given.get('name', 'N/A')}\n"
                        if given.get("description"):
                            spec += f"  - {given.get('description')}\n"
                if gwt.get("whenRef"):
                    when = gwt["whenRef"]
                    if isinstance(when, dict):
                        spec += f"- **When**: {when.get('name', 'N/A')}\n"
                        if when.get("description"):
                            spec += f"  - {when.get('description')}\n"
                if gwt.get("thenRef"):
                    then = gwt["thenRef"]
                    if isinstance(then, dict):
                        spec += f"- **Then**: {then.get('name', 'N/A')}\n"
                        if then.get("description"):
                            spec += f"  - {then.get('description')}\n"
                if gwt.get("testCases"):
                    test_cases = gwt["testCases"]
                    if isinstance(test_cases, list) and len(test_cases) > 0:
                        spec += f"\n#### Test Scenarios ({len(test_cases)} cases)\n"
                        for idx, tc in enumerate(test_cases, 1):
                            if isinstance(tc, dict):
                                spec += f"\n**Scenario {idx}**: {tc.get('scenarioDescription', 'N/A')}\n"
                                if tc.get("givenFieldValues"):
                                    spec += "- Given values:\n"
                                    for k, v in tc.get("givenFieldValues", {}).items():
                                        spec += f"  - `{k}`: {v}\n"
                                if tc.get("whenFieldValues"):
                                    spec += "- When values:\n"
                                    for k, v in tc.get("whenFieldValues", {}).items():
                                        spec += f"  - `{k}`: {v}\n"
                                if tc.get("thenFieldValues"):
                                    spec += "- Then values:\n"
                                    for k, v in tc.get("thenFieldValues", {}).items():
                                        spec += f"  - `{k}`: {v}\n"

    spec += "\n## Implementation Notes\n"
    spec += f"- Framework: `{config.framework.value}`\n- Messaging: `{config.messaging.value}`\n"
    spec += f"\n## Related Files\n"
    spec += f"- **Main PRD**: `PRD.md` - Overall architecture, principles, and development guidelines\n"
    bc_name_slug = name.lower().replace(" ", "_")
    if config.ai_assistant.value == "cursor":
        spec += f"\n### Cursor Rules (Implementation Guidelines)\n"
        spec += f"- **Global Rules**: `.cursorrules` - General DDD principles and coding standards\n"
        spec += f"- **DDD Principles**: `.cursor/rules/ddd-principles.mdc` - DDD patterns (always applied)\n"
        spec += f"- **Event Storming Implementation**: `.cursor/rules/eventstorming-implementation.mdc` - Sticker-to-code mapping (Command, Event, Aggregate, ReadModel, Policy, UI)\n"
        spec += f"- **GWT Test Generation**: `.cursor/rules/gwt-test-generation.mdc` - GWT (Given/When/Then) test patterns\n"
        spec += f"- **Tech Stack Rules**: `.cursor/rules/{config.framework.value}.mdc` - {config.framework.value} implementation guidelines\n"
        if config.include_frontend and config.frontend_framework:
            spec += f"- **Frontend Rules**: `.cursor/rules/{config.frontend_framework.value}.mdc` - Frontend framework implementation guidelines\n"
    else:
        spec += f"\n### Claude Skills (Implementation Guidelines)\n"
        spec += f"- **DDD Principles**: `.claude/skills/ddd-principles.md` - DDD patterns (always reference)\n"
        spec += f"- **Event Storming Implementation**: `.claude/skills/eventstorming-implementation.md` - Sticker-to-code mapping (Command, Event, Aggregate, ReadModel, Policy, UI)\n"
        spec += f"- **GWT Test Generation**: `.claude/skills/gwt-test-generation.md` - GWT (Given/When/Then) test patterns\n"
        spec += f"- **Tech Stack Skills**: `.claude/skills/{config.framework.value}.md` - {config.framework.value} implementation guidelines\n"
        if config.include_frontend and config.frontend_framework:
            spec += f"- **Frontend Skills**: `.claude/skills/{config.frontend_framework.value}.md` - Frontend framework implementation guidelines\n"
        spec += f"- **BC Agent**: `.claude/agents/{bc_name_slug}_agent.md` - BC-specific agent configuration\n"
    spec += f"- **Project Context**: `CLAUDE.md` - Project overview for AI assistants\n"
    return spec


def generate_claude_md(bcs: list[dict], config: TechStackConfig) -> str:
    return f"""# CLAUDE.md - AI Assistant Context

> **Note**: This file provides project context for AI assistants.  
> For detailed architecture and implementation guidelines, refer to **`PRD.md`** (main PRD document).  
> For BC-specific details, refer to `specs/{{bc_name}}_spec.md` files.

## Project
- Name: {config.project_name}
- Deployment: {config.deployment.value}
- Stack: {config.language.value} / {config.framework.value}
- Messaging: {config.messaging.value}
- Database: {config.database.value}

## Bounded Contexts
{chr(10).join([f"- {bc.get('name','Unknown')} ({bc.get('id','')})" for bc in bcs])}

## Reference Files
- **Main PRD**: `PRD.md` - Complete architecture, principles, and implementation guidelines
- **BC Specs**: `specs/{{bc_name}}_spec.md` - Detailed specifications for each BC
- **AI Assistant Guides**: 
  - Cursor: `.cursorrules` (global) + `.cursor/rules/{{framework}}.mdc` (tech stack)
  - Claude: 
    - `.claude/skills/` - Common implementation skills (DDD, Event Storming, Tech Stack)
      - `ddd-principles.md` - DDD patterns (always reference)
      - `eventstorming-implementation.md` - Sticker-to-code mapping
      - `gwt-test-generation.md` - GWT test patterns
      - `{{framework}}.md` - Tech stack specific guidelines
    - `.claude/agents/{{bc_name}}_agent.md` - BC-specific agent configuration
"""


def generate_cursor_rules(config: TechStackConfig) -> str:
    # Get database-specific guidelines
    db_guidelines = _get_database_specific_guidelines(config.database.value)
    
    return f"""# Cursor Rules for {config.project_name}

> **Global Rules**: These apply to the entire project. For BC-specific implementation guides, see `.cursor/rules/{{bc_name}}.mdc` files.
> Use mention feature (`@.cursorrules`) to reference these global standards.

## Domain-Driven Design (DDD) Principles

### Naming Conventions
- **Commands**: Use imperative verbs (CreateOrder, CancelOrder, ProcessPayment)
- **Events**: Use past tense (OrderCreated, PaymentProcessed, UserRegistered)
- **Aggregates**: Use domain nouns (Order, Payment, User)
- **ReadModels**: Use query intent (OrderList, OrderDetail, UserProfile)

### Bounded Context Boundaries
- **Strict Isolation**: Never directly access another BC's database or internal APIs
- **Event Communication**: All cross-BC communication must go through {config.messaging.value} events
- **Independent Deployment**: Each BC should be independently deployable
- **Own Data Model**: Each BC has its own database schema

### Aggregate Rules
- **Transaction Boundary**: Keep transactions within a single aggregate
- **Invariant Enforcement**: Always enforce all business invariants
- **Root Entity**: Access entities only through the aggregate root
- **Consistency**: Maintain consistency within aggregate boundaries only

### Command-Event Pattern
- **Command Validation**: Validate all inputs before execution
- **Event Emission**: Emit events after successful command execution
- **Idempotency**: Consider idempotency for retryable commands
- **Actor Authorization**: Check actor permissions for all commands

### CQRS Pattern
- **Read-Write Separation**: Separate read models from write models
- **Event Projections**: Update ReadModels via event projections
- **Eventual Consistency**: Accept eventual consistency for read models
- **Query Optimization**: Denormalize data for query performance

## Technology Stack Standards

### Language: {config.language.value}
- Follow {config.language.value} best practices and conventions
- Use appropriate type system features
- Maintain code readability and maintainability

### Framework: {config.framework.value}
- Follow {config.framework.value} patterns and conventions
- Use framework-provided features for dependency injection, validation, etc.
- Maintain consistency with framework idioms

### Messaging: {config.messaging.value}
- Use {config.messaging.value} for all event publishing and consumption
- Implement proper error handling and retry logic
- Use dead-letter queues for failed messages
- Maintain event schema versioning

### Database: {config.database.value}
- **BC Isolation**: Each BC has its own database schema/database
- **Transactions**: Use transactions only within aggregate boundaries
- **Indexing**: Implement proper indexing for queries (especially for ReadModels)
- **Connection Pooling**: Configure appropriate connection pool settings
- **Migration**: Use database migration tools for schema changes
- **Never share database between BCs**: Each BC must have independent database access
{db_guidelines}

### Deployment: {config.deployment.value}
- Follow {config.deployment.value} deployment patterns
- Ensure each BC is independently deployable
- Implement proper health checks and monitoring

## Code Quality Standards

### Testing
- Write GWT (Given/When/Then) tests for all commands
- Test aggregate invariants
- Test event publishing and consumption
- Test cross-BC policies (if applicable)
- Maintain high test coverage

### Error Handling
- Validate all inputs
- Handle aggregate invariant violations gracefully
- Implement retry logic for external calls
- Log errors with sufficient context
- Use appropriate error response codes

### Documentation
- Document aggregate invariants
- Document command and event schemas
- Document cross-BC event contracts
- Keep README files up to date

## File Organization

- Keep BC boundaries clear in directory structure
- Separate domain, infrastructure, and API layers
- Group related functionality together
- Follow framework conventions for project structure

## Important Reminders

1. **BC Isolation**: Never break BC boundaries
2. **Event Contracts**: Maintain backward compatibility for events
3. **Aggregate Invariants**: Always enforce invariants
4. **Actor Authorization**: Check permissions for all commands
5. **Event Sourcing**: Events are immutable facts - never modify them
"""


def _get_file_extensions_for_language(language: str, framework: str) -> str:
    """Get file extension globs based on language and framework."""
    if language == "java":
        return "*.java"
    elif language == "kotlin":
        return "*.kt"
    elif language == "typescript":
        if framework in ["nestjs", "express"]:
            return "*.ts,*.tsx"
        return "*.ts"
    elif language == "python":
        return "*.py"
    elif language == "go":
        return "*.go"
    else:
        return "*"


def _get_code_structure_guide(config: TechStackConfig, bc_name: str) -> str:
    """Generate code structure guide based on technology stack."""
    package_name = config.package_name
    bc_name_upper = bc_name.replace("_", "").title()
    
    if config.language == "java" and config.framework == "spring-boot":
        return f"""
**Backend Structure** (Spring Boot):
```
{bc_name}/
├── src/main/java/{package_name.replace('.', '/')}/{bc_name}/
│   ├── domain/
│   │   ├── aggregate/          # Aggregate root entities
│   │   │   └── {{AggregateName}}.java
│   │   ├── command/            # Command classes and handlers
│   │   │   ├── {{CommandName}}.java
│   │   │   └── {{CommandName}}Handler.java
│   │   ├── event/               # Event classes
│   │   │   └── {{EventName}}.java
│   │   ├── readmodel/           # ReadModel classes
│   │   │   └── {{ReadModelName}}.java
│   │   ├── policy/             # Policy implementations
│   │   │   └── {{PolicyName}}.java
│   │   └── valueobject/         # Value objects
│   │       └── {{ValueObjectName}}.java
│   ├── infrastructure/
│   │   ├── messaging/            # {config.messaging.value} integration
│   │   └── persistence/          # {config.database.value} integration
│   ├── api/
│   │   └── controller/          # REST endpoints
│   │       ├── {{CommandName}}Controller.java
│   │       └── {{ReadModelName}}Controller.java
│   └── application/
│       └── {bc_name_upper}Application.java
├── src/main/resources/
│   └── application.yml
└── src/test/java/{package_name.replace('.', '/')}/{bc_name}/
    └── gwt/                  # GWT test cases
```
"""
    elif config.language == "python" and config.framework == "fastapi":
        return f"""
**Backend Structure** (FastAPI):
```
{bc_name}/
├── domain/
│   ├── aggregate/          # Aggregate root entities
│   │   └── {{aggregate_name}}.py
│   ├── command/            # Command classes and handlers
│   │   ├── {{command_name}}.py
│   │   └── {{command_name}}_handler.py
│   ├── event/               # Event classes
│   │   └── {{event_name}}.py
│   ├── readmodel/           # ReadModel classes
│   │   └── {{readmodel_name}}.py
│   ├── policy/             # Policy implementations
│   │   └── {{policy_name}}.py
│   └── valueobject/         # Value objects
│       └── {{value_object_name}}.py
├── infrastructure/
│   ├── messaging/            # {config.messaging.value} integration
│   └── persistence/          # {config.database.value} integration
├── api/
│   └── controllers/          # REST endpoints
│       ├── {{command_name}}_controller.py
│       └── {{readmodel_name}}_controller.py
└── tests/
    └── gwt/                  # GWT test cases
```
"""
    elif config.language == "typescript" and config.framework == "nestjs":
        return f"""
**Backend Structure** (NestJS):
```
{bc_name}/
├── domain/
│   ├── aggregate/          # Aggregate root entities
│   │   └── {{aggregate-name}}.entity.ts
│   ├── command/            # Command classes and handlers
│   │   ├── {{command-name}}.ts
│   │   └── {{command-name}}.handler.ts
│   ├── event/               # Event classes
│   │   └── {{event-name}}.ts
│   ├── readmodel/           # ReadModel classes
│   │   └── {{readmodel-name}}.entity.ts
│   ├── policy/             # Policy implementations
│   │   └── {{policy-name}}.ts
│   └── valueobject/         # Value objects
│       └── {{value-object-name}}.ts
├── infrastructure/
│   ├── messaging/            # {config.messaging.value} integration
│   └── persistence/          # {config.database.value} integration
├── api/
│   └── controllers/          # REST endpoints
│       ├── {{command-name}}.controller.ts
│       └── {{readmodel-name}}.controller.ts
└── tests/
    └── gwt/                  # GWT test cases
```
"""
    elif config.language == "go":
        return f"""
**Backend Structure** (Go):
```
{bc_name}/
├── domain/
│   ├── aggregate/          # Aggregate root entities
│   │   └── {{aggregate_name}}.go
│   ├── command/            # Command classes and handlers
│   │   ├── {{command_name}}.go
│   │   └── {{command_name}}_handler.go
│   ├── event/               # Event classes
│   │   └── {{event_name}}.go
│   ├── readmodel/           # ReadModel classes
│   │   └── {{readmodel_name}}.go
│   ├── policy/             # Policy implementations
│   │   └── {{policy_name}}.go
│   └── valueobject/         # Value objects
│       └── {{value_object_name}}.go
├── infrastructure/
│   ├── messaging/            # {config.messaging.value} integration
│   └── persistence/          # {config.database.value} integration
├── api/
│   └── controllers/          # REST endpoints
│       ├── {{command_name}}_controller.go
│       └── {{readmodel_name}}_controller.go
└── tests/
    └── gwt/                  # GWT test cases
```
"""
    else:
        return f"""
**Backend Structure** ({config.framework.value}):
```
{bc_name}/
├── domain/
│   ├── aggregates/          # Aggregate root entities
│   ├── commands/            # Command classes and handlers
│   ├── events/               # Event classes
│   ├── readmodels/           # ReadModel classes
│   ├── policies/             # Policy implementations
│   └── valueobjects/         # Value objects
├── infrastructure/
│   ├── messaging/            # {config.messaging.value} integration
│   └── persistence/          # {config.database.value} integration
├── api/
│   └── controllers/          # REST endpoints
└── tests/
    └── gwt/                  # GWT test cases
```
"""


def generate_cursor_tech_stack_rule(config: TechStackConfig) -> str:
    """Generate Cursor rule file (.mdc format) for tech stack (not BC-specific)."""
    # Get file extensions based on language and framework
    file_extensions = _get_file_extensions_for_language(config.language.value, config.framework.value)
    # Build globs pattern for tech stack files
    if "," in file_extensions:
        # Multiple extensions (e.g., *.ts,*.tsx)
        exts = [ext.strip() for ext in file_extensions.split(",")]
        globs_pattern = ",".join([f"**/{ext}" for ext in exts])
    else:
        globs_pattern = f"**/{file_extensions}"
    
    # Get code structure guide (use placeholder BC name)
    code_structure = _get_code_structure_guide(config, "{bc_name}")
    
    # Generate tech stack specific implementation guidelines
    tech_stack_guidelines = _get_tech_stack_implementation_guidelines(config)
    
    return f"""---
alwaysApply: false
description: {config.framework.value} ({config.language.value}) implementation guidelines for DDD aggregates commands events readmodels policies
globs: {globs_pattern}
---

# {config.framework.value} ({config.language.value}) Implementation Guidelines

> **Tech Stack Rule**: This rule applies when implementing code using {config.framework.value} with {config.language.value}.
> Reference BC-specific specs in `specs/{{bc_name}}_spec.md` for detailed requirements.
> Use mention feature (`@{config.framework.value}`) to reference these tech stack standards.

## Technology Stack
- **Language**: {config.language.value}
- **Framework**: {config.framework.value}
- **Messaging**: {config.messaging.value}
- **Database**: {config.database.value}
- **Deployment**: {config.deployment.value}
- **Package Name**: {config.package_name if config.language.value in ['java', 'kotlin'] else 'N/A'}

## Code Structure
{code_structure}

## Implementation Guidelines

{tech_stack_guidelines}

## Reference Files

When implementing a specific BC:
1. **Read BC Spec**: `specs/{{bc_name}}_spec.md` - Complete BC requirements (aggregates, commands, events, properties, GWT tests)
2. **Follow Tech Stack Rules**: This file (mention: `@{config.framework.value}`) - {config.framework.value} specific implementation patterns
3. **Check DDD Principles**: `@ddd-principles` - DDD patterns (always applied)
4. **Check Event Storming Rules**: `@eventstorming-implementation` - Sticker-to-code mapping
5. **Check GWT Test Rules**: `@gwt-test-generation` - GWT test patterns
6. **Check Global Rules**: `@.cursorrules` - DDD principles and general coding standards

## Complete Implementation Checklist

### For Each Bounded Context:

#### 1. Read BC Spec First (MANDATORY)
- [ ] **Read BC Spec** (`specs/{{bc_name}}_spec.md`) - Contains ALL requirements
- [ ] **Count ALL elements** - Aggregates, Commands, Events, ReadModels, Policies, UI Wireframes
- [ ] **Verify completeness** - Ensure spec has all required information

#### 2. Database Setup (MANDATORY)
- [ ] **Configure {config.database.value} connection** - Set up connection in application config
- [ ] **Create schema** - Create tables/collections for ALL aggregates
- [ ] **Create indexes** - Index foreign keys and frequently queried columns
- [ ] **Test connection** - Verify database connection works

#### 3. Implement ALL Commands (100% Coverage)
For EACH Command in BC spec:
- [ ] **Command Handler** - Implement handler with validation
- [ ] **REST API Endpoint** - `POST /api/{{bc_name}}/{{command-name}}` (MANDATORY)
- [ ] **Input Validation** - Validate all inputs from inputSchema
- [ ] **Actor Authorization** - Check actor permissions
- [ ] **Event Emission** - Emit events after execution
- [ ] **Error Handling** - Proper error responses (400, 403, etc.)

#### 4. Implement ALL Events (100% Coverage)
For EACH Event in BC spec:
- [ ] **Event Class** - With all properties from spec
- [ ] **Event Publishing** - Publish to {config.messaging.value}
- [ ] **Version Handling** - Include version in message
- [ ] **Error Handling** - Retry logic, dead-letter queue

#### 5. Implement ALL ReadModels (100% Coverage)
For EACH ReadModel in BC spec:
- [ ] **ReadModel Class** - With all properties from spec
- [ ] **Query API Endpoint** - `GET /api/{{bc_name}}/{{readmodel-name}}` (MANDATORY)
- [ ] **Projection Handler** - Update from events
- [ ] **Pagination** - If isMultipleResult: 'list', support pagination

#### 6. Messaging Setup (MANDATORY)
- [ ] **Configure {config.messaging.value}** - Set up connection
- [ ] **Event Publishers** - Publisher service for all events
- [ ] **Event Consumers** - Consumer service for policies
- [ ] **Test messaging** - Verify events can be published/consumed

#### 7. Frontend (If included)
- [ ] **All Commands have UI** - Every Command has a UI button/form
- [ ] **All ReadModels have Pages** - Every ReadModel has a display page
- [ ] **All APIs Connected** - All UI elements call backend APIs

## Getting Started

1. **Choose a BC**: Select a Bounded Context from `specs/` directory
2. **Read BC Spec**: Review `specs/{{bc_name}}_spec.md` for complete requirements
3. **Follow Tech Stack**: Use mention `@{config.framework.value}` for {config.framework.value} implementation patterns
4. **Reference Other Rules**: Use `@ddd-principles`, `@eventstorming-implementation`, `@gwt-test-generation` as needed
5. **Follow Checklist**: Use the checklist above to ensure 100% implementation coverage

**Remember**: 
- **100% Coverage Required** - Every Command, Event, ReadModel, Policy MUST be implemented
- **No Partial Implementation** - Don't skip any element from BC spec
- **Complete API Endpoints** - Every Command and ReadModel MUST have a REST API endpoint
- This rule provides **tech stack specific** guidance. BC-specific requirements are in `specs/{{bc_name}}_spec.md`.
"""


def _get_tech_stack_implementation_guidelines(config: TechStackConfig) -> str:
    """Generate tech stack specific implementation guidelines."""
    # Get database-specific guidelines
    db_guidelines = _get_database_specific_guidelines(config.database.value)
    
    if config.language == "java" and config.framework == "spring-boot":
        return f"""### Spring Boot Specific Guidelines

#### Commands
- Use `@Service` or `@Component` for command handlers
- Use `@Valid` and `@RequestBody` for request validation
- Use `@Transactional` for aggregate operations (keep transactions within aggregate boundaries)
- Use Spring Data JPA repositories for persistence
- Use `ApplicationEventPublisher` for in-memory events or `KafkaTemplate`/`RabbitTemplate` for messaging

#### Database & Persistence
- Use Spring Data JPA with {config.database.value}
- Configure `application.properties` or `application.yml` for database connection
- Use `@Entity` for aggregate root entities
- Use `@Repository` for data access layer
- Use `@Transactional(readOnly = true)` for ReadModel queries
- Implement proper connection pooling (HikariCP is default in Spring Boot)
{db_guidelines}

#### Events
- Use `@Value` (Lombok) or immutable classes for events
- Use `@Async` for asynchronous event publishing
- Use `@KafkaListener` for Kafka or `@RabbitListener` for RabbitMQ
- Include event version in message headers

#### ReadModels
- Use Spring Data JPA repositories for queries
- Use `@Query` annotations for custom queries
- Support pagination with `Pageable`
- Use `@Entity` and JPA annotations

#### REST Controllers
- Use `@RestController` and `@RequestMapping`
- Use `@PostMapping` for commands, `@GetMapping` for queries
- Use `ResponseEntity` for response codes
- Use `@ExceptionHandler` for error handling

#### Testing
- Use `@SpringBootTest` for integration tests
- Use `@MockBean` for mocking dependencies
- Use `TestRestTemplate` or `MockMvc` for API testing"""
    
    elif config.language == "python" and config.framework == "fastapi":
        return f"""### FastAPI Specific Guidelines

#### Commands
- Use Pydantic models for command DTOs
- Use `@app.post()` decorators for command endpoints
- Use dependency injection for handlers
- Use SQLAlchemy for persistence
- Use async/await for async operations

#### Database & Persistence
- Use SQLAlchemy ORM with {config.database.value}
- Use async SQLAlchemy (`asyncpg` for PostgreSQL, `aiomysql` for MySQL)
- Configure database connection in settings/environment variables
- Use `SessionLocal` for database sessions
- Use `@db.transaction` or `async with session.begin()` for transactions
- Keep transactions within aggregate boundaries
- Use connection pooling (SQLAlchemy connection pool)
{db_guidelines}

#### Events
- Use Pydantic models for events
- Use async message brokers (aiokafka, aio-pika)
- Use background tasks for event publishing
- Include event version in message metadata

#### ReadModels
- Use SQLAlchemy models for ReadModels
- Use async database sessions
- Support pagination with limit/offset
- Use query builders for filtering

#### REST Controllers
- Use FastAPI route decorators
- Use Pydantic for request/response models
- Use `HTTPException` for error handling
- Use dependency injection for services

#### Testing
- Use `TestClient` for API testing
- Use pytest fixtures for test setup
- Mock async dependencies"""
    
    elif config.language == "typescript" and config.framework == "nestjs":
        return f"""### NestJS Specific Guidelines

#### Commands
- Use `@Injectable()` for command handlers
- Use `@Post()` decorators for command endpoints
- Use DTOs with `class-validator` for validation
- Use TypeORM or Prisma for persistence
- Use dependency injection

#### Database & Persistence
- Use TypeORM or Prisma with {config.database.value}
- Configure database connection in `TypeOrmModule` or Prisma schema
- Use `@Entity()` decorators for aggregate root entities (TypeORM)
- Use `@Transaction()` for aggregate operations
- Use repositories for data access
- Keep transactions within aggregate boundaries
- Use connection pooling (TypeORM/Prisma connection pool)
{db_guidelines}

#### Events
- Use classes or interfaces for events
- Use `@EventPattern()` for event listeners
- Use `@CqrsModule` for CQRS patterns
- Use message brokers (Kafka, RabbitMQ) via NestJS microservices

#### ReadModels
- Use TypeORM entities or Prisma models
- Use repositories for queries
- Support pagination with `PaginationDto`
- Use query builders

#### REST Controllers
- Use `@Controller()` and `@Post()`/`@Get()` decorators
- Use DTOs for request/response
- Use `HttpException` for error handling
- Use guards for authorization

#### Testing
- Use `@nestjs/testing` for unit tests
- Use `supertest` for e2e tests
- Mock providers with `Test.createTestingModule()`"""
    
    elif config.language == "go":
        return f"""### Go Specific Guidelines

#### Commands
- Use structs for command DTOs
- Use interfaces for handlers
- Use dependency injection manually or with wire
- Use GORM or sqlx for persistence
- Use context.Context for cancellation

#### Database & Persistence
- Use GORM or sqlx with {config.database.value}
- Configure database connection (DSN) in environment variables or config
- Use GORM models for aggregate root entities
- Use `db.Begin()` for transactions (keep within aggregate boundaries)
- Use connection pooling (database/sql connection pool or GORM)
- Use prepared statements for security
{db_guidelines}

#### Events
- Use structs for events
- Use message brokers (sarama for Kafka, amqp for RabbitMQ)
- Use goroutines for async operations
- Include event version in message headers

#### ReadModels
- Use GORM models or structs
- Use query builders
- Support pagination
- Use database/sql or GORM

#### REST Controllers
- Use gorilla/mux or gin/fiber routers
- Use JSON encoding/decoding
- Use http.Error for error handling
- Use middleware for authorization

#### Testing
- Use testing package for unit tests
- Use httptest for API testing
- Mock dependencies with interfaces"""
    
    else:
        return f"""### {config.framework.value} Specific Guidelines

#### Commands
- Implement command handlers following {config.framework.value} patterns
- Validate inputs using framework validation
- Use dependency injection
- Persist using {config.database.value}

#### Events
- Create immutable event classes
- Publish to {config.messaging.value}
- Handle async operations appropriately

#### ReadModels
- Implement query models
- Support pagination and filtering
- Use {config.database.value} for persistence

#### REST Controllers
- Follow {config.framework.value} routing patterns
- Use framework-specific error handling
- Implement proper HTTP status codes"""


# ============================================================================
# Claude Code Skills 생성 함수들 (Cursor rules 기반)
# ============================================================================

def generate_claude_skill_ddd_principles(config: TechStackConfig) -> str:
    """Generate DDD principles skill for Claude Code."""
    return f"""# DDD Principles and Patterns

> **Always Reference**: These DDD principles apply to all code in this project.
> Reference Event Storming model and BC specs for domain-specific requirements.
> Reference this skill file (`.claude/skills/ddd-principles.md`) when implementing any BC.

## Naming Conventions

- **Commands**: Use imperative verbs (CreateOrder, CancelOrder, ProcessPayment)
- **Events**: Use past tense (OrderCreated, PaymentProcessed, UserRegistered)
- **Aggregates**: Use domain nouns (Order, Payment, User)
- **ReadModels**: Use query intent (OrderList, OrderDetail, UserProfile)

## Bounded Context Boundaries

- **Strict Isolation**: Never directly access another BC's database or internal APIs
- **Event Communication**: All cross-BC communication must go through {config.messaging.value} events
- **Independent Deployment**: Each BC should be independently deployable
- **Own Data Model**: Each BC has its own database schema

## Aggregate Rules

- **Transaction Boundary**: Keep transactions within a single aggregate
- **Invariant Enforcement**: Always enforce all business invariants
- **Root Entity**: Access entities only through the aggregate root
- **Consistency**: Maintain consistency within aggregate boundaries only

## Command-Event Pattern

- **Command Validation**: Validate all inputs before execution
- **Event Emission**: Emit events after successful command execution
- **Idempotency**: Consider idempotency for retryable commands
- **Actor Authorization**: Check actor permissions for all commands

## CQRS Pattern

- **Read-Write Separation**: Separate read models from write models
- **Event Projections**: Update ReadModels via event projections
- **Eventual Consistency**: Accept eventual consistency for read models
- **Query Optimization**: Denormalize data for query performance

## Important Reminders

1. **BC Isolation**: Never break BC boundaries
2. **Event Contracts**: Maintain backward compatibility for events
3. **Aggregate Invariants**: Always enforce invariants
4. **Actor Authorization**: Check permissions for all commands
5. **Event Immutability**: Events are immutable facts - never modify them

## Related Skills

- **Event Storming Implementation**: `.claude/skills/eventstorming-implementation.md` - Sticker-to-code mapping patterns
- **GWT Test Generation**: `.claude/skills/gwt-test-generation.md` - GWT test patterns
- **Tech Stack Skills**: `.claude/skills/{config.framework.value}.md` - Framework-specific implementation guidelines
"""


def generate_claude_skill_eventstorming_implementation(config: TechStackConfig) -> str:
    """Generate Event Storming implementation skill for Claude Code."""
    messaging_platform = config.messaging.value
    
    return f"""# Event Storming Implementation Patterns

> **Event Storming Skill**: This skill maps Event Storming stickers to code implementation patterns.
> Reference BC specs (`specs/{{bc_name}}_spec.md`) for complete sticker details from Event Storming model.
> Reference this skill file (`.claude/skills/eventstorming-implementation.md`) when implementing Commands, Events, Aggregates, ReadModels, Policies, and UI.

## Command Implementation

### Command Handler
- **Naming**: Use imperative verbs (CreateOrder, CancelOrder, ProcessPayment)
- **Validation**: Validate all invariants before executing commands
- **Input Schema**: Use the provided `inputSchema` to define command DTOs
- **Actor Authorization**: Check actor permissions before command execution
- **Execution**: Execute through aggregate root
- **Event Emission**: Emit events after successful command execution
- **Idempotency**: Consider idempotency for commands that may be retried

### REST API Endpoints
- **HTTP Method**: POST (all commands change state)
- **Endpoint Pattern**: `POST /api/{{bc_name}}/{{command-name}}`
- **Request Mapping**: Map request body to command DTO using `inputSchema`
- **Response Codes**:
  - `201 Created` for Create commands
  - `200 OK` for Update/Process commands
  - `204 No Content` for Delete commands
  - `400 Bad Request` for validation errors
  - `403 Forbidden` for authorization failures

## Event Implementation

### Event Class
- **Naming**: Use past tense (OrderCreated, PaymentProcessed, UserRegistered)
- **Schema**: Use the provided `schema` to define event classes
- **Properties**: Map all properties from spec to event fields
- **Immutability**: Events are immutable once emitted
- **Versioning**: Use semantic versioning for event schema evolution
- **Metadata**: Include eventId, timestamp, version, etc.

### Event Publishing
- **Publisher**: Use event publisher service in `infrastructure/messaging/`
- **Platform**: Publish to {messaging_platform} after successful command execution
- **Async**: Publish asynchronously to avoid blocking command execution
- **Versioning**: Include event version in message headers/topic
- **Error Handling**: Handle publishing failures (retry, dead-letter queue)
- **Event Schema**: Use semantic versioning for event schema evolution
- **Metadata**: Include eventId, timestamp, version, etc.

### Event Consumption (Policies)
- **Subscription**: Subscribe to events via {messaging_platform} consumer
- **Cross-BC Events**: Handle events from other BCs (deserialize using other BC event schemas)
- **Idempotency**: Implement idempotency checks for duplicate events
- **Error Handling**: Handle consumption failures gracefully
- **Event Contracts**: Maintain backward compatibility for events

## Aggregate Implementation

- **Root Entity**: Use the `rootEntity` as the aggregate root class
- **Invariants**: Enforce all listed invariants in aggregate methods
- **Properties**: Map all properties with correct types (use `isKey` for primary keys, `isForeignKey` for references)
- **Enumerations**: Use provided enumerations for state management
- **Value Objects**: Implement value objects for complex domain concepts

## ReadModel Implementation

### ReadModel Projection
- **CQRS Pattern**: ReadModels are updated via event projections
- **Projection Handler**: Implement event projection handlers in `domain/readmodels/`
- **Actor Support**: Filter/authorize based on `actor` field
- **Denormalization**: Denormalize data for query performance
- **Eventual Consistency**: Accept eventual consistency (ReadModels may be slightly stale)

### Query API Endpoints
- **HTTP Method**: GET (queries don't change state)
- **Endpoint Patterns**:
  - Single result: `GET /api/{{bc_name}}/{{readmodel-name}}/{{id}}`
  - List: `GET /api/{{bc_name}}/{{readmodel-name}}?filter=value&page=1&size=10`
  - Collection: `GET /api/{{bc_name}}/{{readmodel-name}}`
- **Return Types** (based on `isMultipleResult`):
  - `list`: Return ordered arrays
  - `collection`: Return unordered collections
  - `single result`: Return single objects
- **Features**: Support filtering, pagination, and sorting for list/collection types

## Policy Implementation

### Event Listener
- **Subscription**: Subscribe to trigger events via {config.messaging.value} consumer
- **Cross-BC Events**: Handle events from other BCs (deserialize using other BC event schemas)
- **Idempotency**: Implement idempotency checks to handle duplicate events

### Command Invocation
- **Async Invocation**: Invoke target commands asynchronously via {messaging_platform}
- **Cross-BC Commands**: Handle command invocation in different BCs
- **Data Mapping**: Map event data to command input using event/command schemas
- **Retry Logic**: Implement retry logic for failed invocations

### Service Independence & Dependencies
- **No Direct Service Calls**: Policy BC does NOT call target BC service directly
- **Event Contract Dependency**: Policy BC depends ONLY on event contract (schema), not service implementation
- **Independent Deployment**: Policy BC can be deployed/updated independently
- **Target BC Availability**: Policy BC can handle events even if target BC is temporarily unavailable (events queued in messaging platform)
- **Error Handling**:
  - Schema Mismatch: Send to dead-letter queue (DLQ)
  - Version Mismatch: Support multiple versions or reject unsupported versions
  - Transient vs Permanent Failures: Retry transient failures, send permanent failures to DLQ

## UI Wireframe Implementation

### UI Components
- **Attached to Command**: Create form components for command execution
- **Attached to ReadModel**: Create display/list components for query results
- **Wireframe Description**: Follow wireframe descriptions from BC specs
- **API Integration**: Connect UI to backend APIs (Command POST, ReadModel GET)
- **State Management**: Use framework-specific state management (Pinia, Redux, etc.)
- **Error Handling**: Display user-friendly error messages
- **Loading States**: Show loading indicators during API calls

### Complete UI Implementation Checklist

**For EACH Command in BC spec:**
- [ ] **Create UI Button/Form** - Every Command MUST have a UI element
- [ ] **Create API Service** - Service method for `POST /api/{{bc_name}}/{{command-name}}`
- [ ] **Connect UI to API** - Button/form MUST call API service
- [ ] **Handle Response** - Show success/error, update UI state
- [ ] **Validate Input** - Client-side validation
- [ ] **Loading State** - Show loading during API call

**For EACH ReadModel in BC spec:**
- [ ] **Create Display/List Page** - Every ReadModel MUST have a page
- [ ] **Create API Service** - Service method for `GET /api/{{bc_name}}/{{readmodel-name}}`
- [ ] **Connect Page to API** - Page load MUST call API service
- [ ] **Display Data** - Show ReadModel data in UI
- [ ] **Pagination** - If isMultipleResult: 'list', implement pagination

**For EACH UI Wireframe in BC spec:**
- [ ] **Read Template** - HTML template from BC spec
- [ ] **Create Component** - Implement as Vue/React component
- [ ] **Match Structure** - Follow wireframe template structure
- [ ] **Connect to Command/ReadModel** - Wireframe attached to Command → form, ReadModel → display

**CRITICAL**: 100% Coverage Required - Every Command, ReadModel, and UI Wireframe MUST be implemented.

## Related Skills

- **DDD Principles**: `.claude/skills/ddd-principles.md` - DDD patterns and BC boundaries
- **GWT Test Generation**: `.claude/skills/gwt-test-generation.md` - Test patterns for implementations
- **Tech Stack Skills**: `.claude/skills/{config.framework.value}.md` - Framework-specific implementation patterns
"""


def generate_claude_skill_gwt_test_generation(config: TechStackConfig) -> str:
    """Generate GWT test generation skill for Claude Code."""
    return f"""# GWT Test Generation Guidelines

> **GWT Test Skill**: This skill provides guidelines for writing GWT (Given/When/Then) tests based on Event Storming model.
> Reference BC specs (`specs/{{bc_name}}_spec.md`) for GWT test cases from Event Storming.
> Reference this skill file (`.claude/skills/gwt-test-generation.md`) when writing tests.

## GWT (Given/When/Then) Test Pattern

### Test Structure
- **Given**: Set up preconditions (aggregate state, events)
- **When**: Execute the command or trigger the event
- **Then**: Verify outcomes (events emitted, state changes, invariants)

### Test Coverage
- **Commands**: Write GWT tests for all commands
- **Aggregates**: Test aggregate invariants
- **Events**: Test event publishing and consumption
- **Policies**: Test cross-BC policies (if applicable)
- **ReadModels**: Test query results and projections

## Test Implementation

### Framework-Specific Patterns
- **Spring Boot**: Use `@SpringBootTest`, `@MockBean`, `@Test` (JUnit)
- **FastAPI**: Use `pytest`, `TestClient`
- **NestJS**: Use `@nestjs/testing`, `Test.createTestingModule()`
- **Go**: Use `testing` package, table-driven tests

### Best Practices
- **Isolation**: Each test should be independent
- **Mocking**: Mock external dependencies (messaging, database)
- **Assertions**: Verify all expected outcomes
- **Coverage**: Maintain high test coverage

## Test Data

- **Fixtures**: Use test fixtures for common test data
- **Builders**: Use builder pattern for test object creation
- **Factories**: Use factory methods for aggregate creation
- **Cleanup**: Clean up test data after each test

## Related Skills

- **DDD Principles**: `.claude/skills/ddd-principles.md` - DDD patterns and aggregate rules
- **Event Storming Implementation**: `.claude/skills/eventstorming-implementation.md` - Command, Event, Aggregate implementation patterns
- **Tech Stack Skills**: `.claude/skills/{config.framework.value}.md` - Framework-specific testing patterns
"""


def generate_claude_skill_tech_stack(config: TechStackConfig) -> str:
    """Generate tech stack specific skill for Claude Code."""
    # Get file extensions based on language and framework
    file_extensions = _get_file_extensions_for_language(config.language.value, config.framework.value)
    # Get code structure guide (use placeholder BC name)
    code_structure = _get_code_structure_guide(config, "{bc_name}")
    # Generate tech stack specific implementation guidelines
    tech_stack_guidelines = _get_tech_stack_implementation_guidelines(config)
    # Get database-specific guidelines
    db_guidelines = _get_database_specific_guidelines(config.database.value)
    
    return f"""# {config.framework.value} ({config.language.value}) Implementation Guidelines

> **Tech Stack Skill**: This skill provides {config.framework.value} with {config.language.value} implementation guidelines.
> Reference BC-specific specs in `specs/{{bc_name}}_spec.md` for detailed requirements.
> Reference this skill file (`.claude/skills/{config.framework.value}.md`) when implementing code.

## Technology Stack
- **Language**: {config.language.value}
- **Framework**: {config.framework.value}
- **Messaging**: {config.messaging.value}
- **Database**: {config.database.value}
- **Deployment**: {config.deployment.value}
- **Package Name**: {config.package_name if config.language.value in ['java', 'kotlin'] else 'N/A'}

## Code Structure
{code_structure}

## Implementation Guidelines

{tech_stack_guidelines}

## Database & Persistence

### Database Configuration
- **BC Isolation**: Each BC has its own database schema/database
- **Transactions**: Use transactions only within aggregate boundaries
- **Indexing**: Implement proper indexing for queries (especially for ReadModels)
- **Connection Pooling**: Configure appropriate connection pool settings
- **Migration**: Use database migration tools for schema changes
- **Never share database between BCs**: Each BC must have independent database access

{db_guidelines}

## Reference Files

When implementing a specific BC:
1. **Read BC Spec**: `specs/{{bc_name}}_spec.md` - Complete BC requirements (aggregates, commands, events, properties, GWT tests)
2. **Follow Tech Stack Skills**: This file (`.claude/skills/{config.framework.value}.md`) - {config.framework.value} specific implementation patterns
3. **Check DDD Principles**: `.claude/skills/ddd-principles.md` - DDD patterns (always reference)
4. **Check Event Storming Skills**: `.claude/skills/eventstorming-implementation.md` - Sticker-to-code mapping
5. **Check GWT Test Skills**: `.claude/skills/gwt-test-generation.md` - GWT test patterns
6. **Check BC Agent**: `.claude/agents/{{bc_name}}_agent.md` - BC-specific implementation guidance

## Complete Implementation Checklist

### For Each Bounded Context:

#### 1. Read BC Spec First (MANDATORY)
- [ ] **Read BC Spec** (`specs/{{bc_name}}_spec.md`) - Contains ALL requirements
- [ ] **Count ALL elements** - Aggregates, Commands, Events, ReadModels, Policies, UI Wireframes
- [ ] **Verify completeness** - Ensure spec has all required information

#### 2. Database Setup (MANDATORY)
- [ ] **Configure {config.database.value} connection** - Set up connection in application config
- [ ] **Create schema** - Create tables/collections for ALL aggregates
- [ ] **Create indexes** - Index foreign keys and frequently queried columns
- [ ] **Test connection** - Verify database connection works

#### 3. Implement ALL Commands (100% Coverage)
For EACH Command in BC spec:
- [ ] **Command Handler** - Implement handler with validation
- [ ] **REST API Endpoint** - `POST /api/{{bc_name}}/{{command-name}}` (MANDATORY)
- [ ] **Input Validation** - Validate all inputs from inputSchema
- [ ] **Actor Authorization** - Check actor permissions
- [ ] **Event Emission** - Emit events after execution
- [ ] **Error Handling** - Proper error responses (400, 403, etc.)

#### 4. Implement ALL Events (100% Coverage)
For EACH Event in BC spec:
- [ ] **Event Class** - With all properties from spec
- [ ] **Event Publishing** - Publish to {config.messaging.value}
- [ ] **Version Handling** - Include version in message
- [ ] **Error Handling** - Retry logic, dead-letter queue

#### 5. Implement ALL ReadModels (100% Coverage)
For EACH ReadModel in BC spec:
- [ ] **ReadModel Class** - With all properties from spec
- [ ] **Query API Endpoint** - `GET /api/{{bc_name}}/{{readmodel-name}}` (MANDATORY)
- [ ] **Projection Handler** - Update from events
- [ ] **Pagination** - If isMultipleResult: 'list', support pagination

#### 6. Messaging Setup (MANDATORY)
- [ ] **Configure {config.messaging.value}** - Set up connection
- [ ] **Event Publishers** - Publisher service for all events
- [ ] **Event Consumers** - Consumer service for policies
- [ ] **Test messaging** - Verify events can be published/consumed

#### 7. Frontend (If included)
- [ ] **All Commands have UI** - Every Command has a UI button/form
- [ ] **All ReadModels have Pages** - Every ReadModel has a display page
- [ ] **All APIs Connected** - All UI elements call backend APIs

## Getting Started

1. **Choose a BC**: Select a Bounded Context from `specs/` directory
2. **Read BC Spec**: Review `specs/{{bc_name}}_spec.md` for complete requirements
3. **Follow Tech Stack Skills**: Reference `.claude/skills/{config.framework.value}.md` for {config.framework.value} implementation patterns
4. **Reference Other Skills**: Use `.claude/skills/ddd-principles.md`, `.claude/skills/eventstorming-implementation.md`, `.claude/skills/gwt-test-generation.md` as needed
5. **Follow Checklist**: Use the checklist above to ensure 100% implementation coverage

**Remember**: 
- **100% Coverage Required** - Every Command, Event, ReadModel, Policy MUST be implemented
- **No Partial Implementation** - Don't skip any element from BC spec
- **Complete API Endpoints** - Every Command and ReadModel MUST have a REST API endpoint
- This skill provides **tech stack specific** guidance. BC-specific requirements are in `specs/{{bc_name}}_spec.md`.

## Related Skills

- **DDD Principles**: `.claude/skills/ddd-principles.md` - DDD patterns and BC boundaries
- **Event Storming Implementation**: `.claude/skills/eventstorming-implementation.md` - Sticker-to-code mapping
- **GWT Test Generation**: `.claude/skills/gwt-test-generation.md` - GWT test patterns
"""


def generate_claude_skill_frontend(config: TechStackConfig) -> str:
    """Generate frontend framework skill for Claude Code - Technical implementation patterns only."""
    if not config.include_frontend or not config.frontend_framework:
        return ""
    
    frontend_guidelines = _get_frontend_implementation_guidelines(config)
    
    return f"""# {config.frontend_framework.value} Frontend Implementation Guidelines

> **Frontend Skill**: This skill provides {config.frontend_framework.value} **technical implementation patterns** (HOW to implement).
> For frontend architecture and strategy (WHAT/WHY), refer to `Frontend-PRD.md`.
> Reference BC specs (`specs/{{bc_name}}_spec.md`) for UI wireframes and attached Commands/ReadModels.
> Reference this skill file (`.claude/skills/{config.frontend_framework.value}.md`) when writing frontend code.

## Frontend Framework
- **Framework**: {config.frontend_framework.value}
- **Backend API**: {config.framework.value} REST APIs
- **State Management**: Framework-specific state management

## Code Structure

**Frontend Structure** ({config.frontend_framework.value}):
```
frontend/
├── src/
│   ├── features/              # Feature-based organization (BC-based)
│   │   └── {{bc_name}}/
│   │       ├── components/    # UI components
│   │       ├── views/         # Page views
│   │       ├── stores/        # State management
│   │       └── services/      # API services
│   ├── shared/                # Shared components
│   └── router/                # Routing configuration
└── package.json
```

## Implementation Guidelines

{frontend_guidelines}

## Reference Files

When implementing frontend code:
1. **Read Frontend PRD**: `Frontend-PRD.md` - Frontend architecture, strategy, and UI overview (read this first)
2. **Read Backend PRD**: `PRD.md` - Backend architecture and API endpoints
3. **Read BC Specs**: `specs/{{bc_name}}_spec.md` - UI wireframes and API contracts
4. **Follow Frontend Skills**: This file - {config.frontend_framework.value} technical implementation patterns
5. **Check Backend Skills**: `.claude/skills/{config.framework.value}.md` - Backend API patterns

## Complete Implementation Checklist

### For EACH Command in BC spec:
- [ ] **Create UI Button/Form** - Every Command MUST have a UI element
- [ ] **Create API Service** - Service method for `POST /api/{{bc_name}}/{{command-name}}`
- [ ] **Connect UI to API** - Button/form MUST call API service
- [ ] **Handle Response** - Show success/error, update UI state
- [ ] **Validate Input** - Client-side validation
- [ ] **Loading State** - Show loading during API call

### For EACH ReadModel in BC spec:
- [ ] **Create Display/List Page** - Every ReadModel MUST have a page
- [ ] **Create API Service** - Service method for `GET /api/{{bc_name}}/{{readmodel-name}}`
- [ ] **Connect Page to API** - Page load MUST call API service
- [ ] **Display Data** - Show ReadModel data in UI
- [ ] **Pagination** - If isMultipleResult: 'list', implement pagination

### For EACH UI Wireframe in BC spec:
- [ ] **Read Template** - HTML template from BC spec
- [ ] **Create Component** - Implement as {config.frontend_framework.value} component
- [ ] **Match Structure** - Follow wireframe template structure
- [ ] **Connect to Command/ReadModel** - Wireframe attached to Command → form, ReadModel → display

**CRITICAL**: 100% Coverage Required - Every Command, ReadModel, and UI Wireframe MUST be implemented.

## Related Skills

- **Event Storming Implementation**: `.claude/skills/eventstorming-implementation.md` - UI wireframe implementation patterns
- **Tech Stack Skills**: `.claude/skills/{config.framework.value}.md` - Backend API patterns
- **DDD Principles**: `.claude/skills/ddd-principles.md` - DDD patterns
"""


def generate_agent_config(bc: dict, config: TechStackConfig) -> str:
    bc_name = (bc.get("name", "unknown") or "unknown").lower().replace(" ", "_")
    bc_display_name = bc.get("name", "Unknown")
    bc_desc = bc.get("description", "No description")
    
    aggs = bc.get("aggregates", []) or []
    agg_names = [a.get("name", "") for a in aggs if a.get("name")]
    
    rms = bc.get("readmodels", []) or []
    rm_names = [rm.get("name", "") for rm in rms if rm.get("name")]
    
    pols = bc.get("policies", []) or []
    
    # Count commands and events
    total_cmds = sum(len(a.get("commands", []) or []) for a in aggs)
    total_evts = sum(len(a.get("events", []) or []) for a in aggs)
    
    # Build skills reference list
    skills_refs = [
        f"- `.claude/skills/ddd-principles.md` - DDD patterns and BC boundaries (always reference)",
        f"- `.claude/skills/eventstorming-implementation.md` - Sticker-to-code mapping (Command, Event, Aggregate, ReadModel, Policy, UI)",
        f"- `.claude/skills/gwt-test-generation.md` - GWT (Given/When/Then) test patterns",
        f"- `.claude/skills/{config.framework.value}.md` - {config.framework.value} implementation guidelines",
    ]
    if config.include_frontend and config.frontend_framework:
        skills_refs.append(f"- `.claude/skills/{config.frontend_framework.value}.md` - Frontend framework guidelines")
    
    skills_refs_text = "\n".join(skills_refs)
    
    return f"""# Agent Configuration: {bc_display_name}

## Scope & Boundaries
- **Bounded Context**: {bc_display_name}
- **Directory**: Only modify files within `{bc_name}/`
- **Spec File**: Refer to `specs/{bc_name}_spec.md` for complete requirements
- **BC Description**: {bc_desc}

## Required Skills

Before implementing, ensure you have loaded these skills:
{skills_refs_text}

**Note**: These skills provide common implementation patterns. Reference them when implementing Commands, Events, Aggregates, ReadModels, Policies, and UI components.

## Your Responsibilities

You are responsible for implementing the **{bc_display_name}** Bounded Context. This BC is part of a larger microservices architecture using Domain-Driven Design (DDD) and Event-Driven Architecture (EDA).

### Key Components

#### Aggregates ({len(agg_names)} total)
{chr(10).join([f"- **{name}**" for name in agg_names if name]) if agg_names else "- None defined"}

**Your Tasks:**
- Implement aggregate root entities with all properties (see spec for complete property list)
- Enforce business invariants listed in the spec
- Implement enumerations and value objects
- Maintain transactional consistency within each aggregate

**Reference Skills:**
- `.claude/skills/ddd-principles.md` - Aggregate rules and transaction boundaries
- `.claude/skills/eventstorming-implementation.md` - Aggregate implementation patterns
- `.claude/skills/{config.framework.value}.md` - Framework-specific aggregate patterns

#### Commands ({total_cmds} total)

**Reference Skills for Implementation:**
- `.claude/skills/eventstorming-implementation.md` - Command handler and REST API endpoint patterns
- `.claude/skills/{config.framework.value}.md` - Framework-specific command implementation
- `.claude/skills/ddd-principles.md` - Command validation and actor authorization

**Key Requirements:**
- All commands MUST have REST API endpoints: `POST /api/{bc_name}/{{command-name}}`
- Validate inputs using `inputSchema` from spec
- Check actor authorization (match actor field from spec)
- Emit events after successful execution

#### Events ({total_evts} total)

**Reference Skills for Implementation:**
- `.claude/skills/eventstorming-implementation.md` - Event class, publishing, and consumption patterns
- `.claude/skills/{config.framework.value}.md` - Framework-specific event implementation

**Key Requirements:**
- All events MUST be published to {config.messaging.value}
- Include version in message headers/topic
- Handle failures (retry, dead-letter queue)

#### ReadModels ({len(rm_names)} total)
{chr(10).join([f"- **{name}**" for name in rm_names if name]) if rm_names else "- None defined"}

**Reference Skills for Implementation:**
- `.claude/skills/eventstorming-implementation.md` - ReadModel projection and query API endpoint patterns
- `.claude/skills/{config.framework.value}.md` - Framework-specific ReadModel implementation

**Key Requirements:**
- All ReadModels MUST have query API endpoints: `GET /api/{bc_name}/{{readmodel-name}}`
- Support actor-based filtering (check actor from spec)
- Support pagination for list/collection types

#### Policies ({len(pols)} total)

**Reference Skills for Implementation:**
- `.claude/skills/eventstorming-implementation.md` - Policy event listener and command invocation patterns
- `.claude/skills/ddd-principles.md` - Cross-BC communication patterns

**Key Requirements:**
- Subscribe to trigger events via {config.messaging.value} consumer
- Invoke target commands asynchronously via {config.messaging.value}
- Implement idempotency checks
- Handle cross-BC events (deserialize using other BC event schemas)

## BC-Specific Implementation Notes

### Technology Stack
- **Language**: {config.language.value}
- **Framework**: {config.framework.value}
- **Messaging**: {config.messaging.value}
- **Database**: {config.database.value}
- **Deployment**: {config.deployment.value}

**Note**: For detailed tech stack implementation guidelines, see `.claude/skills/{config.framework.value}.md`

### BC-Specific Constraints

1. **BC Boundary**: Do NOT access other BCs' databases or internal APIs directly
2. **Event Contracts**: Do NOT change event schemas without versioning
3. **Aggregate Invariants**: Always enforce all invariants listed in the spec
4. **Actor Authorization**: Check actor permissions for all commands
5. **Transaction Scope**: Keep transactions within a single aggregate

## Reference Files (Efficient Context Usage)

**Claude Code Context Strategy:**
- This agent file provides **BC-specific guidance** (scope, boundaries, component counts)
- The spec file (`specs/{bc_name}_spec.md`) provides **complete requirements** (all properties, schemas, test cases)
- The skills files (`.claude/skills/*.md`) provide **common implementation patterns**
- The main PRD (`PRD.md`) provides **architecture context** (principles, cross-BC patterns)
- **Load only what you need**: Reference specific sections rather than loading entire files

**File References:**
- **Spec**: `specs/{bc_name}_spec.md` - Complete BC specification with all details (MUST READ FIRST)
- **Skills**: `.claude/skills/*.md` - Common implementation patterns (reference as needed)
- **Main PRD**: `PRD.md` - Overall architecture and guidelines
- **Project Context**: `CLAUDE.md` - Project overview

## Getting Started

1. **Load Required Skills**: Ensure all required skills (listed above) are loaded
2. **Read BC Spec**: Open `specs/{bc_name}_spec.md` to get complete requirements (aggregates, commands, events, properties, GWT tests)
3. **Reference Skills**: Use skills files for implementation patterns when needed
4. **Check Architecture**: Reference `PRD.md` when implementing cross-BC features or policies

**Implementation Order:**
1. Aggregate root entities (check spec for properties)
2. Commands and events (check spec for schemas)
3. ReadModel projections (check spec for structure)
4. Policies (check spec and PRD for cross-BC contracts)
5. GWT tests (check spec for test scenarios)
6. API endpoints

**Remember**: 
- You are implementing ONE bounded context. Focus on this BC's responsibilities.
- Communicate with other BCs only through events.
- Reference skills files for common patterns, spec file for BC-specific requirements.
"""


def generate_readme(bcs: list[dict], config: TechStackConfig) -> str:
    return f"""# {config.project_name}

Generated from Event Storming model.

## Bounded Contexts
{chr(10).join([f"- {bc.get('name','Unknown')}: {bc.get('description','')}" for bc in bcs])}
"""


def generate_frontend_prd(bcs: list[dict], config: TechStackConfig) -> str:
    """Generate Frontend PRD based on UI wireframes and ReadModels."""
    if not config.include_frontend or not config.frontend_framework:
        return ""
    
    frontend_fw = config.frontend_framework.value
    
    # Collect all UIs and their attached commands/readmodels
    all_uis = []
    for bc in bcs:
        uis = bc.get("uis", []) or []
        for ui in uis:
            if ui.get("id"):
                all_uis.append({
                    "bc_name": bc.get("name", "Unknown"),
                    "ui": ui
                })
    
    # Collect ReadModels for query screens
    all_readmodels = []
    for bc in bcs:
        rms = bc.get("readmodels", []) or []
        for rm in rms:
            if rm.get("id"):
                all_readmodels.append({
                    "bc_name": bc.get("name", "Unknown"),
                    "readmodel": rm
                })
    
    prd = f"""# {config.project_name} - Frontend Product Requirements Document

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## ⚠️ Important: Read All Reference Files

**This Frontend PRD provides frontend architecture, strategy, and UI overview (WHAT/WHY). For technical implementation patterns (HOW), refer to:**
1. **Frontend Tech Stack Rules/Skills**: `.cursor/rules/{frontend_fw}.mdc` (Cursor) or `.claude/skills/{frontend_fw}.md` (Claude) - Technical implementation patterns
2. **Backend PRD** (`PRD.md`) - Backend architecture and API endpoints
3. **BC Specifications** (`specs/{{bc_name}}_spec.md`) - Complete backend requirements including UI wireframes
4. **Backend Tech Stack Rules/Skills**: `.cursor/rules/{config.framework.value}.mdc` (Cursor) or `.claude/skills/{config.framework.value}.md` (Claude) - Backend API patterns

## Technology Stack

| Component | Choice |
|-----------|--------|
| **Frontend Framework** | {frontend_fw} |
| **Backend API** | {config.framework.value} ({config.language.value}) |
| **Deployment** | {config.deployment.value} |

## UI Wireframes Overview

Total UI Screens: {len(all_uis)}
Total Query Screens (ReadModels): {len(all_readmodels)}

### UI Screens by Bounded Context
"""
    
    for bc in bcs:
        uis = bc.get("uis", []) or []
        if uis:
            bc_name = bc.get("name", "Unknown")
            bc_name_slug = bc_name.lower().replace(" ", "_")
            prd += f"\n#### {bc_name} ({len(uis)} screens)\n"
            prd += f"**Reference**: See `specs/{bc_name_slug}_spec.md` for detailed UI wireframes with templates.\n\n"
            for ui in uis:
                if ui.get("id"):
                    ui_name = ui.get("name", "Unknown")
                    attached_to = ui.get("attachedToName", "")
                    attached_type = ui.get("attachedToType", "")
                    description = ui.get("description", "")
                    prd += f"- **{ui_name}**"
                    if attached_to:
                        prd += f" (attached to {attached_type}: `{attached_to}`)"
                    prd += "\n"
                    if description:
                        prd += f"  - Description: {description}\n"
                    prd += f"  - **Wireframe Template**: See `specs/{bc_name_slug}_spec.md` for complete HTML template\n"
    
    prd += f"""
### Query Screens (ReadModels)

"""
    for item in all_readmodels:
        bc_name = item["bc_name"]
        rm = item["readmodel"]
        rm_name = rm.get("name", "Unknown")
        actor = rm.get("actor", "")
        is_multiple = rm.get("isMultipleResult", "")
        prd += f"- **{rm_name}** (BC: {bc_name})"
        if actor:
            prd += f" - Actor: {actor}"
        if is_multiple:
            prd += f" - Result Type: {is_multiple}"
        prd += "\n"
    
    prd += f"""
## Frontend Implementation Strategy

### Progressive BC Integration: Main Page First, Then BC Features

**This is the recommended implementation order for frontend development:**

1. **Phase 1: Main Landing Page** (Start Here)
   - Create main landing/home page (`HomeView.vue` or `HomePage.tsx`)
   - Implement navigation structure (menu, sidebar, header)
   - Add routing foundation
   - Set up shared layout components
   - Configure state management infrastructure

2. **Phase 2: Add BC Features One by One**
   - For each Bounded Context, add its domain features incrementally:
     - Create BC feature directory: `features/{{bc_name}}/`
     - Implement BC-specific components, views, stores, services
     - Add routes for BC pages
     - Integrate BC features into main navigation
   - **Order**: Start with core BCs (e.g., User/Auth BC), then add business BCs

3. **Phase 3: Integration & Polish**
   - Connect BC features to main navigation
   - Implement cross-BC navigation flows
   - Add shared components and utilities
   - Optimize and refactor

**Implementation Order Example**:
```
1. Main Page (Home/Landing) → Navigation structure
2. BC 1 (e.g., User/Auth) → Login, Profile pages
3. BC 2 (e.g., Order) → Order list, Order detail pages
4. BC 3 (e.g., Payment) → Payment pages
5. ... (continue for each BC)
```

## UI/UX Requirements

- **Responsive Design**: Support mobile, tablet, desktop
- **Accessibility**: Follow WCAG guidelines
- **Error Messages**: Display user-friendly error messages
- **Validation**: Client-side validation before API calls
- **Loading States**: Show loading indicators
- **Success Feedback**: Confirm successful operations

## Wireframe Implementation Overview

For each UI wireframe:
1. **Read BC spec** (`specs/{{bc_name}}_spec.md`) - Contains complete wireframe templates and descriptions
2. **Identify attached Command/ReadModel** from BC spec
3. **Create view component** for the screen based on wireframe template
4. **Implement form/display** based on Command/ReadModel properties from BC spec
5. **Connect to API** using service layer (see Frontend Tech Stack Rules/Skills for technical patterns)
6. **Handle responses** and update UI accordingly

**Important**: 
- Wireframe templates (HTML) are stored in BC specs, not in this Frontend-PRD. Always refer to `specs/{{bc_name}}_spec.md` for detailed wireframe templates.
- For technical implementation patterns (API integration, state management, component structure), refer to Frontend Tech Stack Rules/Skills.

## Reference Files

- **Backend PRD**: `PRD.md` - Backend architecture and API endpoints
- **BC Specs**: `specs/{{bc_name}}_spec.md` - Complete backend requirements including UI wireframes
- **Frontend Tech Stack Rules/Skills**: 
  - Cursor: `@{frontend_fw}` - {frontend_fw} technical implementation patterns (use @mention)
  - Claude: `.claude/skills/{frontend_fw}.md` - {frontend_fw} technical implementation patterns
- **Backend Tech Stack Rules/Skills**: 
  - Cursor: `@{config.framework.value}` - Backend API patterns (use @mention)
  - Claude: `.claude/skills/{config.framework.value}.md` - Backend API patterns
- **Event Storming Rules/Skills**: 
  - Cursor: `@eventstorming-implementation` - UI wireframe implementation patterns
  - Claude: `.claude/skills/eventstorming-implementation.md` - UI wireframe implementation patterns

## Getting Started

### Implementation Workflow: Main Page First, Then BC Features

**When asked to "진행해" (proceed) for frontend implementation:**

1. **Read Both PRDs Together** (Architecture & Strategy):
   - ✅ **Backend PRD** (`PRD.md`) - Understand API endpoints and data contracts
   - ✅ **Frontend PRD** (`Frontend-PRD.md`) - This file for frontend architecture, strategy, and UI overview
   - ✅ **BC Specs** (`specs/{{bc_name}}_spec.md`) - Check UI wireframes with templates and attached Commands/ReadModels

2. **Start with Main Landing Page** (Follow strategy from this PRD):
   - Create main/home page first (navigation foundation)
   - Set up routing structure
   - Implement shared layout components (header, sidebar, footer)
   - Configure state management infrastructure

3. **Add BC Features Incrementally** (Follow strategy from this PRD):
   - For each BC, read its spec (`specs/{{bc_name}}_spec.md`)
   - Create BC feature directory: `features/{{bc_name}}/`
   - Implement BC pages/components based on wireframes from BC spec
   - Add BC routes to main navigation
   - Connect to backend APIs (from Backend PRD)

4. **Follow Technical Implementation Patterns** (Refer to Frontend Tech Stack Rules/Skills):
   - **Frontend Tech Stack Rules/Skills**: For {frontend_fw} technical patterns (component structure, API integration, state management)
   - **Backend Tech Stack Rules/Skills**: For API patterns
   - **Event Storming Rules/Skills**: For UI wireframe implementation patterns

5. **For Each BC Feature**:
   - Read wireframe template from BC spec (`specs/{{bc_name}}_spec.md`)
   - Create components based on wireframe template
   - Use attached Command/ReadModel properties from BC spec
   - Connect to APIs using service layer (see Frontend Tech Stack Rules/Skills for technical details)
   - Test integration and error handling

**Remember**: 
- **This Frontend-PRD provides architecture and strategy** (WHAT/WHY) - Read this first for overall approach
- **Frontend Tech Stack Rules/Skills provide technical patterns** (HOW) - Refer to them when writing code
- **Always start with main page** - It provides the foundation for all BC features
- **Add BC features one by one** - Don't try to implement all BCs at once
- **Wireframe templates are in BC specs**, not in this Frontend-PRD
"""
    
    return prd


def generate_frontend_cursor_rule(config: TechStackConfig) -> str:
    """Generate Cursor rule file for frontend framework - Technical implementation patterns only."""
    if not config.include_frontend or not config.frontend_framework:
        return ""
    
    frontend_fw = config.frontend_framework.value
    
    # Get file extensions based on frontend framework
    if frontend_fw == "vue":
        file_extensions = "*.vue,*.ts,*.js"
    elif frontend_fw == "react":
        file_extensions = "*.tsx,*.ts,*.jsx,*.js"
    else:
        file_extensions = "*.ts,*.js,*.vue,*.tsx,*.jsx"
    
    # Get frontend-specific guidelines
    frontend_guidelines = _get_frontend_implementation_guidelines(config)
    
    return f"""---
alwaysApply: false
description: {frontend_fw} frontend implementation guidelines for UI components views stores services
globs: frontend/**/{file_extensions},src/**/{file_extensions}
---

# {frontend_fw} Frontend Implementation Guidelines

> **Frontend Tech Stack Rule**: This rule provides {frontend_fw} **technical implementation patterns** (HOW to implement).
> For frontend architecture and strategy (WHAT/WHY), refer to `Frontend-PRD.md`.
> Reference backend PRD (`PRD.md`) and BC specs (`specs/{{bc_name}}_spec.md`) for API contracts.
> Use mention feature (`@{frontend_fw}`) to reference these frontend standards.

## Technology Stack
- **Frontend Framework**: {frontend_fw}
- **Backend API**: {config.framework.value} ({config.language.value})
- **Deployment**: {config.deployment.value}

## Code Structure

**Frontend Structure** ({frontend_fw}):
```
frontend/
├── src/
│   ├── features/              # Feature-based organization (BC-based)
│   │   └── {{bc_name}}/
│   │       ├── components/    # UI components
│   │       │   └── {{ComponentName}}.vue (or .tsx)
│   │       ├── views/         # Page views
│   │       │   └── {{ViewName}}.vue (or .tsx)
│   │       ├── stores/        # State management
│   │       │   └── {{StoreName}}.ts (or .js)
│   │       └── services/      # API services
│   │           └── {{ServiceName}}.ts (or .js)
│   ├── shared/                # Shared components
│   │   ├── components/
│   │   └── utils/
│   └── router/                # Routing configuration
└── package.json
```

## Implementation Guidelines

{frontend_guidelines}

## Reference Files

When implementing frontend code:
1. **Read Frontend PRD**: `Frontend-PRD.md` - Frontend architecture, strategy, and UI overview (read this first)
2. **Read Backend PRD**: `PRD.md` - Backend architecture and API endpoints
3. **Read BC Specs**: `specs/{{bc_name}}_spec.md` - UI wireframes and API contracts
4. **Follow Frontend Rules**: This file (mention: `@{frontend_fw}`) - {frontend_fw} technical implementation patterns
5. **Check Backend Rules**: `.cursor/rules/{config.framework.value}.mdc` (mention: `@{config.framework.value}`) - Backend API patterns

## Complete Implementation Checklist

### For Each Bounded Context:

#### 1. Read BC Spec First
- [ ] **Read BC Spec** (`specs/{{bc_name}}_spec.md`) - Contains ALL UI wireframes, Commands, ReadModels
- [ ] **Identify all Commands** in the BC spec - Each Command MUST have a UI button/form
- [ ] **Identify all ReadModels** in the BC spec - Each ReadModel MUST have a display/list page
- [ ] **Check UI Wireframes** - Each wireframe template shows the UI structure

#### 2. Implement ALL Commands (100% Coverage Required)
For EACH Command in BC spec:
- [ ] **Create UI Button/Form** - Every Command MUST have a UI element (button, form, etc.)
- [ ] **Create API Service Method** - Service method to call `POST /api/{{bc_name}}/{{command-name}}`
- [ ] **Connect Button to API** - Button click/form submit MUST call the API service
- [ ] **Handle Response** - Show success/error messages, update UI state
- [ ] **Validate Input** - Client-side validation before API call
- [ ] **Loading State** - Show loading indicator during API call

**CRITICAL**: If a Command exists in BC spec, it MUST have:
1. A UI button/form element
2. An API service method
3. Connection between UI and API
4. Error handling

#### 3. Implement ALL ReadModels (100% Coverage Required)
For EACH ReadModel in BC spec:
- [ ] **Create Display/List Page** - Every ReadModel MUST have a page/component
- [ ] **Create API Service Method** - Service method to call `GET /api/{{bc_name}}/{{readmodel-name}}`
- [ ] **Connect Page to API** - Page load MUST call the API service
- [ ] **Display Data** - Show ReadModel data in UI (list, detail, etc.)
- [ ] **Handle Pagination** - If `isMultipleResult: 'list'`, implement pagination
- [ ] **Error Handling** - Handle API errors gracefully

**CRITICAL**: If a ReadModel exists in BC spec, it MUST have:
1. A display/list page/component
2. An API service method
3. Connection between page and API
4. Data display logic

#### 4. Implement ALL UI Wireframes (100% Coverage Required)
For EACH UI Wireframe in BC spec:
- [ ] **Read Wireframe Template** - HTML template from BC spec
- [ ] **Create Component/Page** - Implement wireframe as Vue/React component
- [ ] **Connect to Attached Command/ReadModel** - Wireframe attached to Command → form, ReadModel → display
- [ ] **Match Template Structure** - Follow wireframe template HTML structure
- [ ] **Add Styling** - Apply appropriate styling (framework-specific)

#### 5. Complete Integration
- [ ] **All Commands have UI** - Verify every Command has a UI button/form
- [ ] **All ReadModels have Pages** - Verify every ReadModel has a display page
- [ ] **All APIs are Connected** - Verify all UI elements call backend APIs
- [ ] **Error Handling** - All API calls have error handling
- [ ] **Loading States** - All API calls show loading indicators
- [ ] **Navigation** - Add routes for all BC pages to main navigation

## Getting Started

1. **Choose a BC**: Select a Bounded Context from `specs/` directory
2. **Read BC Spec**: Review `specs/{{bc_name}}_spec.md` for UI wireframes and API contracts
3. **Follow Frontend Tech Stack**: Use this rule for {frontend_fw} implementation patterns
4. **Check Backend PRD**: Reference `PRD.md` for API endpoint details
5. **Implement ALL Commands and ReadModels** - Use the checklist above

**Remember**: 
- **100% Coverage Required** - Every Command and ReadModel in BC spec MUST be implemented
- **No Partial Implementation** - Don't skip any Command or ReadModel
- **Complete UI-API Connection** - Every UI element MUST be connected to backend API
"""


# ============================================================================
# 세분화된 Cursor Rules 생성 함수들
# ============================================================================

def generate_ddd_principles_rule(config: TechStackConfig) -> str:
    """Generate DDD principles rule file."""
    return f"""---
alwaysApply: true
description: Domain-Driven Design (DDD) principles and patterns for Event Storming model
---

# DDD Principles and Patterns

> **Always Applied**: These DDD principles apply to all code in this project.
> Reference Event Storming model and BC specs for domain-specific requirements.
> Use mention feature (`@ddd-principles`) to reference these DDD patterns.

## Naming Conventions

- **Commands**: Use imperative verbs (CreateOrder, CancelOrder, ProcessPayment)
- **Events**: Use past tense (OrderCreated, PaymentProcessed, UserRegistered)
- **Aggregates**: Use domain nouns (Order, Payment, User)
- **ReadModels**: Use query intent (OrderList, OrderDetail, UserProfile)

## Bounded Context Boundaries

- **Strict Isolation**: Never directly access another BC's database or internal APIs
- **Event Communication**: All cross-BC communication must go through {config.messaging.value} events
- **Independent Deployment**: Each BC should be independently deployable
- **Own Data Model**: Each BC has its own database schema

## Aggregate Rules

- **Transaction Boundary**: Keep transactions within a single aggregate
- **Invariant Enforcement**: Always enforce all business invariants
- **Root Entity**: Access entities only through the aggregate root
- **Consistency**: Maintain consistency within aggregate boundaries only

## Command-Event Pattern

- **Command Validation**: Validate all inputs before execution
- **Event Emission**: Emit events after successful command execution
- **Idempotency**: Consider idempotency for retryable commands
- **Actor Authorization**: Check actor permissions for all commands

## CQRS Pattern

- **Read-Write Separation**: Separate read models from write models
- **Event Projections**: Update ReadModels via event projections
- **Eventual Consistency**: Accept eventual consistency for read models
- **Query Optimization**: Denormalize data for query performance

## Important Reminders

1. **BC Isolation**: Never break BC boundaries
2. **Event Contracts**: Maintain backward compatibility for events
3. **Aggregate Invariants**: Always enforce invariants
4. **Actor Authorization**: Check permissions for all commands
5. **Event Immutability**: Events are immutable facts - never modify them

## Related Rules

- **Event Storming Implementation**: `@eventstorming-implementation` - Sticker-to-code mapping patterns
- **GWT Test Generation**: `@gwt-test-generation` - GWT test patterns
- **Tech Stack Rules**: `@{config.framework.value}` - Framework-specific implementation guidelines
"""






def generate_gwt_test_generation_rule(config: TechStackConfig) -> str:
    """Generate GWT test generation rules."""
    return f"""---
alwaysApply: false
description: GWT (Given/When/Then) test generation guidelines based on Event Storming GWT test cases
globs: **/*Test*.java,**/*Test*.kt,**/*test*.py,**/*test*.ts,**/*test*.go,**/*spec*.ts
---

# GWT Test Generation Rules

> **GWT Test Rule**: This rule applies when writing GWT (Given/When/Then) tests based on Event Storming model.
> Reference BC specs (`specs/{{bc_name}}_spec.md`) for GWT test cases from Event Storming.
> Use mention feature (`@gwt-test-generation`) to reference these testing patterns.

## GWT (Given/When/Then) Test Pattern

### Test Structure
- **Given**: Set up preconditions (aggregate state, events)
- **When**: Execute the command or trigger the event
- **Then**: Verify outcomes (events emitted, state changes, invariants)

### Test Coverage
- **Commands**: Write GWT tests for all commands
- **Aggregates**: Test aggregate invariants
- **Events**: Test event publishing and consumption
- **Policies**: Test cross-BC policies (if applicable)
- **ReadModels**: Test query results and projections

## Test Implementation

### Framework-Specific Patterns
- **Spring Boot**: Use `@SpringBootTest`, `@MockBean`, `@Test` (JUnit)
- **FastAPI**: Use `pytest`, `TestClient`
- **NestJS**: Use `@nestjs/testing`, `Test.createTestingModule()`
- **Go**: Use `testing` package, table-driven tests

### Best Practices
- **Isolation**: Each test should be independent
- **Mocking**: Mock external dependencies (messaging, database)
- **Assertions**: Verify all expected outcomes
- **Coverage**: Maintain high test coverage

## Test Data

- **Fixtures**: Use test fixtures for common test data
- **Builders**: Use builder pattern for test object creation
- **Factories**: Use factory methods for aggregate creation
- **Cleanup**: Clean up test data after each test

## Related Rules

- **DDD Principles**: `@ddd-principles` - DDD patterns and aggregate rules
- **Event Storming Implementation**: `@eventstorming-implementation` - Command, Event, Aggregate implementation patterns
- **Tech Stack Rules**: `@{config.framework.value}` - Framework-specific testing patterns
"""


def generate_eventstorming_implementation_rule(config: TechStackConfig) -> str:
    """Generate Event Storming sticker-to-code implementation rules."""
    messaging_platform = config.messaging.value
    
    return f"""---
alwaysApply: false
description: Event Storming sticker-to-code implementation patterns (Command, Event, Aggregate, ReadModel, Policy, UI)
globs: **/*
---

# Event Storming Implementation Rules

> **Event Storming Rule**: This rule maps Event Storming stickers to code implementation patterns.
> Reference BC specs (`specs/{{bc_name}}_spec.md`) for complete sticker details from Event Storming model.
> Use mention feature (`@eventstorming-implementation`) to reference these patterns.

## Command Implementation

### Command Handler
- **Naming**: Use imperative verbs (CreateOrder, CancelOrder, ProcessPayment)
- **Validation**: Validate all invariants before executing commands
- **Input Schema**: Use the provided `inputSchema` to define command DTOs
- **Actor Authorization**: Check actor permissions before command execution
- **Execution**: Execute through aggregate root
- **Event Emission**: Emit events after successful command execution
- **Idempotency**: Consider idempotency for commands that may be retried

### REST API Endpoints
- **HTTP Method**: POST (all commands change state)
- **Endpoint Pattern**: `POST /api/{{bc_name}}/{{command-name}}`
- **Request Mapping**: Map request body to command DTO using `inputSchema`
- **Response Codes**:
  - `201 Created` for Create commands
  - `200 OK` for Update/Process commands
  - `204 No Content` for Delete commands
  - `400 Bad Request` for validation errors
  - `403 Forbidden` for authorization failures

## Event Implementation

### Event Class
- **Naming**: Use past tense (OrderCreated, PaymentProcessed, UserRegistered)
- **Schema**: Use the provided `schema` to define event classes
- **Properties**: Map all properties from spec to event fields
- **Immutability**: Events are immutable once emitted
- **Versioning**: Use semantic versioning for event schema evolution
- **Metadata**: Include eventId, timestamp, version, etc.

### Event Publishing
- **Publisher**: Use event publisher service in `infrastructure/messaging/`
- **Platform**: Publish to {messaging_platform} after successful command execution
- **Async**: Publish asynchronously to avoid blocking command execution
- **Versioning**: Include event version in message headers/topic
- **Error Handling**: Handle publishing failures (retry, dead-letter queue)
- **Event Schema**: Use semantic versioning for event schema evolution
- **Metadata**: Include eventId, timestamp, version, etc.

### Event Consumption (Policies)
- **Subscription**: Subscribe to events via {messaging_platform} consumer
- **Cross-BC Events**: Handle events from other BCs (deserialize using other BC event schemas)
- **Idempotency**: Implement idempotency checks for duplicate events
- **Error Handling**: Handle consumption failures gracefully
- **Event Contracts**: Maintain backward compatibility for events

## Aggregate Implementation

- **Root Entity**: Use the `rootEntity` as the aggregate root class
- **Invariants**: Enforce all listed invariants in aggregate methods
- **Properties**: Map all properties with correct types (use `isKey` for primary keys, `isForeignKey` for references)
- **Enumerations**: Use provided enumerations for state management
- **Value Objects**: Implement value objects for complex domain concepts

## ReadModel Implementation

### ReadModel Projection
- **CQRS Pattern**: ReadModels are updated via event projections
- **Projection Handler**: Implement event projection handlers in `domain/readmodels/`
- **Actor Support**: Filter/authorize based on `actor` field
- **Denormalization**: Denormalize data for query performance
- **Eventual Consistency**: Accept eventual consistency (ReadModels may be slightly stale)

### Query API Endpoints
- **HTTP Method**: GET (queries don't change state)
- **Endpoint Patterns**:
  - Single result: `GET /api/{{bc_name}}/{{readmodel-name}}/{{id}}`
  - List: `GET /api/{{bc_name}}/{{readmodel-name}}?filter=value&page=1&size=10`
  - Collection: `GET /api/{{bc_name}}/{{readmodel-name}}`
- **Return Types** (based on `isMultipleResult`):
  - `list`: Return ordered arrays
  - `collection`: Return unordered collections
  - `single result`: Return single objects
- **Features**: Support filtering, pagination, and sorting for list/collection types

## Policy Implementation

### Event Listener
- **Subscription**: Subscribe to trigger events via {config.messaging.value} consumer
- **Cross-BC Events**: Handle events from other BCs (deserialize using other BC event schemas)
- **Idempotency**: Implement idempotency checks to handle duplicate events

### Command Invocation
- **Async Invocation**: Invoke target commands asynchronously via {messaging_platform}
- **Cross-BC Commands**: Handle command invocation in different BCs
- **Data Mapping**: Map event data to command input using event/command schemas
- **Retry Logic**: Implement retry logic for failed invocations

## UI Wireframe Implementation

### UI Components
- **Attached to Command**: Create form components for command execution
- **Attached to ReadModel**: Create display/list components for query results
- **Wireframe Description**: Follow wireframe descriptions from BC specs
- **API Integration**: Connect UI to backend APIs (Command POST, ReadModel GET)
- **State Management**: Use framework-specific state management (Pinia, Redux, etc.)
- **Error Handling**: Display user-friendly error messages
- **Loading States**: Show loading indicators during API calls

### Complete UI Implementation Checklist

**For EACH Command in BC spec:**
- [ ] **Create UI Button/Form** - Every Command MUST have a UI element
- [ ] **Create API Service** - Service method for `POST /api/{{bc_name}}/{{command-name}}`
- [ ] **Connect UI to API** - Button/form MUST call API service
- [ ] **Handle Response** - Show success/error, update UI state
- [ ] **Validate Input** - Client-side validation
- [ ] **Loading State** - Show loading during API call

**For EACH ReadModel in BC spec:**
- [ ] **Create Display/List Page** - Every ReadModel MUST have a page
- [ ] **Create API Service** - Service method for `GET /api/{{bc_name}}/{{readmodel-name}}`
- [ ] **Connect Page to API** - Page load MUST call API service
- [ ] **Display Data** - Show ReadModel data in UI
- [ ] **Pagination** - If isMultipleResult: 'list', implement pagination

**For EACH UI Wireframe in BC spec:**
- [ ] **Read Template** - HTML template from BC spec
- [ ] **Create Component** - Implement as Vue/React component
- [ ] **Match Structure** - Follow wireframe template structure
- [ ] **Connect to Command/ReadModel** - Wireframe attached to Command → form, ReadModel → display

**CRITICAL**: 100% Coverage Required - Every Command, ReadModel, and UI Wireframe MUST be implemented.

## Related Rules

- **DDD Principles**: `@ddd-principles` - DDD patterns and BC boundaries
- **GWT Test Generation**: `@gwt-test-generation` - Test patterns for implementations
- **Tech Stack Rules**: `@{config.framework.value}` - Framework-specific implementation patterns
"""


def _get_database_specific_guidelines(database: str) -> str:
    """Generate database-specific implementation guidelines."""
    if database == "postgresql":
        return """
- **PostgreSQL Specific**:
  - Use `SERIAL` or `BIGSERIAL` for auto-increment IDs, or `UUID` for distributed systems
  - Use `JSONB` for flexible schema (if needed for event storage or denormalized data)
  - Use `VARCHAR` with appropriate length limits
  - Use `TIMESTAMP WITH TIME ZONE` for timestamps
  - Create indexes on foreign keys and frequently queried columns
  - Use `EXPLAIN ANALYZE` to optimize queries
  - Consider using `PARTITION BY` for large tables (if applicable)
  - Use connection pooling (HikariCP for Java, asyncpg for Python, etc.)"""
    
    elif database == "mysql":
        return """
- **MySQL Specific**:
  - Use `InnoDB` storage engine (supports transactions and foreign keys)
  - Use `AUTO_INCREMENT` for primary keys, or `CHAR(36)` for UUIDs
  - Use `VARCHAR` with appropriate length limits
  - Use `DATETIME` or `TIMESTAMP` for timestamps
  - Create indexes on foreign keys and frequently queried columns
  - Use `utf8mb4` character set for full Unicode support
  - Use connection pooling (HikariCP for Java, SQLAlchemy for Python, etc.)
  - Consider using `EXPLAIN` to optimize queries"""
    
    elif database == "mongodb":
        return """
- **MongoDB Specific**:
  - Use `ObjectId` for document IDs (or UUIDs if needed)
  - Design document structure to match query patterns (denormalize for reads)
  - Create indexes on frequently queried fields
  - Use compound indexes for multi-field queries
  - Use `$lookup` sparingly (prefer denormalization for performance)
  - Use transactions for multi-document operations (MongoDB 4.0+)
  - Use connection pooling (MongoDB driver connection pool)
  - Consider using `explain()` to optimize queries"""
    
    elif database == "h2":
        return """
- **H2 Specific**:
  - Use `BIGINT AUTO_INCREMENT` for primary keys, or `CHAR(36)` for UUIDs
  - Use `VARCHAR` with appropriate length limits
  - Use `TIMESTAMP` for timestamps
  - Create indexes on foreign keys and frequently queried columns
  - Use in-memory mode (`jdbc:h2:mem:`) for testing
  - Use file-based mode (`jdbc:h2:file:`) for development
  - H2 is typically used for development/testing, not production"""
    
    else:
        return f"""
- **{database} Specific**:
  - Follow {database} best practices for your use case
  - Implement proper indexing strategy
  - Use appropriate data types for your domain
  - Configure connection pooling appropriately"""


def _get_frontend_implementation_guidelines(config: TechStackConfig) -> str:
    """Generate frontend framework specific implementation guidelines."""
    frontend_fw = config.frontend_framework.value if config.frontend_framework else ""
    
    if frontend_fw == "vue":
        return """### Vue.js 3 Specific Guidelines

#### Components
- Use `<script setup>` syntax for Composition API
- Use `defineProps` and `defineEmits` for component interface
- Use `ref` and `reactive` for reactive state
- Use `computed` for derived state
- Use `watch` for side effects

#### Views/Pages
- Use Vue Router for navigation
- Use route params and query for data fetching
- Implement loading states with `v-if` and loading indicators
- Handle errors with try-catch and error components

#### State Management (Pinia)
- Create stores in `stores/` directory
- Use `defineStore` for store definition
- Separate stores by feature/BC
- Use `getters` for computed state
- Use `actions` for async operations (API calls)

#### API Services
- Create service files in `services/` directory
- Use `fetch` or `axios` for HTTP requests
- Handle errors and return typed responses
- Use async/await for async operations

#### Forms
- Use `v-model` for two-way binding
- Validate with `vuelidate` or custom validators
- Show validation errors inline
- Disable submit button during submission

#### Testing
- Use Vitest for unit tests
- Use Vue Test Utils for component testing
- Mock API calls in tests"""
    
    elif frontend_fw == "react":
        return """### React Specific Guidelines

#### Components
- Use functional components with hooks
- Use `useState` for local state
- Use `useEffect` for side effects
- Use `useMemo` and `useCallback` for optimization
- Use TypeScript for type safety

#### Views/Pages
- Use React Router for navigation
- Use route params and search params
- Implement loading states with conditional rendering
- Handle errors with Error Boundaries

#### State Management
- Use Context API for global state (small apps)
- Use Redux Toolkit or Zustand for complex state
- Separate stores by feature/BC
- Use selectors for computed state
- Use thunks/sagas for async operations

#### API Services
- Create service files in `services/` directory
- Use `fetch` or `axios` for HTTP requests
- Use custom hooks (e.g., `useApi`) for data fetching
- Handle errors and return typed responses

#### Forms
- Use controlled components with `value` and `onChange`
- Use `react-hook-form` for form management
- Validate with `zod` or `yup`
- Show validation errors inline

#### Testing
- Use Jest and React Testing Library
- Mock API calls with MSW (Mock Service Worker)
- Test user interactions, not implementation"""
    
    else:
        return f"""### {frontend_fw} Specific Guidelines

#### Components
- Follow {frontend_fw} component patterns
- Use framework-specific state management
- Implement proper lifecycle hooks

#### API Integration
- Create service layer for API calls
- Handle errors and loading states
- Use framework-specific HTTP client

#### Forms
- Use framework-specific form handling
- Validate inputs
- Show validation errors

#### Testing
- Use framework-specific testing tools
- Test components and integration"""


def generate_dockerfile(config: TechStackConfig) -> str:
    if config.framework == Framework.FASTAPI:
        return """FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
"""
    if config.framework in [Framework.NESTJS, Framework.EXPRESS]:
        return """FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
CMD ["npm","run","start"]
"""
    return """# Dockerfile template (customize per service)
"""


def generate_docker_compose(config: TechStackConfig) -> str:
    # Database service
    if config.database == Database.POSTGRESQL:
        db_service = """  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: ${DB_NAME:-app}
      POSTGRES_USER: ${DB_USER:-postgres}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-postgres}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
"""
    elif config.database == Database.MONGODB:
        db_service = """  mongodb:
    image: mongo:6
    ports:
      - "27017:27017"
    volumes:
      - mongodb_data:/data/db
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
      interval: 10s
      timeout: 5s
      retries: 5
"""
    elif config.database == Database.MYSQL:
        db_service = """  mysql:
    image: mysql:8
    environment:
      MYSQL_DATABASE: ${DB_NAME:-app}
      MYSQL_USER: ${DB_USER:-mysql}
      MYSQL_PASSWORD: ${DB_PASSWORD:-mysql}
      MYSQL_ROOT_PASSWORD: ${DB_ROOT_PASSWORD:-root}
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 5
"""
    else:
        db_service = ""

    # Messaging service
    if config.messaging.value == "kafka":
        messaging_service = """  zookeeper:
    image: confluentinc/cp-zookeeper:latest
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000
    ports:
      - "2181:2181"
    healthcheck:
      test: ["CMD", "nc", "-z", "localhost", "2181"]
      interval: 10s
      timeout: 5s
      retries: 5

  kafka:
    image: confluentinc/cp-kafka:latest
    depends_on:
      - zookeeper
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "true"
    ports:
      - "9092:9092"
    healthcheck:
      test: ["CMD", "kafka-broker-api-versions", "--bootstrap-server", "localhost:9092"]
      interval: 10s
      timeout: 5s
      retries: 5
"""
    elif config.messaging.value == "rabbitmq":
        messaging_service = """  rabbitmq:
    image: rabbitmq:3-management
    environment:
      RABBITMQ_DEFAULT_USER: ${RABBITMQ_USER:-guest}
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD:-guest}
    ports:
      - "5672:5672"   # AMQP port
      - "15672:15672" # Management UI
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
"""
    elif config.messaging.value == "redis-streams":
        messaging_service = """  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
"""
    else:
        messaging_service = ""

    volumes = ""
    if config.database in [Database.POSTGRESQL, Database.MONGODB, Database.MYSQL]:
        volumes += "\nvolumes:"
        if config.database == Database.POSTGRESQL:
            volumes += "\n  postgres_data:"
        elif config.database == Database.MONGODB:
            volumes += "\n  mongodb_data:"
        elif config.database == Database.MYSQL:
            volumes += "\n  mysql_data:"
    if config.messaging.value == "rabbitmq":
        if not volumes:
            volumes = "\nvolumes:"
        volumes += "\n  rabbitmq_data:"
    if config.messaging.value == "redis-streams":
        if not volumes:
            volumes = "\nvolumes:"
        volumes += "\n  redis_data:"

    # Modern Docker Compose V2 format (no version field needed)
    return f"""services:
{db_service}{messaging_service}{volumes}
"""


