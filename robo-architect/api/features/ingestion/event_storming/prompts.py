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
- BC IDs: BC-NAME (e.g., BC-ORDER, BC-PAYMENT)
- Aggregate IDs: AGG-NAME (e.g., AGG-ORDER)
- Command IDs: CMD-VERB-NOUN (e.g., CMD-CANCEL-ORDER)
- Event IDs: EVT-NOUN-PASTVERB (e.g., EVT-ORDER-CANCELLED)
- Policy IDs: POL-ACTION-ON-TRIGGER (e.g., POL-REFUND-ON-CANCEL)
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
- A unique ID (BC-NAME, e.g., BC-ORDER)
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
3. If similar concepts exist in other BCs, they are DIFFERENT aggregates with DIFFERENT IDs
4. Aggregate IDs MUST include the BC name for uniqueness (e.g., AGG-{bc_id_short}-ORDER)

Guidelines for identifying Aggregates:
1. An Aggregate is a cluster of domain objects treated as a single unit
2. One entity is the Aggregate Root (entry point for all operations)
3. Aggregates enforce consistency boundaries (transactions)
4. Invariants (business rules) are checked within an aggregate
5. Other aggregates (even in other BCs) are referenced by ID only

For each Aggregate, provide:
- A unique ID: AGG-{bc_id_short}-NAME (e.g., AGG-ORDER-CART, AGG-INVENTORY-STOCK)
- The aggregate name (unique within this BC)
- The root entity name
- Key invariants it enforces
- A description of what it manages
- user_story_ids: List of User Story IDs that this aggregate implements (IMPORTANT for traceability!)

Example for Order BC:
- AGG-ORDER-CART: Shopping cart management, implements [US-001]
- AGG-ORDER-ORDER: Order lifecycle management, implements [US-001, US-002, US-003]

Example for Inventory BC:
- AGG-INVENTORY-STOCK: Stock level management, implements [US-009, US-010]

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
- A unique ID: CMD-BCNAME-VERB-NOUN (e.g., CMD-ORDER-CANCEL-ORDER)
- The command name in PascalCase
- Who/what triggers this command (user, system, policy)
- A description of what the command does
- user_story_ids: List of User Story IDs that this command directly implements

Example:
- CMD-ORDER-PLACE-ORDER: PlaceOrder, implements [US-001]
- CMD-ORDER-CANCEL-ORDER: CancelOrder, implements [US-002]

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
- A unique ID: EVT-BCNAME-NOUN-PASTVERB (e.g., EVT-ORDER-ORDER-CANCELLED)
- The event name in PascalCase
- A description of what happened
- user_story_ids: List of User Story IDs (inherited from the emitting command)

Example:
- EVT-ORDER-ORDER-PLACED: OrderPlaced, implements [US-001]
- EVT-ORDER-ORDER-CANCELLED: OrderCancelled, implements [US-002]

This creates traceability: UserStory -> Command -> Event

Output should be a list of EventCandidate objects."""

# =============================================================================
# Policy Identification
# =============================================================================

IDENTIFY_POLICIES_PROMPT = """Identify Policies for cross-Bounded Context communication.

Available Events in the system:
{events}

Available Commands in each BC:
{commands_by_bc}

Bounded Contexts:
{bounded_contexts}

Guidelines for identifying Policies:
1. Policies react to Events from OTHER Bounded Contexts
2. A Policy triggers a Command in its OWN Bounded Context
3. Pattern: "When [Event] then [Command]"
4. Policies enable loose coupling between BCs

For each Policy, provide:
- A unique ID (POL-ACTION-ON-TRIGGER, e.g., POL-REFUND-ON-CANCEL)
- A descriptive name
- The triggering event (from another BC)
- The target BC where this policy lives
- The command it invokes (in the same BC as the policy)
- A description in "When X then Y" format

Common patterns:
- When OrderPlaced → ProcessPayment (Payment BC)
- When OrderCancelled → ProcessRefund (Payment BC)
- When OrderCancelled → RestoreStock (Inventory BC)

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

