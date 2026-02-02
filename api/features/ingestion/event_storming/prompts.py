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

IDENTIFY_BC_FROM_STORIES_PROMPT = """Analyze the following User Stories and identify candidate Bounded Contexts following Domain-Driven Design principles.

User Stories:
{user_stories}

<core_instructions>
<title>Bounded Context Division Task</title>
<task_description>Your task is to analyze the provided User Stories and divide them into multiple Bounded Contexts following Domain-Driven Design principles. You will identify natural boundaries within the business domain and create cohesive, loosely-coupled bounded contexts that align with organizational structure and business capabilities.</task_description>

<guidelines>
<title>Bounded Context Division Guidelines</title>

<section id="core_principles">
<title>Core Principles</title>
<rule id="1">**High Cohesion, Low Coupling:** Group related behaviors and data together while minimizing inter-context dependencies</rule>
<rule id="2">**Event Action Range:** Consider event's action range to create bounded context boundaries</rule>
<rule id="3">**Event Flow:** Consider relationships between events to create flow</rule>
<rule id="4">**Actor Grouping:** Consider which actors (roles) are responsible for which user stories</rule>
<rule id="5">**Business Capability Alignment:** Ensure bounded contexts align with business capabilities</rule>
<rule id="6">**User Story Grouping:** Group user stories that share domain concepts, data ownership, and business processes</rule>
</section>

<section id="domain_classification">
<title>Domain Classification Strategy</title>

<core_domain>
<title>Core Domain</title>
<characteristics>
<item>Direct impact on business competitive advantage</item>
<item>User-facing functionality</item>
<item>Strategic importance to business goals</item>
<item>Unique business logic that differentiates the company</item>
</characteristics>
<examples>
<item>Order management in e-commerce</item>
<item>Product recommendation engine</item>
<item>Customer loyalty program</item>
</examples>
</core_domain>

<supporting_domain>
<title>Supporting Domain</title>
<characteristics>
<item>Enables core domain functionality</item>
<item>Internal business processes</item>
<item>Medium business impact</item>
<item>Important but not differentiating</item>
</characteristics>
<examples>
<item>Inventory management</item>
<item>Shipping and logistics</item>
<item>Customer support ticketing</item>
</examples>
</supporting_domain>

<generic_domain>
<title>Generic Domain</title>
<characteristics>
<item>Common functionality across industries</item>
<item>Can be replaced by third-party solutions</item>
<item>Low differentiation but can have high complexity</item>
<item>Standard business processes</item>
</characteristics>
<examples>
<item>User authentication and authorization</item>
<item>Payment processing</item>
<item>Email notifications</item>
</examples>
</generic_domain>
</section>

<section id="identification_rules">
<title>Bounded Context Identification Rules</title>
<rule id="1">**Group Related User Stories:** User stories that share domain concepts, actors, or business processes should be in the same BC</rule>
<rule id="2">**Consider Organizational Boundaries:** If different teams would own different parts, consider separate BCs</rule>
<rule id="3">**Consider Scaling Requirements:** If different parts have different load patterns, consider separate BCs</rule>
<rule id="4">**Consider Data Ownership:** If different parts own different data, consider separate BCs</rule>
<rule id="5">**Avoid Over-Granularity:** Don't create too many fine-grained BCs - they become microservices later</rule>
<rule id="6">**Avoid Under-Granularity:** Don't create too few BCs - each should have a clear, cohesive purpose</rule>
<rule id="7">**User Story Assignment:** Each user story should belong to exactly ONE primary Bounded Context</rule>
</section>

<section id="output_requirements">
<title>Output Requirements</title>
<requirement id="1">**Bounded Context Name:** Must be in English PascalCase (e.g., "OrderManagement", "PaymentProcessing")</requirement>
<requirement id="2">**Description:** Clear explanation of what this BC is responsible for</requirement>
<requirement id="3">**Rationale:** Detailed explanation of why this should be a separate BC, considering cohesion, coupling, and domain boundaries</requirement>
<requirement id="4">**User Story Assignment:** List all user story IDs that belong to this BC</requirement>
<requirement id="5">**Domain Classification:** MUST classify each BC as Core Domain, Supporting Domain, or Generic Domain. This classification is required for proper domain modeling and strategic design decisions.</requirement>
</section>
</guidelines>
</core_instructions>

<analysis_approach>
Consider the following when analyzing:
1. **Domain Concepts:** What key business concepts are mentioned across user stories?
2. **Actor Patterns:** Which actors (roles) appear together in related stories?
3. **Business Processes:** What business processes or workflows are described?
4. **Data Ownership:** What data would each BC own and manage?
5. **Integration Points:** Where would BCs need to communicate with each other?

Think about:
- Which user stories naturally belong together?
- What would be the boundaries between different BCs?
- How would BCs interact (event-driven, request/response, etc.)?
</analysis_approach>

For each Bounded Context candidate, provide:
- **name:** Descriptive name in PascalCase
- **description:** What this BC is responsible for
- **rationale:** Why this should be a separate BC (consider cohesion, coupling, domain boundaries)
- **user_story_ids:** List of User Story IDs that belong to this BC
- **domain_type:** MUST be one of: "Core Domain", "Supporting Domain", or "Generic Domain". This field is required and must be provided for each BC.

Output should be a list of BoundedContextCandidate objects with clear, well-reasoned boundaries."""

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

EXTRACT_AGGREGATES_PROMPT = """You are tasked with identifying Aggregates within a specified Bounded Context based on User Story breakdowns, following Domain-Driven Design principles.

<target_bounded_context>
Name: {bc_name}
ID: {bc_id}
Description: {bc_description}
</target_bounded_context>

<user_story_breakdowns>
{breakdowns}
</user_story_breakdowns>

<existing_aggregates_in_other_bcs>
{existing_aggregates}
</existing_aggregates_in_other_bcs>

<core_instructions>
<title>Aggregate Identification Task</title>
<task_description>Analyze the User Story breakdowns and identify Aggregates that enforce business invariants and maintain transactional consistency within this Bounded Context. Each Aggregate should be a cluster of domain objects treated as a single unit with clear boundaries.</task_description>

<guidelines>
<title>Aggregate Identification Guidelines</title>

<section id="core_principles">
<title>Core Principles</title>
<rule id="1">**Transactional Consistency:** Consolidate transaction-critical data within a single Aggregate to preserve atomicity. Avoid splitting core transactional data (e.g., do not separate order/order items or loan/loan details).</rule>
<rule id="2">**Consistency Boundaries:** Aggregates enforce consistency boundaries (transactions). All invariants (business rules) are checked within an aggregate.</rule>
<rule id="3">**Single Bounded Context:** An Aggregate belongs to EXACTLY ONE Bounded Context - never shared across BCs. If similar concepts exist in other BCs, they are DIFFERENT aggregates (modeled independently per BC).</rule>
<rule id="4">**Aggregate Root:** One entity is the Aggregate Root (entry point for all operations). All external access to the aggregate must go through the root.</rule>
<rule id="5">**Reference by ID:** Other aggregates (even in other BCs) are referenced by ID only, not by direct object references.</rule>
</section>

<section id="aggregate_structure">
<title>Aggregate Structure Requirements</title>
<rule id="1">**Enumerations:** When storing state or similar information, always use Enumerations. Ensure that all Enumerations are directly associated with the Aggregate.</rule>
<rule id="2">**Value Objects:** Distribute properties across well-defined Value Objects to improve maintainability. Avoid creating Value Objects with only one property unless they represent a significant domain concept. Do not derive an excessive number of Value Objects.</rule>
<rule id="3">**Aggregate References:** Aggregates that relate to other Aggregates should use Value Objects to hold these references. When referencing another Aggregate via a ValueObject, write the name as '<Referenced Aggregate Name> + Reference'. Avoid bidirectional references: ensure that references remain unidirectional.</rule>
<rule id="4">**Reference Handling:** Before creating an Aggregate, consider if an Aggregate with the same core concept already exists in other BCs. If it exists, reference it using a Value Object with a foreign key rather than duplicating its definition.</rule>
<rule id="5">**Reference Validation:** When creating a Value Object with referenced_aggregate_name, you MUST reference an Aggregate that exists in the "existing_aggregates_in_other_bcs" section above. Do NOT reference non-existent Aggregates. Only use referenced_aggregate_name if the Aggregate is listed in the existing aggregates section. If the referenced Aggregate does not exist, do not include the reference.</rule>
<rule id="6">**Reference Field Specification:** When creating a Value Object with referenced_aggregate_name, you MUST also specify referenced_aggregate_field to indicate which specific field in the referenced Aggregate this Value Object points to. Typically, this should be the identifier field (e.g., "id", "orderId", "customerId") of the referenced Aggregate. If the referenced Aggregate uses a standard identifier field like "id", use that. This field specification is critical for precise reference targeting in the domain model.</rule>
</section>

<section id="naming_conventions">
<title>Naming Conventions</title>
<rule id="1">**English Names:** Use English for all object names (Aggregate, Enumeration, Value Object).</rule>
<rule id="2">**No Type Information:** Do not include type information in names or aliases (e.g., use "Book" instead of "BookAggregate").</rule>
<rule id="3">**Uniqueness:** Within a single Bounded Context, each Aggregate name must be unique.</rule>
<rule id="4">**PascalCase:** Use PascalCase for all names (e.g., "ShoppingCart", "OrderStatus", "PaymentReference").</rule>
</section>

<section id="traceability">
<title>Traceability Requirements</title>
<rule id="1">**User Story Mapping:** Each Aggregate MUST list which User Story IDs from this BC it implements. This creates traceability from requirements to implementation.</rule>
<rule id="2">**Complete Coverage:** Ensure that all User Stories listed in the breakdowns are covered by at least one Aggregate.</rule>
</section>
</guidelines>
</core_instructions>

<analysis_approach>
Consider the following when identifying Aggregates:
1. **Business Invariants:** What business rules must be enforced atomically?
2. **Transactional Boundaries:** What data must be changed together in a single transaction?
3. **Domain Concepts:** What key entities/concepts are mentioned in the User Story breakdowns?
4. **Consistency Requirements:** What data needs to be kept consistent together?
5. **Potential Aggregates:** Review the "Potential Aggregates" listed in the breakdowns as starting points

Think about:
- Which domain objects naturally belong together?
- What would be the boundaries between different Aggregates?
- How would Aggregates interact with each other (via Value Objects with references)?
</analysis_approach>

<output_requirements>
For each Aggregate, provide:
- **name:** Aggregate name in PascalCase (unique within this BC)
- **root_entity:** Root entity name (entry point for all operations)
- **invariants:** List of business invariants this aggregate enforces
- **description:** What this aggregate manages
- **user_story_ids:** List of User Story IDs that this aggregate implements (IMPORTANT for traceability!)
- **enumerations:** (Optional) List of Enumerations associated with this aggregate (for state or similar information)
- **value_objects:** (Optional) List of Value Objects within this aggregate (for properties or references to other Aggregates)

For each Enumeration:
- **name:** Enumeration name in PascalCase
- **alias:** (Optional) Alias for display
- **items:** List of enumeration item values as strings (e.g., ["PENDING", "PROCESSING", "COMPLETED"]). Generate appropriate items based on the enumeration's purpose and domain context.

For each Value Object:
- **name:** Value Object name in PascalCase
- **alias:** (Optional) Alias for display
- **referenced_aggregate_name:** (Optional) Name of the referenced Aggregate if this is a reference Value Object
- **referenced_aggregate_field:** (Optional) Name of the specific field in the referenced Aggregate that this Value Object references. This should typically be the identifier field (e.g., "id", "orderId", "customerId") of the referenced Aggregate. If the referenced Aggregate has a standard identifier field, use that field name. If not specified, the reference will point to the Aggregate root entity itself.
- **fields:** List of fields in this value object. Each field should be an object with:
  - **name:** Field name (e.g., "street", "city", "amount")
  - **type:** Field type (e.g., "String", "Integer", "Decimal", "Date")
  Generate appropriate fields based on the value object's purpose and what data it should encapsulate.

CRITICAL: 
- Do NOT generate IDs; server assigns UUID id + derives key.
- **MUST generate enumeration items** - Each enumeration should have a meaningful list of item values.
- **MUST generate value object fields** - Each value object should have fields that represent its data structure (unless it's a simple reference value object that only holds an aggregate reference).
</output_requirements>

<examples>
Example for Order BC:
- Aggregate: Cart
  - Root Entity: Cart
  - Invariants: ["Cart total must be non-negative", "Cart items must have valid quantities"]
  - Description: Shopping cart management
  - User Story IDs: [US-001]
  - Enumerations: [{{"name": "CartStatus", "alias": "Cart Status", "items": ["ACTIVE", "ABANDONED", "CHECKED_OUT"]}}]
  - Value Objects: []

- Aggregate: Order
  - Root Entity: Order
  - Invariants: ["Order total must match sum of items", "Order must have at least one item"]
  - Description: Order lifecycle management
  - User Story IDs: [US-001, US-002, US-003]
  - Enumerations: [{{"name": "OrderStatus", "alias": "Order Status", "items": ["PENDING", "CONFIRMED", "SHIPPED", "DELIVERED", "CANCELLED"]}}]
  - Value Objects: [
      {{"name": "CustomerReference", "alias": "Customer Reference", "referenced_aggregate_name": "Customer", "referenced_aggregate_field": "id", "fields": [{{"name": "customerId", "type": "String"}}]}},
      {{"name": "ShippingAddress", "alias": "Shipping Address", "fields": [{{"name": "street", "type": "String"}}, {{"name": "city", "type": "String"}}, {{"name": "postalCode", "type": "String"}}, {{"name": "country", "type": "String"}}]}}
    ]

Example for Inventory BC:
- Aggregate: Stock
  - Root Entity: Stock
  - Invariants: ["Stock quantity cannot be negative"]
  - Description: Stock level management
  - User Story IDs: [US-009, US-010]
  - Enumerations: []
  - Value Objects: []
</examples>

Output should be a list of AggregateCandidate objects with clear boundaries, proper structure, and complete traceability."""

# =============================================================================
# Command Extraction
# =============================================================================

EXTRACT_COMMANDS_PROMPT = """You are tasked with identifying Commands for the given Aggregate based on User Story requirements, following Domain-Driven Design and Event Storming principles.

<target_aggregate>
Name: {aggregate_name}
ID: {aggregate_id}
Bounded Context: {bc_name}
</target_aggregate>

<user_stories>
{user_story_context}
</user_stories>

<core_instructions>
<title>Command Identification Task</title>
<task_description>Analyze the User Stories and identify all Commands that this Aggregate should handle. Commands represent user/system intentions to change state and are the entry points for business operations.</task_description>

<guidelines>
<title>Command Identification Guidelines</title>

<section id="command_definition">
<title>What is a Command?</title>
<rule id="1">**State-Changing Intent:** Commands represent intentions to change the system's state or data. They are imperative actions that express "what should happen".</rule>
<rule id="2">**Single Aggregate Responsibility:** Each Command is handled by exactly ONE Aggregate. The Aggregate is responsible for validating and executing the command.</rule>
<rule id="3">**User/System Intent:** Commands can be triggered by users, systems, or policies (from other Bounded Contexts).</rule>
<rule id="4">**Idempotency Consideration:** Some commands may be idempotent (safe to retry), but this is determined at implementation time.</rule>
</section>

<section id="command_categories">
<title>Command Categories</title>
<rule id="1">
<name>Create Operations</name>
<description>Commands that create new domain entities or initiate new business processes</description>
<examples>CreateOrder, RegisterUser, CreateReservation, InitiatePayment</examples>
</rule>

<rule id="2">
<name>Update Operations</name>
<description>Commands that modify existing domain entities or change their state</description>
<examples>UpdateProfile, ModifyOrder, ChangeReservationStatus, UpdateInventory</examples>
</rule>

<rule id="3">
<name>Delete/Cancel Operations</name>
<description>Commands that remove entities or cancel business processes</description>
<examples>CancelOrder, DeleteReservation, RemoveItem, AbortTransaction</examples>
</rule>

<rule id="4">
<name>Process Operations</name>
<description>Commands that execute business processes or workflows</description>
<examples>ProcessPayment, ConfirmReservation, VerifyEmail, CalculatePrice</examples>
</rule>

<rule id="5">
<name>Business Logic Operations</name>
<description>Commands that execute specific business rules or validations</description>
<examples>ValidateOrder, AuthenticateUser, CheckAvailability, ApproveRequest</examples>
</rule>

<rule id="6">
<name>External Integration Operations</name>
<description>Commands that interact with external systems or services</description>
<examples>SyncInventory, NotifyExternalSystem, ImportData, ExportReport</examples>
</rule>
</section>

<section id="naming_conventions">
<title>Naming Conventions</title>
<rule id="1">**Verb + Noun Pattern:** Use imperative verb followed by noun in PascalCase (e.g., CreateOrder, CancelOrder, ProcessPayment)</rule>
<rule id="2">**Clear Intent:** Command names should clearly express the business intent (e.g., PlaceOrder is better than Order)</rule>
<rule id="3">**Domain Language:** Use domain-specific terminology that business stakeholders understand</rule>
<rule id="4">**Avoid Generic CRUD:** Unless explicitly required, avoid generic CRUD operations. Focus on domain-specific operations.</rule>
</section>

<section id="actor_classification">
<title>Actor Classification</title>
<rule id="1">**Primary Rule - Match User Story Role:** The actor should primarily match the role from the User Story that the Command implements. If a User Story has role "customer", the actor should be "customer". If it has "manager", use "manager". Use the exact role from the User Story when available.</rule>
<rule id="2">**Fallback to Standard Actors:** Only when the User Story role is generic (e.g., "user") or when no User Story is associated, use these standard actors:
- **user:** Generic end users through UI or API (e.g., PlaceOrder, UpdateProfile)
- **admin:** Administrators or privileged users (e.g., ApproveOrder, SuspendUser)
- **system:** System processes, scheduled jobs, or internal workflows (e.g., ProcessScheduledPayment, CleanupExpiredSessions)
- **external:** External systems or services (e.g., SyncInventoryFromERP, ReceiveWebhookNotification)</rule>
<rule id="3">**Natural Language:** Use natural, domain-appropriate actor names. Examples: "customer", "seller", "delivery_driver", "warehouse_manager", "payment_gateway", etc. Do not force-fit into only 4 categories.</rule>
<rule id="4">**Consistency:** Maintain consistency - if multiple Commands implement User Stories with the same role, use the same actor name.</rule>
</section>

<section id="traceability">
<title>Traceability Requirements</title>
<rule id="1">**User Story Mapping:** Each Command MUST list which User Story IDs it directly implements. This creates traceability: UserStory → Command.</rule>
<rule id="2">**Complete Coverage:** Ensure that all User Stories for this Aggregate are covered by at least one Command.</rule>
<rule id="3">**Multiple Stories:** A Command can implement multiple User Stories if it serves multiple requirements.</rule>
</section>

<section id="command_event_relationship">
<title>Command-Event Relationship</title>
<rule id="1">**Event Emission:** Every Command should emit at least one Event upon successful execution. The Event represents what happened as a result of the Command.</rule>
<rule id="2">**Event Naming:** Events are named in past tense (e.g., OrderPlaced, PaymentProcessed), while Commands are imperative (e.g., PlaceOrder, ProcessPayment).</rule>
<rule id="3">**Event Inheritance:** Events inherit user_story_ids from the Command that emits them, maintaining traceability.</rule>
</section>
</guidelines>
</core_instructions>

<analysis_approach>
When identifying Commands, consider:
1. **User Actions:** What actions can users take that affect this Aggregate?
2. **System Triggers:** What automated processes or scheduled jobs interact with this Aggregate?
3. **Business Processes:** What business workflows involve this Aggregate?
4. **State Changes:** What state changes are possible for entities in this Aggregate?
5. **Cross-BC Interactions:** What commands might be invoked by policies from other Bounded Contexts?

Think about:
- Which User Stories require state changes in this Aggregate?
- What business operations are mentioned in the User Stories?
- What commands would be needed to support the Aggregate's responsibilities?
</analysis_approach>

<output_requirements>
For each Command, provide:
- **name:** Command name in PascalCase using Verb+Noun pattern (e.g., CreateOrder, CancelOrder, ProcessPayment)
- **actor:** Who/what triggers this command. MUST match the role from the User Story when available (e.g., if User Story role is "customer", use "customer"). Use natural, domain-appropriate names.
- **category:** Command category - one of: Create, Update, Delete, Process, Business Logic, or External Integration
- **inputSchema:** JSON schema or description of command input parameters (optional but recommended for complex commands)
- **description:** Clear, concise description of what this command does and its business purpose
- **user_story_ids:** List of User Story IDs that this command directly implements (IMPORTANT for traceability!)

CRITICAL:
- Do NOT generate IDs; server assigns UUID id + derives key.
- Ensure ALL User Stories for this Aggregate are covered by at least one Command.
- Use domain-specific command names, not generic CRUD unless explicitly required.
- Commands should reflect business intent, not technical implementation details.
- Actor should match User Story role when available - do not force into only 4 categories.
</output_requirements>

<examples>
Example for Order Aggregate:
- **CreateOrder** (actor: user, implements: [US-001])
  - Description: Creates a new order with items and customer information
  
- **CancelOrder** (actor: user, implements: [US-002])
  - Description: Cancels an existing order and initiates refund process
  
- **UpdateOrderStatus** (actor: system, implements: [US-003])
  - Description: Updates order status based on shipping or fulfillment events

Example for Payment Aggregate:
- **ProcessPayment** (actor: user, implements: [US-005])
  - Description: Processes payment for an order using selected payment method
  
- **RefundPayment** (actor: system, implements: [US-006])
  - Description: Refunds a payment, typically triggered by order cancellation policy
</examples>

Output should be a list of CommandCandidate objects with clear business intent, proper actor classification, and complete traceability to User Stories."""

# =============================================================================
# Event Extraction
# =============================================================================

EXTRACT_EVENTS_PROMPT = """You are tasked with identifying Events emitted by Commands in this Aggregate, following Domain-Driven Design and Event Storming principles.

<target_aggregate>
Name: {aggregate_name}
Bounded Context: {bc_name}
</target_aggregate>

<commands>
{commands}
</commands>

<core_instructions>
<title>Event Identification Task</title>
<task_description>Analyze the Commands and identify all Events that should be emitted when these Commands execute successfully. Events represent immutable facts that happened in the domain and are the foundation of event-driven architecture.</task_description>

<guidelines>
<title>Event Identification Guidelines</title>

<section id="event_definition">
<title>What is an Event?</title>
<rule id="1">**Immutable Facts:** Events represent facts that have already happened. They are immutable and cannot be changed once emitted.</rule>
<rule id="2">**Past Tense:** Events are named in past tense because they describe something that has already occurred (e.g., OrderPlaced, PaymentProcessed).</rule>
<rule id="3">**Command Result:** Events are the result of successful Command execution. Every Command should emit at least one Event on success.</rule>
<rule id="4">**Domain Significance:** Events represent business-significant state changes, not technical implementation details.</rule>
<rule id="5">**Cross-BC Communication:** Events can be consumed by other Bounded Contexts through Policies, enabling loose coupling.</rule>
</section>

<section id="event_discovery_methodology">
<title>Event Discovery Methodology</title>
<rule id="1">
<name>Comprehensive Coverage</name>
<description>Convert EVERY significant business moment into domain events. Do not skip or summarize business processes.</description>
</rule>

<rule id="2">
<name>Complete State Capture</name>
<description>Ensure ALL business-significant state changes are represented as events. Capture the complete lifecycle of domain entities.</description>
</rule>

<rule id="3">
<name>Flow Completeness</name>
<description>Include both happy path scenarios AND exception flows. Events should represent both successful outcomes and failures (e.g., OrderPlaced, OrderPlacementFailed).</description>
</rule>

<rule id="4">
<name>State Change Focus</name>
<description>Generate events ONLY for business-significant state changes. Do NOT create events for read-only operations or queries.</description>
</rule>

<rule id="5">
<name>Primary Business Actions</name>
<description>Focus on the primary business action rather than secondary consequences. The event should represent the main business outcome.</description>
</rule>
</section>

<section id="event_categories">
<title>Event Categories</title>
<rule id="1">
<name>Creation Events</name>
<description>Events emitted when new entities are created</description>
<examples>OrderCreated, UserRegistered, ReservationMade, PaymentInitiated</examples>
</rule>

<rule id="2">
<name>State Change Events</name>
<description>Events emitted when entity state changes</description>
<examples>OrderConfirmed, PaymentProcessed, ReservationCancelled, InventoryUpdated</examples>
</rule>

<rule id="3">
<name>Completion Events</name>
<description>Events emitted when business processes complete</description>
<examples>OrderShipped, PaymentCompleted, ReservationConfirmed, RefundProcessed</examples>
</rule>

<rule id="4">
<name>Failure Events</name>
<description>Events emitted when operations fail (important for exception handling)</description>
<examples>OrderPlacementFailed, PaymentRejected, ReservationConflictDetected</examples>
</rule>

<rule id="5">
<name>Business Process Events</name>
<description>Events emitted during business workflows</description>
<examples>OrderValidated, PaymentAuthorized, InventoryReserved, NotificationSent</examples>
</rule>
</section>

<section id="naming_conventions">
<title>Naming Conventions</title>
<rule id="1">**Past Participle Pattern:** Use Noun + Past Participle in PascalCase (e.g., OrderPlaced, PaymentProcessed, UserRegistered)</rule>
<rule id="2">**Clear Business Intent:** Event names should clearly express what business fact occurred (e.g., OrderPlaced is better than OrderEvent)</rule>
<rule id="3">**Domain Language:** Use domain-specific terminology that business stakeholders understand</rule>
<rule id="4">**Consistency:** Maintain consistent naming patterns across related events (e.g., OrderPlaced, OrderConfirmed, OrderShipped)</rule>
</section>

<section id="command_event_mapping">
<title>Command-Event Mapping</title>
<rule id="1">**One-to-Many Relationship:** A Command can emit multiple Events if it triggers multiple business outcomes (e.g., CancelOrder might emit OrderCancelled and RefundInitiated).</rule>
<rule id="2">**At Least One Event:** Every Command MUST emit at least one Event on successful execution.</rule>
<rule id="3">**Event Naming Relationship:** Events are named in past tense (OrderPlaced) while Commands are imperative (PlaceOrder). The Event name should reflect the Command's outcome.</rule>
<rule id="4">**Failure Events:** Consider emitting failure events for important error scenarios (e.g., OrderPlacementFailed).</rule>
</section>

<section id="traceability">
<title>Traceability Requirements</title>
<rule id="1">**User Story Inheritance:** Events MUST inherit user_story_ids from the Command that emits them. This maintains traceability: UserStory → Command → Event.</rule>
<rule id="2">**Complete Coverage:** Ensure that all Commands have corresponding Events, maintaining complete traceability.</rule>
<rule id="3">**Multiple Stories:** An Event can be related to multiple User Stories if the emitting Command implements multiple stories.</rule>
</section>

<section id="event_versioning">
<title>Event Versioning</title>
<rule id="1">**Version Format:** Events use semantic versioning in their key (e.g., OrderPlaced@1.0.0). The server will handle version assignment.</rule>
<rule id="2">**Backward Compatibility:** When events change, new versions are created to maintain backward compatibility with existing consumers.</rule>
</section>
</guidelines>
</core_instructions>

<analysis_approach>
When identifying Events, consider:
1. **Command Outcomes:** What happens when each Command executes successfully?
2. **State Changes:** What state changes occur in the Aggregate as a result of Commands?
3. **Business Facts:** What business facts are created that other parts of the system need to know about?
4. **Cross-BC Needs:** What events would other Bounded Contexts need to react to?
5. **Exception Scenarios:** What failure events should be emitted for important error cases?

Think about:
- What business facts are created when each Command executes?
- What state changes are significant enough to be events?
- What would other Bounded Contexts need to know about?
- What events would support the business workflows described in User Stories?
</analysis_approach>

<output_requirements>
For each Event, provide:
- **name:** Event name in PascalCase using Noun+PastParticiple pattern (e.g., OrderPlaced, PaymentProcessed, UserRegistered)
- **version:** Event version (default: "1.0.0") for schema evolution
- **payload:** JSON schema or description of event payload/data (optional but recommended for complex events)
- **description:** Clear, concise description of what happened and why it's significant
- **user_story_ids:** List of User Story IDs inherited from the emitting Command (IMPORTANT for traceability!)

CRITICAL:
- Do NOT generate IDs; server assigns UUID id + derives key with version (e.g., @1.0.0).
- Ensure ALL Commands have at least one corresponding Event.
- Events should represent business facts, not technical implementation details.
- Use past tense naming to reflect that events represent things that have already happened.
- Consider both success and failure scenarios when appropriate.
</output_requirements>

<examples>
Example for Order Aggregate Commands:
- **CreateOrder** command → **OrderCreated** event
  - Description: A new order has been created with items and customer information
  - Inherits user_story_ids from CreateOrder command

- **CancelOrder** command → **OrderCancelled** event
  - Description: An existing order has been cancelled and refund process initiated
  - Inherits user_story_ids from CancelOrder command

- **UpdateOrderStatus** command → **OrderStatusUpdated** event
  - Description: The status of an order has been updated (e.g., from PENDING to CONFIRMED)
  - Inherits user_story_ids from UpdateOrderStatus command

Example for Payment Aggregate Commands:
- **ProcessPayment** command → **PaymentProcessed** event
  - Description: A payment has been successfully processed for an order
  - Inherits user_story_ids from ProcessPayment command

- **ProcessPayment** command → **PaymentFailed** event (alternative outcome)
  - Description: Payment processing failed due to insufficient funds or other reasons
  - Inherits user_story_ids from ProcessPayment command

- **RefundPayment** command → **PaymentRefunded** event
  - Description: A payment has been refunded, typically triggered by order cancellation
  - Inherits user_story_ids from RefundPayment command
</examples>

Output should be a list of EventCandidate objects with clear business significance, proper naming conventions, and complete traceability to Commands and User Stories."""

# =============================================================================
# ReadModel Extraction
# =============================================================================

EXTRACT_READMODELS_PROMPT = """You are tasked with identifying ReadModels (query/projection models) for the given Bounded Context, following Domain-Driven Design and CQRS principles.

<target_bounded_context>
Name: {bc_name}
ID: {bc_id}
Description: {bc_description}
</target_bounded_context>

<user_stories>
{user_stories}
</user_stories>

<available_events>
{events}
</available_events>

<core_instructions>
<title>ReadModel Identification Task</title>
<task_description>Analyze the User Stories and identify all ReadModels (query/projection models) that this Bounded Context should provide. ReadModels represent query operations that retrieve data without changing state and are the foundation of CQRS read side.</task_description>

<guidelines>
<title>ReadModel Identification Guidelines</title>

<section id="readmodel_definition">
<title>What is a ReadModel?</title>
<rule id="1">**Query Intent Only:** ReadModels are for QUERY operations only (read/search/list/detail/status). Do NOT create ReadModels for commands that change state.</rule>
<rule id="2">**No State Changes:** ReadModels retrieve data without modifying it. They are read-only projections optimized for query performance.</rule>
<rule id="3">**CQRS Pattern:** ReadModels are updated by Events through projections, enabling eventual consistency between write and read sides.</rule>
<rule id="4">**User-Facing Queries:** ReadModels support user-facing queries and UI data requirements.</rule>
</section>

<section id="readmodel_categories">
<title>ReadModel Categories</title>
<rule id="1">
<name>Data Retrieval</name>
<description>Operations to fetch data without modifying it</description>
<examples>
<category name="Single Retrieval">UserProfile, ReservationDetail, FlightDetail, OrderDetail, ProductDetail</category>
<category name="List Retrieval">FlightList, ReservationHistory, InquiryList, OrderList, ProductList</category>
</examples>
</rule>

<rule id="2">
<name>Search and Filtering</name>
<description>Data retrieval based on specific conditions or criteria</description>
<examples>
<category name="Search">FlightSearch, SearchReservations, SearchOrders, SearchProducts</category>
<category name="Filtering">FilteredFlightList, AvailableSeats, ActiveOrders, InStockProducts</category>
</examples>
</rule>

<rule id="3">
<name>Statistics and Reports</name>
<description>Aggregated data or summary information</description>
<examples>
<category name="Statistics">ReservationStatistics, SalesReport, OrderSummary, RevenueReport</category>
<category name="Status">SeatAvailability, FlightStatus, OrderStatus, InventoryStatus</category>
</examples>
</rule>

<rule id="4">
<name>UI Support Data</name>
<description>Data required for screen composition and user interface</description>
<examples>
<category name="Option Lists">AirportList, SeatClassOptions, CategoryList, PaymentMethodOptions</category>
<category name="Configuration">UserPreferences, SystemSettings, DisplayConfig, FilterOptions</category>
</examples>
</rule>
</section>

<section id="naming_conventions">
<title>Naming Conventions</title>
<rule id="1">**Noun + Purpose Pattern:** Use Noun + Purpose in PascalCase (e.g., OrderSummary, OrderStatus, ProductCatalog, InventorySnapshot, UserProfile)</rule>
<rule id="2">**Clear Query Intent:** ReadModel names should clearly express what data is being queried (e.g., OrderList is better than OrderQuery)</rule>
<rule id="3">**Domain Language:** Use domain-specific terminology that business stakeholders understand</rule>
<rule id="4">**Consistency:** Maintain consistent naming patterns across related ReadModels (e.g., OrderList, OrderDetail, OrderSummary)</rule>
</section>

<section id="actor_classification">
<title>Actor Classification</title>
<rule id="1">**Primary Rule - Match User Story Role:** The actor should primarily match the role from the User Story that the ReadModel supports. If a User Story has role "customer", the actor should be "customer". If it has "admin", use "admin". Use the exact role from the User Story when available.</rule>
<rule id="2">**Fallback to Standard Actors:** Only when the User Story role is generic (e.g., "user") or when no User Story is associated, use these standard actors:
- **user:** Generic end users through UI or API (e.g., OrderList, UserProfile)
- **admin:** Administrators or privileged users (e.g., OrderStatistics, UserManagementList)
- **system:** System processes or internal queries (e.g., SystemHealthStatus, BackgroundJobStatus)</rule>
<rule id="3">**Natural Language:** Use natural, domain-appropriate actor names. Examples: "customer", "seller", "manager", "analyst", etc. Do not force-fit into only 3 categories.</rule>
<rule id="4">**Consistency:** Maintain consistency - if multiple ReadModels support User Stories with the same role, use the same actor name.</rule>
</section>

<section id="multiple_result_indicator">
<title>Multiple Result Indicator</title>
<rule id="1">**isMultipleResult:** MUST be one of: 'list', 'collection', or 'single result'.
- **'list':** Ordered lists of items (e.g., OrderList, ReservationHistory, InquiryList)
- **'collection':** Unordered collections or catalogs (e.g., ProductCatalog, CategoryList, OptionList)
- **'single result':** Single item results (e.g., OrderDetail, UserProfile, ProductDetail, OrderStatus)</rule>
<rule id="2">**Naming Hints:** 
- Names ending with "List", "History" typically use `isMultipleResult: 'list'`
- Names ending with "Catalog", "Options" typically use `isMultipleResult: 'collection'`
- Names ending with "Detail", "Profile", "Summary", "Status" typically use `isMultipleResult: 'single result'`</rule>
</section>

<section id="traceability">
<title>Traceability Requirements</title>
<rule id="1">**User Story Mapping:** Each ReadModel MUST list which User Story IDs it supports. This creates traceability: UserStory → ReadModel.</rule>
<rule id="2">**Complete Coverage:** Ensure that all query-related User Stories are covered by at least one ReadModel.</rule>
<rule id="3">**Multiple Stories:** A ReadModel can support multiple User Stories if it serves multiple query requirements.</rule>
</section>

<section id="event_projection">
<title>Event-Based Projection</title>
<rule id="1">**Event Updates:** ReadModels are updated by Events through projections. Consider which Events in this BC would update each ReadModel.</rule>
<rule id="2">**Event Availability:** The available Events list shows which Events can be used to build projections for ReadModels.</rule>
<rule id="3">**Denormalization:** ReadModels can be denormalized for query performance, combining data from multiple Aggregates or Events.</rule>
</section>
</guidelines>
</core_instructions>

<analysis_approach>
When identifying ReadModels, consider:
1. **Query Requirements:** What data do users need to view or search?
2. **User Story Queries:** What query operations are mentioned in the User Stories?
3. **UI Data Needs:** What data is required for UI screens and components?
4. **Event Projections:** Which Events would update each ReadModel?
5. **Search and Filtering:** What search or filtering capabilities are needed?

Think about:
- Which User Stories require query operations (not state changes)?
- What data needs to be displayed in UI screens?
- What search, list, or detail views are needed?
- What aggregated or summary data is required?
</analysis_approach>

<output_requirements>
For each ReadModel, provide:
- **name:** ReadModel name in PascalCase using Noun+Purpose pattern (e.g., OrderList, OrderDetail, UserProfile, ProductCatalog)
- **actor:** Who uses this ReadModel. MUST match the role from the User Story when available (e.g., if User Story role is "customer", use "customer"). Use natural, domain-appropriate names.
- **isMultipleResult:** MUST be one of: 'list' (ordered lists), 'collection' (unordered collections/catalogs), or 'single result' (single item results)
- **description:** Clear, concise description of what data this ReadModel retrieves and its purpose
- **user_story_ids:** List of User Story IDs that this ReadModel supports (IMPORTANT for traceability!)

CRITICAL:
- Do NOT generate IDs; server assigns UUID id + derives key.
- ReadModels are for QUERY intent only - do NOT create ReadModels for commands that change state.
- Keep it focused: prefer 0~3 ReadModels per Bounded Context for the first iteration.
- provisioningType is fixed to CQRS (you do NOT need to output provisioningType).
- Actor should match User Story role when available - do not force into only 3 categories.
- Ensure ALL query-related User Stories are covered by at least one ReadModel.
</output_requirements>

<examples>
Example for Order BC:
- **OrderList** (actor: customer, isMultipleResult: 'list', implements: [US-003])
  - Description: List of orders for a customer with summary information
  
- **OrderDetail** (actor: customer, isMultipleResult: 'single result', implements: [US-003])
  - Description: Detailed information about a specific order
  
- **OrderSummary** (actor: admin, isMultipleResult: 'single result', implements: [US-010])
  - Description: Aggregated summary of orders for reporting

Example for Product BC:
- **ProductCatalog** (actor: customer, isMultipleResult: 'collection', implements: [US-001])
  - Description: Catalog of available products with search and filtering
  
- **ProductDetail** (actor: customer, isMultipleResult: 'single result', implements: [US-001])
  - Description: Detailed information about a specific product
</examples>

Output should be a list of ReadModelCandidate objects with clear query intent, proper actor classification, and complete traceability to User Stories."""

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
   - For Commands: includes category and inputSchema (if available) - USE THESE to guide property generation
   - For Events: includes version and payload (if available) - USE THESE to guide property generation
4) A list of known Aggregate keys in the whole system (optional hint list for FK targets)

CRITICAL RULES (STRICT):
1) Only output domain-meaningful fields. DO NOT spam generic/system fields (createdAt, updatedAt, version, deleted, tenantId, etc.) unless absolutely domain-required.
2) Property `name` MUST be camelCase. Identifiers MUST be exactly `id` or end with `Id` (e.g., orderId, customerId).
3) `type` MUST be a Java type string. Use: String, UUID, int, long, boolean, BigDecimal, LocalDateTime, LocalDate, List<T>.
4) Every Property MUST include: name, type, description, isKey, isForeignKey, isRequired.
5) **IMPORTANT - Use inputSchema/payload when available:**
   - For Commands: If inputSchema is provided, use it to determine the command's input parameters/properties. The inputSchema describes what data the command expects.
   - For Events: If payload is provided, use it to determine the event's data structure/properties. The payload describes what data the event carries.
   - These schemas are valuable hints from the domain modeling phase - respect them when generating properties.
6) `isForeignKey` is your decision (do not apply simple automatic rules). If isForeignKey=true, provide fkTargetHint whenever reasonably confident.
7) fkTargetHint format (if provided): `<TargetType>:<TargetKey>:<TargetPropertyName>`
   - TargetType is one of: Aggregate|ReadModel|Event|Command
   - TargetKey is the Neo4j natural key of the target node
   - TargetPropertyName should typically be `id` (or another isKey field if explicit)
8) Output properties grouped by parent using PropertyBatch schema:
   - parentType must be one of Aggregate|Command|Event
   - parentKey MUST match one of the provided keys for this scope
9) Keep the list compact but complete enough to build a usable first draft.

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

