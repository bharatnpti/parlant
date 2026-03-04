# JourneyAPI.create_journey() Flow Documentation

## Overview

This document provides a comprehensive analysis of the `JourneyAPI.create_journey()` flow, including all components, external service calls, database interactions, and sample data flows. The journey creation process involves multiple sophisticated components working together to create structured conversational workflows.

## Table of Contents

1. [API Entry Point](#api-entry-point)
2. [Core Flow Components](#core-flow-components)
3. [Guideline Evaluator System](#guideline-evaluator-system)
4. [Proposer Mechanisms](#proposer-mechanisms)
5. [Database Interactions](#database-interactions)
6. [External Service Calls](#external-service-calls)
7. [Sample Data Flow](#sample-data-flow)
8. [Error Handling](#error-handling)
9. [Performance Considerations](#performance-considerations)

## API Entry Point

### Location
- **File**: `src/parlant/api/journeys.py`
- **Method**: `create_journey()` (lines 397-437)
- **HTTP Endpoint**: `POST /journeys`

### Request Structure
```python
class JourneyCreationParamsDTO:
    title: str                    # Journey title (1-100 chars)
    description: str              # Detailed journey description
    conditions: Sequence[str]     # Trigger conditions
    tags: Optional[list[TagId]]   # Associated tags
```

### Authorization
```python
await authorization_policy.authorize(request=request, operation=Operation.CREATE_JOURNEY)
```

## Core Flow Components

### 1. Authorization Check
- **Component**: `AuthorizationPolicy`
- **Purpose**: Validates user permissions for journey creation
- **Operation**: `Operation.CREATE_JOURNEY`

### 2. Guideline Creation Loop
```python
guidelines = [
    await guideline_store.create_guideline(
        condition=condition,
        action=None,
        tags=[],
    )
    for condition in params.conditions
]
```

### 3. Journey Creation
```python
journey = await journey_store.create_journey(
    title=params.title,
    description=params.description,
    conditions=[g.id for g in guidelines],
    tags=params.tags,
)
```

### 4. Tag Association
```python
for guideline in guidelines:
    await guideline_store.upsert_tag(
        guideline_id=guideline.id,
        tag_id=Tag.for_journey_id(journey.id),
    )
```

## Guideline Evaluator System

### Core Components

#### 1. GenericGuidelineMatchingStrategy
- **File**: `src/parlant/core/engines/alpha/guideline_matching/generic/generic_guideline_matching_strategy.py`
- **Purpose**: Orchestrates guideline evaluation and matching processes

#### 2. DisambiguationBatch
- **File**: `src/parlant/core/engines/alpha/guideline_matching/generic/disambiguation_batch.py`
- **Purpose**: Handles ambiguous guideline matching scenarios

### Evaluation Flow

#### Step 1: Guideline Matching
```python
class GenericDisambiguationGuidelineMatchingBatch:
    async def _get_disambiguation_targets(self, disambiguation_targets):
        # Groups guidelines by journey and builds evaluation context
        journey_to_conditions = defaultdict(list)
        guidelines_targets = []
        
        for g in disambiguation_targets:
            for t in g.tags:
                if t.startswith("journey:"):
                    journey_id = JourneyId(t.split(":", 1)[1])
                    journey_to_conditions[journey_id].append(g.content.condition)
```

#### Step 2: Context Building
```python
async def _build_context(self, interaction_events, disambiguation_condition):
    # Builds comprehensive context for evaluation
    context = GuidelineMatchingContext(
        events=interaction_events,
        agent_id=self._context.agent_id,
        customer_id=self._context.customer_id,
        session_id=self._context.session_id,
    )
```

#### Step 3: Evaluation Execution
```python
async def execute(self) -> GuidelineMatchingBatchResult:
    # Executes the disambiguation evaluation
    response = await self._schematic_generator.generate(
        prompt=prompt,
        hints={"temperature": 0.0},
    )
```

### Evaluation Schema
```python
class DisambiguationGuidelineMatchesSchema:
    tldr: str                                    # Summary of evaluation
    disambiguation_requested: bool               # Whether disambiguation needed
    customer_resolved: Optional[bool] = False    # Customer resolution status
    is_ambiguous: bool                          # Ambiguity flag
    guidelines: Optional[list[GuidelineCheck]] = []  # Evaluated guidelines
    clarification_action: Optional[str] = ""    # Clarification action
```

## Proposer Mechanisms

### 1. GuidelineActionProposer

#### Purpose
Generates action descriptions for guidelines that have conditions but no actions.

#### Implementation
```python
class GuidelineActionProposer:
    async def propose_action(
        self,
        guideline: GuidelineContent,
        tool_ids: Sequence[ToolId],
        progress_report: Optional[ProgressReport] = None,
    ) -> Optional[GuidelineActionProposition]:
```

#### Process Flow
1. **Tool Analysis**: Analyzes available tools for the guideline
2. **Prompt Building**: Constructs detailed prompts with tool specifications
3. **Action Generation**: Uses LLM to generate appropriate actions
4. **Validation**: Validates generated actions against tool capabilities

#### Sample Prompt Structure
```
GENERAL INSTRUCTIONS
-----------------
In our system, the behavior of a conversational AI agent is guided by "guidelines"...

Guideline Condition:
--------------------------
{customer asks for weather information}

Relevant Tools:
--------------
- local:get_weather: {
    "tool_name": "local:get_weather",
    "description": "Get the current weather and forecast for a specific city",
    "required_parameters": {
        "city": {"schema": {"type": "string"}, "description": "The city to get the weather for"}
    }
}
```

### 2. GuidelineConnectionProposer

#### Purpose
Identifies causal connections between guidelines to create workflow dependencies.

#### Implementation
```python
class GuidelineConnectionProposer:
    async def propose_connections(
        self,
        agent: Agent,
        introduced_guidelines: Sequence[GuidelineContent],
        existing_guidelines: Sequence[GuidelineContent] = [],
    ) -> Sequence[GuidelineConnectionProposition]:
```

#### Connection Types
1. **Direct Causation**: Source action directly causes target condition
2. **General Case**: Source action causes broad condition that includes target
3. **Implication**: Source action makes target condition likely
4. **No Connection**: No causal relationship exists

#### Scoring System
- **Score 10**: Direct causation
- **Score 7-9**: Strong causal relationship
- **Score 4-6**: Moderate relationship
- **Score 1-3**: Weak or no relationship

### 3. RelativeActionProposer

#### Purpose
Rewrites guideline actions to be self-contained and context-independent.

#### Implementation
```python
class RelativeActionProposer:
    async def propose_relative_action(
        self,
        examined_journey: Journey,
        step_guidelines: Sequence[Guideline] = [],
        journey_conditions: Sequence[Guideline] = [],
    ) -> RelativeActionProposition:
```

#### Rewriting Logic
```python
class RelativeActionBatch:
    index: str
    conditions: str
    action: str
    needs_rewrite_rational: str
    needs_rewrite: bool
    former_reference: Optional[str] = None
    rewritten_action: Optional[str] = None
```

#### Example Rewriting
**Original Action**: "Book it."
**Rewritten Action**: "Book the hotel for the specified dates and number of guests."

## Database Interactions

### 1. JourneyStore Operations

#### Journey Creation
```python
async def create_journey(
    self,
    title: str,
    description: str,
    conditions: Sequence[GuidelineId],
    creation_utc: Optional[datetime] = None,
    tags: Optional[Sequence[TagId]] = None,
) -> Journey:
```

#### Database Collections Used
1. **journeys**: Main journey documents
2. **journey_nodes**: Journey node associations
3. **journey_edges**: Journey edge associations
4. **journey_tags**: Journey tag associations
5. **journey_conditions**: Journey condition associations
6. **journeys_vector**: Vector embeddings for similarity search

#### Document Structure
```python
class JourneyDocument:
    id: ObjectId
    version: Version.String
    creation_utc: str
    title: str
    description: str
    root_id: JourneyNodeId
```

### 2. GuidelineStore Operations

#### Guideline Creation
```python
async def create_guideline(
    self,
    condition: str,
    action: Optional[str] = None,
    metadata: Mapping[str, JSONSerializable] = {},
    creation_utc: Optional[datetime] = None,
    enabled: bool = True,
    tags: Optional[Sequence[TagId]] = None,
) -> Guideline:
```

#### Database Collections Used
1. **guidelines**: Main guideline documents
2. **guideline_tags**: Guideline tag associations
3. **guidelines_vector**: Vector embeddings for similarity search

### 3. Vector Database Operations

#### Embedding Generation
```python
async def _vector_document_loader(self, doc: VectorDocument):
    # Handles vector document migration and loading
    return await VectorDocumentMigrationHelper[JourneyVectorDocument](
        self,
        migration_handlers,
    ).migrate(doc)
```

#### Similarity Search
```python
async def find_relevant_journeys(
    self,
    query: str,
    available_journeys: Sequence[Journey],
    max_journeys: int = 5,
) -> Sequence[Journey]:
    queries = await query_chunks(query, self._embedder)
    filters: Where = {"journey_id": {"$in": [str(j.id) for j in available_journeys]}}
    
    tasks = [
        self._vector_collection.find_similar_documents(
            filters=filters,
            query=q,
            k=max_journeys,
        )
        for q in queries
    ]
```

## External Service Calls

### 1. LLM Service Calls

#### SchematicGenerator
```python
response = await self._schematic_generator.generate(
    prompt=prompt,
    hints={"temperature": temperature},
)
```

#### Optimization Policy
```python
generation_attempt_temperatures = (
    self._optimization_policy.get_guideline_proposition_retry_temperatures(
        hints={"type": self.__class__.__name__}
    )
)
```

### 2. Service Registry

#### Tool Service Access
```python
for tid in tool_ids:
    service = await self._service_registry.read_tool_service(tid.service_name)
    tool = await service.read_tool(tid.tool_name)
    tools.append(tool)
```

### 3. Entity Queries

#### Glossary Term Lookup
```python
terms = await self._entity_queries.find_glossary_terms_for_context(
    agent_id=agent.id,
    query=test_guideline + causation_candidates,
)
```

## Sample Data Flow

### 1. Request Example
```json
{
    "title": "Customer Onboarding",
    "description": "1. Customer wants to lock their card\n2. Customer reports that their card doesn't work\n3. Customer suspects their card has been stolen",
    "conditions": [
        "customer needs unlocking their card",
        "customer needs help with card"
    ],
    "tags": ["tag1", "tag2"]
}
```

### 2. Guideline Creation Flow
```python
# For each condition, create a guideline
guideline_1 = await guideline_store.create_guideline(
    condition="customer needs unlocking their card",
    action=None,
    tags=[],
)

guideline_2 = await guideline_store.create_guideline(
    condition="customer needs help with card",
    action=None,
    tags=[],
)
```

### 3. Journey Creation
```python
journey = await journey_store.create_journey(
    title="Customer Onboarding",
    description="1. Customer wants to lock their card\n2. Customer reports that their card doesn't work\n3. Customer suspects their card has been stolen",
    conditions=[guideline_1.id, guideline_2.id],
    tags=["tag1", "tag2"],
)
```

### 4. Database Documents Created

#### Journey Document
```json
{
    "id": "IUCGT-lvpS",
    "version": "0.3.0",
    "creation_utc": "2025-01-27T10:30:00Z",
    "title": "Customer Onboarding",
    "description": "1. Customer wants to lock their card\n2. Customer reports that their card doesn't work\n3. Customer suspects their card has been stolen",
    "root_id": "IUCGT-lvpS-root"
}
```

#### Journey Vector Document
```json
{
    "id": "vec-IUCGT-lvpS",
    "version": "0.3.0",
    "journey_id": "IUCGT-lvpS",
    "content": "Customer Onboarding\n1. Customer wants to lock their card\n2. Customer reports that their card doesn't work\n3. Customer suspects their card has been stolen\nNodes: \nEdges: ",
    "checksum": "a1b2c3d4e5f6..."
}
```

#### Journey Condition Association Documents
```json
[
    {
        "id": "cond-assoc-1",
        "version": "0.3.0",
        "creation_utc": "2025-01-27T10:30:00Z",
        "journey_id": "IUCGT-lvpS",
        "condition": "guid_123abc"
    },
    {
        "id": "cond-assoc-2",
        "version": "0.3.0",
        "creation_utc": "2025-01-27T10:30:00Z",
        "journey_id": "IUCGT-lvpS",
        "condition": "guid_456def"
    }
]
```

#### Journey Tag Association Documents
```json
[
    {
        "id": "tag-assoc-1",
        "version": "0.3.0",
        "creation_utc": "2025-01-27T10:30:00Z",
        "journey_id": "IUCGT-lvpS",
        "tag_id": "tag1"
    },
    {
        "id": "tag-assoc-2",
        "version": "0.3.0",
        "creation_utc": "2025-01-27T10:30:00Z",
        "journey_id": "IUCGT-lvpS",
        "tag_id": "tag2"
    }
]
```

### 5. Response Example
```json
{
    "id": "IUCGT-lvpS",
    "title": "Customer Onboarding",
    "description": "1. Customer wants to lock their card\n2. Customer reports that their card doesn't work\n3. Customer suspects their card has been stolen",
    "conditions": ["guid_123abc", "guid_456def"],
    "tags": ["tag1", "tag2"]
}
```

## Error Handling

### 1. Authorization Errors
- **HTTP 403**: Insufficient permissions
- **Component**: `AuthorizationPolicy`

### 2. Validation Errors
- **HTTP 422**: Invalid request parameters
- **Validation**: Pydantic model validation

### 3. Database Errors
- **ItemNotFoundError**: Resource not found
- **Connection Errors**: Database connectivity issues

### 4. LLM Generation Errors
```python
for generation_attempt in range(3):
    try:
        # Generation attempt
        result = await self._generate_action(...)
        return result
    except Exception as exc:
        self._logger.warning(
            f"Generation attempt {generation_attempt} failed: {traceback.format_exception(exc)}"
        )
        last_generation_exception = exc

raise EvaluationError() from last_generation_exception
```

## Performance Considerations

### 1. Concurrent Operations
```python
# Parallel guideline creation
guidelines = await asyncio.gather(*[
    guideline_store.create_guideline(condition=condition, action=None, tags=[])
    for condition in params.conditions
])
```

### 2. Database Locking
```python
async with self._lock.writer_lock:
    # Atomic journey creation operations
    await self._collection.insert_one(document=self._serialize(journey))
    await self._vector_collection.insert_one(document=vector_doc)
```

### 3. Vector Search Optimization
```python
# Batch vector queries
tasks = [
    self._vector_collection.find_similar_documents(
        filters=filters,
        query=q,
        k=max_journeys,
    )
    for q in queries
]
all_results = chain.from_iterable(await safe_gather(*tasks))
```

### 4. Caching Strategy
- **Embedding Cache**: Cached vector embeddings for similarity search
- **Guideline Cache**: Cached guideline lookups
- **Journey Cache**: Cached journey metadata

## Conclusion

The `JourneyAPI.create_journey()` flow is a sophisticated system that orchestrates multiple components to create structured conversational workflows. It involves:

1. **Authorization and validation** of incoming requests
2. **Guideline creation** for each journey condition
3. **Journey creation** with proper associations
4. **Tag management** for organization and retrieval
5. **Vector embedding** for similarity search capabilities
6. **Error handling** with retry mechanisms
7. **Performance optimization** through concurrent operations and caching

The system is designed to be scalable, maintainable, and robust, with comprehensive error handling and performance optimizations throughout the flow.
