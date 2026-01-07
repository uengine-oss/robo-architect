"""
LLM Prompts for Event Storming Workflow

These prompts guide the LLM to generate Event Storming artifacts
from User Stories in a structured, domain-driven design approach.
"""

# =============================================================================
# System Prompts
# =============================================================================

SYSTEM_PROMPT = """You are an expert Domain-Driven Design (DDD) consultant specializing in Event Storming.
Your role is to help decompose software requirements into:
- Bounded Contexts (BC): Strategic design boundaries
- Aggregates: Tactical design units with transaction consistency
- Commands: Actions that change state
- Events: Facts that happened (past tense)
- Policies: Reactions to events that trigger commands

Follow these principles:
1. Each Bounded Context should have a single, cohesive purpose
2. Aggregates enforce business invariants within a BC
3. Commands represent user intentions (verb form: CreateOrder)
4. Events represent completed actions (past tense: OrderCreated)
5. Policies connect BCs via event-driven communication

When identifying Bounded Contexts, consider:
- Domain expertise differences (different teams, different knowledge)
- Scaling requirements (different load patterns)
- Data ownership (who owns what data)
- Business capability boundaries

Use consistent naming conventions:
IMPORTANT (IDs):
- Do NOT invent or format IDs (no BC-/AGG-/CMD-/EVT-/POL- prefixes).
- The server will assign UUID `id` and derive a natural `key` from names.
- Your job is to propose good names + descriptions + traceability lists.
"""

# =============================================================================
# Bounded Context Identification
# =============================================================================

IDENTIFY_BC_PROMPT = """Analyze the following User Story and identify which Bounded Context(s) it belongs to.

User Story:
{user_story}

Existing Bounded Contexts in the system:
{existing_bcs}

Guidelines:
1. If the user story fits an existing BC, assign it there
2. If it requires a new BC, propose one with clear rationale
3. Consider if the story crosses multiple BCs (rare, but possible)
4. Don't create too many BCs - group related functionality

A user story typically belongs to ONE primary Bounded Context.
Consider the domain expertise, data ownership, and business capability.

Respond with:
1. The recommended Bounded Context (existing or new)
2. Your rationale for this assignment
3. Any concerns or alternatives to consider"""

IDENTIFY_BC_FROM_STORIES_PROMPT = """Analyze the following User Stories and identify candidate Bounded Contexts.

User Stories:
{user_stories}

Guidelines for identifying Bounded Contexts:
1. Group related functionality that shares domain concepts
2. Consider organizational boundaries (different teams)
3. Consider scaling requirements (different load patterns)
4. Consider data ownership (who owns what data)
5. Don't create too fine-grained BCs - they become microservices later

For each Bounded Context candidate, provide:
- A descriptive name
- What it's responsible for
- Which user stories belong to it
- Rationale for why it should be separate

Output should be a list of BoundedContextCandidate objects."""

# =============================================================================
# User Story Breakdown
# =============================================================================

BREAKDOWN_USER_STORY_PROMPT = """Break down the following User Story into detailed components for Event Storming.

User Story:
{user_story}

Bounded Context: {bc_name}

Analyze this user story and identify:
1. Sub-tasks: What specific steps are needed to fulfill this story?
2. Domain Concepts: What key entities/concepts are involved?
3. Potential Aggregates: What consistency boundaries exist?
4. Potential Commands: What actions can users take?

Be specific and domain-focused. Think about:
- What data needs to be managed together (aggregate roots)
- What invariants must be maintained
- What events would be published when actions complete

Output should be a UserStoryBreakdown object."""

# =============================================================================
# Aggregate Extraction
# =============================================================================

EXTRACT_AGGREGATES_PROMPT = """Based on the User Story breakdown, identify Aggregates for this Bounded Context.

Bounded Context: {bc_name} (ID: {bc_id})
Description: {bc_description}

User Story Breakdowns (ONLY for this BC):
{breakdowns}

CRITICAL RULES:
1. An Aggregate belongs to EXACTLY ONE Bounded Context - never shared across BCs
2. Only consider the user stories listed above (which belong to THIS BC only)
3. If similar concepts exist in other BCs, they are DIFFERENT aggregates (modeled independently per BC)
4. Do NOT generate IDs; server assigns UUID id + derives key.

Guidelines for identifying Aggregates:
1. An Aggregate is a cluster of domain objects treated as a single unit
2. One entity is the Aggregate Root (entry point for all operations)
3. Aggregates enforce consistency boundaries (transactions)
4. Invariants (business rules) are checked within an aggregate
5. Other aggregates (even in other BCs) are referenced by ID only

For each Aggregate, provide:
- The aggregate name (unique within this BC)
- The root entity name
- Key invariants it enforces
- A description of what it manages
- user_story_ids: List of User Story IDs that this aggregate implements (IMPORTANT for traceability!)

Example for Order BC:
- Cart: Shopping cart management, implements [US-001]
- Order: Order lifecycle management, implements [US-001, US-002, US-003]

Example for Inventory BC:
- Stock: Stock level management, implements [US-009, US-010]

IMPORTANT: Each aggregate must list which user stories from this BC it implements.
This creates traceability from requirements to implementation.

Output should be a list of AggregateCandidate objects."""

# =============================================================================
# Command Extraction
# =============================================================================

EXTRACT_COMMANDS_PROMPT = """Identify Commands for the given Aggregate based on user story requirements.

Aggregate: {aggregate_name}
Aggregate ID: {aggregate_id}
Bounded Context: {bc_name}

User Stories for this Aggregate:
{user_story_context}

Guidelines for identifying Commands:
1. Commands represent user/system intentions to change state
2. Name commands as imperative verbs (CreateOrder, CancelOrder)
3. Each command should map to a user action or system trigger
4. Commands are handled by exactly one aggregate
5. IMPORTANT: Track which user story each command implements

For each Command, provide:
- The command name in PascalCase
- Who/what triggers this command (user, system, policy)
- A description of what the command does
- user_story_ids: List of User Story IDs that this command directly implements

Example:
- PlaceOrder: implements [US-001]
- CancelOrder: implements [US-002]

This creates traceability: UserStory -> Command

Output should be a list of CommandCandidate objects."""

# =============================================================================
# Event Extraction
# =============================================================================

EXTRACT_EVENTS_PROMPT = """Identify Events emitted by Commands in this Aggregate.

Aggregate: {aggregate_name}
Bounded Context: {bc_name}
Commands (with their user stories):
{commands}

Guidelines for identifying Events:
1. Events represent facts that happened (past tense)
2. Name events as NounPastVerb (OrderCreated, PaymentProcessed)
3. Every command should emit at least one event on success
4. Events are immutable facts - they cannot be changed
5. IMPORTANT: Inherit user_story_ids from the command that emits this event

For each Event, provide:
- The event name in PascalCase
- A description of what happened
- user_story_ids: List of User Story IDs (inherited from the emitting command)

Example:
- OrderPlaced: implements [US-001]
- OrderCancelled: implements [US-002]

This creates traceability: UserStory -> Command -> Event

Output should be a list of EventCandidate objects."""

# =============================================================================
# ReadModel Extraction
# =============================================================================

EXTRACT_READMODELS_PROMPT = """Identify ReadModels (query/projection models) for the given Bounded Context.

Bounded Context: {bc_name} (ID: {bc_id})
Description: {bc_description}

User Stories for this Bounded Context:
{user_stories}

Available Events in this Bounded Context (for projection updates):
{events}

CRITICAL RULES:
1. ReadModels are for QUERY intent only (read/search/list/detail/status). Do NOT create ReadModels for commands that change state.
2. Naming: PascalCase using **Noun + Purpose**. Examples: OrderSummary, OrderStatus, ProductCatalog, InventorySnapshot.
3. Keep it minimal: prefer 0~3 ReadModels per Bounded Context for the first iteration.
4. Each ReadModel MUST list which user stories it supports via user_story_ids (traceability).
5. provisioningType is fixed to CQRS (you do NOT need to output provisioningType).

If there are no query-type user stories, return an empty list.

Output should be a list of ReadModelCandidate objects."""

# =============================================================================
# Property Generation (Phase 1)
# =============================================================================

GENERATE_PROPERTIES_AGGREGATE_BATCH_PROMPT = """You will generate domain-meaningful Properties (fields) for Event Storming nodes.

Targets:
- Aggregate, Command, Event (for ONE Aggregate scope)

You are given:
1) Bounded Context info
2) Aggregate info (id + key are canonical from DB)
3) Commands and Events under that Aggregate (id + key are canonical from DB)
4) A list of known Aggregate keys in the whole system (optional hint list for FK targets)

CRITICAL RULES (STRICT):
1) Only output domain-meaningful fields. DO NOT spam generic/system fields (createdAt, updatedAt, version, deleted, tenantId, etc.) unless absolutely domain-required.
2) Property `name` MUST be camelCase. Identifiers MUST be exactly `id` or end with `Id` (e.g., orderId, customerId).
3) `type` MUST be a Java type string. Use: String, UUID, int, long, boolean, BigDecimal, LocalDateTime, LocalDate, List<T>.
4) Every Property MUST include: name, type, description, isKey, isForeignKey, isRequired.
5) `isForeignKey` is your decision (do not apply simple automatic rules). If isForeignKey=true, provide fkTargetHint whenever reasonably confident.
6) fkTargetHint format (if provided): `<TargetType>:<TargetKey>:<TargetPropertyName>`
   - TargetType is one of: Aggregate|ReadModel|Event|Command
   - TargetKey is the Neo4j natural key of the target node
   - TargetPropertyName should typically be `id` (or another isKey field if explicit)
7) Output properties grouped by parent using PropertyBatch schema:
   - parentType must be one of Aggregate|Command|Event
   - parentKey MUST match one of the provided keys for this scope
8) Keep the list compact but complete enough to build a usable first draft.

Bounded Context:
- id: {bc_id}
- key: {bc_key}
- name: {bc_name}
- description: {bc_description}

Aggregate (parentType=Aggregate):
- id: {aggregate_id}
- key: {aggregate_key}
- name: {aggregate_name}
- rootEntity: {aggregate_root_entity}
- invariants: {aggregate_invariants}
- description: {aggregate_description}

Commands (parentType=Command):
{commands}

Events (parentType=Event):
{events}

Known Aggregate keys (FK target hints; optional):
{known_aggregate_keys}

Return ONLY a PropertyBatch object."""


GENERATE_PROPERTIES_READMODELS_BATCH_PROMPT = """You will generate domain-meaningful Properties (fields) for ReadModels (query/projection models).

Targets:
- ReadModel(s) for ONE Bounded Context

CRITICAL RULES (STRICT):
1) Only output domain-meaningful query columns. Avoid generic/system fields unless truly needed.
2) Property `name` MUST be camelCase. Identifiers MUST be exactly `id` or end with `Id`.
3) `type` MUST be a Java type string. Use: String, UUID, int, long, boolean, BigDecimal, LocalDateTime, LocalDate, List<T>.
4) Every Property MUST include: name, type, description, isKey, isForeignKey, isRequired.
5) `isForeignKey` is your decision. If isForeignKey=true, provide fkTargetHint whenever reasonably confident.
6) fkTargetHint format (if provided): `<TargetType>:<TargetKey>:<TargetPropertyName>`
7) Output properties grouped by parent using PropertyBatch schema:
   - parentType MUST be ReadModel
   - parentKey MUST match one of the provided readmodel keys
8) ReadModels are for QUERY. Prefer denormalized columns that support the user stories.

Bounded Context:
- id: {bc_id}
- key: {bc_key}
- name: {bc_name}
- description: {bc_description}

ReadModels (parentType=ReadModel):
{readmodels}

Known Aggregate keys (FK target hints; optional):
{known_aggregate_keys}

Return ONLY a PropertyBatch object."""

# =============================================================================
# Policy Identification
# =============================================================================

IDENTIFY_POLICIES_PROMPT = """Identify Policies for cross-Bounded Context communication.

User Stories in the system:
{user_stories}

Available Events (with source BC and related user stories):
{events}

Available Commands in each BC:
{commands_by_bc}

Bounded Contexts:
{bounded_contexts}

Guidelines for identifying Policies:
1. Policies react to Events from OTHER Bounded Contexts (cross-BC only)
2. A Policy triggers a Command in its OWN Bounded Context
3. Pattern: "When [Event from BC-A] then [Command in BC-B]"
4. Policies enable loose coupling between BCs
5. IMPORTANT: The trigger_event_bc MUST be different from target_bc (cross-BC communication)
6. IMPORTANT: Inherit user_story_ids from the triggering event for traceability

For each Policy, provide:
- name: Descriptive policy name (e.g., RefundOnOrderCancelled)
- trigger_event: Event name that triggers this policy
- trigger_event_bc: BC where the trigger event originates (MUST be different from target_bc)
- target_bc: BC where this policy lives
- invoke_command: Command this policy invokes (in target_bc)
- description: "When X then Y" format
- user_story_ids: User Story IDs related to this policy (inherited from trigger event)

Common patterns:
- When OrderPlaced (Order BC) → ProcessPayment (Payment BC), user_story_ids from OrderPlaced
- When OrderCancelled (Order BC) → ProcessRefund (Payment BC), user_story_ids from OrderCancelled
- When OrderCancelled (Order BC) → RestoreStock (Inventory BC), user_story_ids from OrderCancelled

This creates traceability: UserStory → Command → Event → Policy → Command

Output should be a list of PolicyCandidate objects."""

# =============================================================================
# Review Prompts
# =============================================================================

REVIEW_BC_PROMPT = """Review the proposed Bounded Contexts for this Event Storming session.

Proposed Bounded Contexts:
{bc_candidates}

Original User Stories:
{user_stories}

Please review and provide feedback:
1. Are the BC boundaries appropriate?
2. Are any BCs too large (should be split)?
3. Are any BCs too small (should be merged)?
4. Are user stories correctly assigned?

If approved, respond with "APPROVED".
If changes needed, describe the changes."""

REVIEW_AGGREGATES_PROMPT = """Review the proposed Aggregates for Bounded Context: {bc_name}

Proposed Aggregates:
{aggregates}

Please review and provide feedback:
1. Are aggregate boundaries correct?
2. Are invariants properly identified?
3. Should any aggregates be merged or split?

If approved, respond with "APPROVED".
If changes needed, describe the changes."""

REVIEW_POLICIES_PROMPT = """Review the proposed Policies for cross-BC communication.

Proposed Policies:
{policies}

Please review and provide feedback:
1. Are the event-to-command mappings correct?
2. Are there missing policies?
3. Are there unnecessary policies?

If approved, respond with "APPROVED".
If changes needed, describe the changes."""

