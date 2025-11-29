# WriterOS Coding Standards

**Last Updated:** 2025-11-28
**Status:** ENFORCED
**Scope:** All new code and refactoring

---

## Core Principles

### 1. Object-Oriented Programming (OOP)

**Requirement:** All new code must follow OOP principles.

**Guidelines:**

- Use classes for encapsulation and modularity
- Apply SOLID principles consistently
- Prefer composition over inheritance
- Use abstract base classes (ABC) for interfaces
- Implement design patterns where appropriate (Strategy, Factory, Composite, etc.)

**Example:**

```python
"""
Example of proper OOP design.

Design Decision:
- Used Strategy pattern to allow different filtering implementations
- Abstract base class defines interface contract
- Concrete classes implement specific filtering logic

Reasoning:
- Makes code extensible (new filters can be added without modifying existing code)
- Follows Open/Closed Principle
- Easy to test each filter in isolation
"""
from abc import ABC, abstractmethod
from typing import List
from uuid import UUID


class GraphFilter(ABC):
    """
    Abstract base class for graph traversal filters.

    Design Decision:
    Used ABC instead of duck typing to enforce interface contract.

    Reasoning:
    - Explicit interface makes intent clear
    - IDE support for method signatures
    - Runtime validation that subclasses implement required methods
    """

    @abstractmethod
    def filter_relationships(
        self,
        relationships: List['Relationship'],
        vault_id: UUID,
        **kwargs
    ) -> List['Relationship']:
        """
        Filter a list of relationships based on specific criteria.

        Args:
            relationships: List of relationships to filter
            vault_id: Vault context for the operation
            **kwargs: Additional filter parameters (subclass-specific)

        Returns:
            Filtered list of relationships

        Raises:
            NotImplementedError: If subclass does not implement this method
        """
        pass


class RelationshipTypeFilter(GraphFilter):
    """
    Concrete implementation that filters by relationship type.

    Design Decision:
    Store allowed types as a set for O(1) lookup performance.

    Reasoning:
    - Filtering is O(n) instead of O(n*m) with list membership checks
    - Immutable after construction (thread-safe)
    """

    def __init__(self, allowed_types: List['RelationType']):
        """
        Initialize the filter with allowed relationship types.

        Args:
            allowed_types: List of relationship types to allow through filter

        Design Decision:
        Accept list but convert to set internally.

        Reasoning:
        - List is more intuitive for callers
        - Set is more efficient for filtering
        - Conversion happens once at construction time
        """
        self.allowed_types = set(allowed_types)

    def filter_relationships(
        self,
        relationships: List['Relationship'],
        vault_id: UUID,
        **kwargs
    ) -> List['Relationship']:
        """
        Filter relationships to only those matching allowed types.

        Implementation Note:
        Uses list comprehension for performance over filter() + lambda.

        Complexity: O(n) where n is number of relationships
        """
        return [
            rel for rel in relationships
            if rel.relationship_type in self.allowed_types
        ]
```

---

### 2. Test-Driven Development (TDD)

**Requirement:** All new features must be developed using TDD.

**Process:**

1. **RED** - Write failing test first
2. **GREEN** - Write minimal code to make test pass
3. **REFACTOR** - Clean up implementation while keeping tests green

**Guidelines:**

- Write tests before implementation
- One test per behavior (not one test per method)
- Use Given-When-Then structure for clarity
- Aim for 100% coverage of public methods
- Use meaningful test names that describe the behavior

**Example:**

```python
"""
Test suite for RelationshipTypeFilter.

Design Decision:
Each test follows Given-When-Then structure for clarity.

Reasoning:
- Makes test intent immediately clear
- Easy to understand for new developers
- Serves as living documentation
"""
import pytest
from uuid import uuid4
from writeros.rag.graph_enhancements import RelationshipTypeFilter
from writeros.schema import Relationship, RelationType


class TestRelationshipTypeFilter:
    """
    Test suite for RelationshipTypeFilter class.

    Design Decision:
    Group related tests in a class for organization.

    Reasoning:
    - Easier to navigate test file
    - Can share fixtures via class-level setup
    - Clear test scope (all tests in class test one component)
    """

    def test_filter_by_single_type_returns_only_matching_relationships(
        self,
        sample_vault_id
    ):
        """
        Test that filtering by a single type returns only relationships of that type.

        Design Decision:
        Test name describes the expected behavior, not the implementation.

        Reasoning:
        - Tests should survive refactoring
        - Name tells you what the code should do, not how it does it
        - Makes test failures more informative
        """
        # GIVEN: A list of relationships with different types
        relationships = [
            Relationship(
                id=uuid4(),
                vault_id=sample_vault_id,
                source_entity_id=uuid4(),
                target_entity_id=uuid4(),
                relationship_type=RelationType.PARENT,
                strength=1.0
            ),
            Relationship(
                id=uuid4(),
                vault_id=sample_vault_id,
                source_entity_id=uuid4(),
                target_entity_id=uuid4(),
                relationship_type=RelationType.FRIEND,
                strength=0.8
            ),
            Relationship(
                id=uuid4(),
                vault_id=sample_vault_id,
                source_entity_id=uuid4(),
                target_entity_id=uuid4(),
                relationship_type=RelationType.PARENT,
                strength=1.0
            ),
        ]

        # WHEN: Filtering by a single type (PARENT)
        filter_instance = RelationshipTypeFilter([RelationType.PARENT])
        filtered = filter_instance.filter_relationships(
            relationships,
            sample_vault_id
        )

        # THEN: Only PARENT relationships are returned
        assert len(filtered) == 2
        assert all(
            rel.relationship_type == RelationType.PARENT
            for rel in filtered
        )

    def test_filter_with_empty_input_returns_empty_list(self, sample_vault_id):
        """
        Test that filtering an empty list returns an empty list.

        Design Decision:
        Test edge cases explicitly.

        Reasoning:
        - Edge cases often reveal bugs
        - Documents expected behavior for edge cases
        - Prevents defensive programming bugs (e.g., None checks where not needed)
        """
        # GIVEN: An empty list of relationships
        relationships = []

        # WHEN: Filtering the empty list
        filter_instance = RelationshipTypeFilter([RelationType.PARENT])
        filtered = filter_instance.filter_relationships(
            relationships,
            sample_vault_id
        )

        # THEN: An empty list is returned
        assert filtered == []
        assert isinstance(filtered, list)
```

---

### 3. No Emojis

**Requirement:** Code, comments, and documentation must not contain emojis.

**Rationale:**

- Terminal compatibility issues (Windows, SSH sessions)
- Professional code standards
- Accessibility concerns (screen readers)
- Cross-platform rendering issues

**Violations:**

```python
# BAD: Using emojis in comments
def process_data():
    # Process the data! 🚀
    pass

# BAD: Using emojis in error messages
raise ValueError("Invalid input 😞")

# BAD: Using emojis in logging
logger.info("Processing complete! ✅")
```

**Correct:**

```python
# GOOD: Clear, professional comments
def process_data():
    """
    Process the input data according to business rules.

    Design Decision:
    Validate input before processing to fail fast.

    Reasoning:
    Prevents partial processing of invalid data which could
    corrupt the database state.
    """
    pass

# GOOD: Descriptive error messages
raise ValueError("Invalid input: expected positive integer, got negative value")

# GOOD: Professional logging
logger.info("data_processing_complete", record_count=100, duration_ms=500)
```

---

### 4. Documentation Standards

**Requirement:** All code must be well-documented with clear explanations of design decisions and reasoning.

#### 4.1 Module-Level Documentation

Every module must have a docstring explaining:
- Purpose of the module
- Key design decisions
- Dependencies
- Usage examples (if applicable)

**Example:**

```python
"""
Graph-based retrieval enhancement components.

Purpose:
Provides OOP components for filtering and scoring entities during
graph-based retrieval operations. Enables granular control over
relationship traversal and entity importance weighting.

Design Decisions:
1. Used Strategy pattern for filters to allow runtime composition
2. Separate concerns: filtering (GraphFilter) vs. scoring (EntityScorer)
3. Immutable filter objects (thread-safe, cacheable)

Key Dependencies:
- sqlmodel: Database ORM
- writeros.schema: Entity and Relationship models
- writeros.utils.db: Database session management

Usage:
    from writeros.rag.graph_enhancements import RelationshipTypeFilter

    filter = RelationshipTypeFilter([RelationType.PARENT, RelationType.ALLY])
    filtered = filter.filter_relationships(all_relationships, vault_id)

See Also:
    - graph_retrieval.py: Integration with RAG pipeline
    - test_graph_enhancements.py: Test suite with usage examples
"""
from abc import ABC, abstractmethod
# ... rest of module
```

#### 4.2 Class-Level Documentation

Every class must have a docstring explaining:
- Purpose of the class
- Design decisions (why this class exists)
- Key attributes
- Usage examples

**Example:**

```python
class PageRankScorer(EntityScorer):
    """
    Computes entity importance using PageRank algorithm.

    Purpose:
    Identifies central entities in the knowledge graph to weight
    retrieval results toward more important characters/locations.

    Design Decision:
    Implemented PageRank instead of simpler degree centrality because:
    1. PageRank accounts for quality of connections, not just quantity
    2. Handles directed graphs correctly (parent->child vs. child->parent)
    3. Industry-standard algorithm with well-understood properties

    Algorithm:
    Iterative convergence based on:
        score(entity) = (1-d)/N + d * sum(score(neighbor) / out_degree(neighbor))

    where:
        d = damping factor (probability of following a link)
        N = total number of entities

    Complexity:
    Time: O(iterations * edges)
    Space: O(entities)

    Attributes:
        damping_factor: Probability of following a link (0.0-1.0)
        iterations: Maximum number of iterations
        convergence_threshold: Stop if change < threshold

    Usage:
        scorer = PageRankScorer(damping_factor=0.85, iterations=20)
        scores = await scorer.score_entities(entity_ids, vault_id)

        for entity_id, score in scores.items():
            print(f"{entity_id}: {score.importance_score:.3f}")

    See Also:
        - EntityScorer: Abstract base class
        - retrieve_chunks_with_advanced_graph: Usage in retrieval pipeline

    References:
        Page, L., Brin, S., Motwani, R., & Winograd, T. (1999).
        The PageRank citation ranking: Bringing order to the web.
        Stanford InfoLab Technical Report.
    """
```

#### 4.3 Method-Level Documentation

Every public method must have a docstring with:
- Purpose
- Arguments (with types and descriptions)
- Returns (with type and description)
- Raises (exceptions that may be raised)
- Design decisions (if non-trivial)
- Examples (if helpful)

**Example:**

```python
def filter_relationships(
    self,
    relationships: List[Relationship],
    vault_id: UUID,
    **kwargs
) -> List[Relationship]:
    """
    Filter relationships by temporal bounds (story sequence or world time).

    Purpose:
    Implements temporal firewall to prevent spoilers and enforce
    point-in-time queries ("Who was allied with X at chapter 15?").

    Args:
        relationships: List of relationships to filter
        vault_id: Vault context (used for logging, not filtering logic)
        **kwargs: Additional parameters (unused, for interface compatibility)

    Returns:
        Filtered list of relationships that satisfy temporal constraints.
        Returns empty list if no relationships match.
        Order is preserved from input list.

    Raises:
        ValueError: If both max_sequence and current_sequence are set
                   (ambiguous which constraint to apply)

    Design Decision:
    Check established_at_sequence AND ended_at_sequence for current_sequence
    queries instead of just is_active flag.

    Reasoning:
    is_active is a snapshot flag that may not reflect the state at the
    queried sequence. Explicit temporal bounds are more reliable for
    point-in-time queries.

    Examples:
        # Filter to relationships established by chapter 20
        filter = TemporalGraphFilter(mode="sequence", max_sequence=20)
        filtered = filter.filter_relationships(all_rels, vault_id)

        # Filter to relationships active at chapter 15
        filter = TemporalGraphFilter(mode="sequence", current_sequence=15)
        filtered = filter.filter_relationships(all_rels, vault_id)

    Performance:
    O(n) where n is number of relationships.
    All checks are in-memory integer comparisons.
    """
    # Implementation with inline comments for complex logic
    filtered = []

    for rel in relationships:
        # Check if relationship was established within bounds
        # Design Decision: Use continue for early exit to reduce nesting
        if self.max_sequence is not None and rel.established_at_sequence:
            if rel.established_at_sequence > self.max_sequence:
                continue  # Established too late

        # ... rest of implementation

    return filtered
```

#### 4.4 Inline Comments for Complex Logic

Use inline comments to explain:
- Non-obvious logic
- Performance optimizations
- Workarounds for bugs/limitations
- Algorithm steps

**Guidelines:**

- Comment the "why", not the "what" (code should be self-documenting for "what")
- Use comments to mark sections of complex algorithms
- Explain design decisions that aren't obvious from the code

**Example:**

```python
def compute_pagerank_scores(self, adjacency_graph):
    """Compute PageRank scores using power iteration method."""

    N = len(adjacency_graph)

    # Initialize scores uniformly
    # Design Decision: Use 1/N instead of 1.0 for all nodes
    # Reasoning: Ensures sum of scores = 1.0 (probability distribution)
    scores = {node: 1.0 / N for node in adjacency_graph}

    d = self.damping_factor

    for iteration in range(self.iterations):
        new_scores = {}
        max_change = 0.0

        for node in adjacency_graph:
            # Random jump probability (teleportation)
            # This prevents score from getting trapped in subgraphs
            rank = (1 - d) / N

            # Contribution from incoming edges
            # Design Decision: Weight by relationship strength
            # Reasoning: Strong relationships (allies) should contribute more
            #            than weak relationships (acquaintances)
            for neighbor, strength in adjacency_graph[node].in_edges:
                out_degree = len(adjacency_graph[neighbor].out_edges)
                if out_degree > 0:
                    # Divide by out_degree to normalize (PageRank formula)
                    contribution = (scores[neighbor] * strength) / out_degree
                    rank += d * contribution

            new_scores[node] = rank

            # Track maximum change for convergence check
            max_change = max(max_change, abs(rank - scores[node]))

        scores = new_scores

        # Early termination if converged
        # Design Decision: Check convergence every iteration
        # Reasoning: Saves iterations (typical convergence at 5-10 iterations)
        #            vs. checking only at end (always runs all iterations)
        if max_change < self.convergence_threshold:
            break

    return scores
```

---

### 5. Code Organization

**Requirement:** Code must be well-separated with clear boundaries between concerns.

#### 5.1 File Organization

Each file should have a single, clear purpose:

```
src/writeros/rag/
├── graph_enhancements.py      # OOP components (filters, scorers)
├── graph_retrieval.py         # Retrieval functions using components
└── retriever.py               # Main RAG retriever class

tests/rag/
├── test_graph_enhancements.py # Unit tests for OOP components
└── test_graph_retrieval.py    # Integration tests for retrieval
```

#### 5.2 Class Organization

Within a class, organize methods in this order:

1. Class docstring
2. Class attributes (if any)
3. `__init__` method
4. Public methods (alphabetically or by logical grouping)
5. Private methods (prefixed with `_`)
6. Magic methods (`__repr__`, `__str__`, etc.)

**Example:**

```python
class RelationshipTypeFilter(GraphFilter):
    """Class docstring here."""

    # Class attribute (if needed)
    DEFAULT_TYPES = [RelationType.PARENT, RelationType.FRIEND]

    def __init__(self, allowed_types: List[RelationType]):
        """Initialize the filter."""
        self.allowed_types = set(allowed_types)

    # Public methods (alphabetically)

    def filter_relationships(self, ...):
        """Filter relationships by type."""
        pass

    def get_allowed_types(self):
        """Get the list of allowed types."""
        return list(self.allowed_types)

    # Private methods

    def _validate_types(self, types):
        """Validate that types are valid RelationType instances."""
        pass

    # Magic methods

    def __repr__(self):
        """Return string representation of filter."""
        return f"RelationshipTypeFilter(types={len(self.allowed_types)})"
```

#### 5.3 Module Organization

Within a module file, organize code in this order:

1. Module docstring
2. Imports (grouped: stdlib, third-party, local)
3. Constants
4. Data classes / Type definitions
5. Abstract base classes
6. Concrete classes
7. Functions
8. Main block (if applicable)

**Example:**

```python
"""
Module docstring.
"""

# Standard library imports
from abc import ABC, abstractmethod
from typing import List, Dict, Set
from uuid import UUID

# Third-party imports
from sqlmodel import Session, select

# Local imports
from writeros.schema import Entity, Relationship
from writeros.utils.db import engine
from writeros.core.logging import get_logger

# Module-level constants
DEFAULT_DAMPING_FACTOR = 0.85
MAX_ITERATIONS = 20

# Logger
logger = get_logger(__name__)


# Data classes
@dataclass
class GraphPath:
    """Represents a path through the graph."""
    pass


# Abstract base classes
class GraphFilter(ABC):
    """Abstract base class for filters."""
    pass


# Concrete classes
class RelationshipTypeFilter(GraphFilter):
    """Concrete filter implementation."""
    pass


# Functions
def helper_function():
    """Standalone helper function."""
    pass
```

---

### 6. Naming Conventions

**Requirement:** Use clear, descriptive names that reveal intent.

#### 6.1 Classes

- Use PascalCase
- Name should be a noun or noun phrase
- Should describe what the class IS, not what it DOES

```python
# GOOD
class RelationshipTypeFilter:
class PageRankScorer:
class GraphPathTracker:

# BAD
class FilterRelationships:  # Sounds like a function
class DoPageRank:  # Sounds like a function
class Tracker:  # Too vague
```

#### 6.2 Methods

- Use snake_case
- Name should be a verb or verb phrase
- Should describe what the method DOES

```python
# GOOD
def filter_relationships(self, ...):
def compute_pagerank(self, ...):
def track_paths(self, ...):

# BAD
def relationships(self, ...):  # Noun, unclear what it does
def pagerank(self, ...):  # Noun, unclear what it does
def do_work(self, ...):  # Too vague
```

#### 6.3 Variables

- Use snake_case
- Name should describe the data it holds
- Boolean variables should sound like yes/no questions

```python
# GOOD
entity_count = len(entities)
is_active = check_status()
has_children = len(children) > 0

# BAD
n = len(entities)  # Too short, unclear
flag = check_status()  # Too vague
children_exist = len(children) > 0  # Awkward phrasing
```

---

### 7. Error Handling

**Requirement:** Use explicit error handling with informative messages.

#### 7.1 Exceptions

- Raise specific exception types
- Include context in error messages
- Document exceptions in docstrings

```python
def filter_relationships(self, relationships, vault_id):
    """
    Filter relationships by type.

    Args:
        relationships: List of relationships to filter
        vault_id: Vault context

    Returns:
        Filtered list of relationships

    Raises:
        TypeError: If relationships is not a list
        ValueError: If relationships list is empty
        ValueError: If vault_id is not a valid UUID
    """
    if not isinstance(relationships, list):
        raise TypeError(
            f"Expected relationships to be list, got {type(relationships)}"
        )

    if not relationships:
        raise ValueError("Cannot filter empty relationships list")

    # ... rest of implementation
```

#### 7.2 Logging

- Use structured logging
- Log at appropriate levels
- Include context for debugging

```python
logger.debug("filter_started", relationship_count=len(relationships))

try:
    filtered = self._apply_filter(relationships)
    logger.info(
        "filter_complete",
        original_count=len(relationships),
        filtered_count=len(filtered),
        filter_type=self.__class__.__name__
    )
except Exception as e:
    logger.error(
        "filter_failed",
        error=str(e),
        error_type=type(e).__name__,
        relationship_count=len(relationships)
    )
    raise
```

---

### 8. Performance Considerations

**Requirement:** Document performance characteristics and optimization decisions.

```python
class PageRankScorer:
    """
    Performance Characteristics:
    - Time Complexity: O(iterations * edges)
    - Space Complexity: O(entities)
    - Typical iterations: 5-10 (with damping_factor=0.85)

    Performance Optimizations:
    1. Early termination on convergence (saves ~50% of iterations)
    2. Set for entity lookup (O(1) vs O(n) with list)
    3. Pre-computed adjacency lists (avoid repeated DB queries)

    Benchmarks:
    - 50 entities, 100 edges: ~100ms
    - 200 entities, 500 edges: ~250ms
    - 1000 entities, 3000 edges: ~500ms
    """

    def score_entities(self, entity_ids, vault_id):
        """
        Compute PageRank scores.

        Design Decision:
        Build adjacency lists upfront instead of querying per iteration.

        Reasoning:
        Initial cost of O(edges) to build adjacency lists is amortized
        over iterations. Without this, we'd query DB iterations times,
        which would be O(iterations * edges * db_latency).

        Trade-off:
        Higher memory usage (store all edges) for better performance.
        For typical graphs (< 1000 entities), memory cost is negligible
        (< 1MB) but performance gain is significant (10x speedup).
        """
        pass
```

---

## Enforcement

### Code Review Checklist

Before merging code, verify:

- [ ] All new code follows OOP principles
- [ ] TDD process was followed (tests written first)
- [ ] No emojis in code, comments, or documentation
- [ ] All classes have comprehensive docstrings with design decisions
- [ ] All public methods have docstrings with Args/Returns/Raises
- [ ] Complex logic has inline comments explaining reasoning
- [ ] Code is well-organized (clear file/class/module structure)
- [ ] Names are descriptive and follow conventions
- [ ] Error handling is explicit with informative messages
- [ ] Performance considerations are documented

### Automated Checks

Consider adding pre-commit hooks to enforce:

```bash
# Check for emojis in code
grep -r '[^\x00-\x7F]' src/writeros --exclude-dir=__pycache__

# Check for missing docstrings
pylint --disable=all --enable=missing-docstring src/writeros

# Run tests
pytest tests/ --cov=src/writeros --cov-report=term-missing
```

---

## Examples of Violations

### Violation: No Design Decision Documentation

```python
# BAD: No explanation of why this approach was chosen
class PageRankScorer:
    def __init__(self, damping_factor=0.85):
        self.damping_factor = damping_factor
```

```python
# GOOD: Clear design decision with reasoning
class PageRankScorer:
    """
    Design Decision:
    Default damping_factor of 0.85 based on original PageRank paper.

    Reasoning:
    This value has been empirically validated across many graph types.
    Lower values (< 0.5) cause too much random jumping, making the
    algorithm too sensitive to starting conditions. Higher values
    (> 0.95) cause slow convergence and can trap score in subgraphs.
    """
    def __init__(self, damping_factor: float = 0.85):
        if not 0.0 <= damping_factor <= 1.0:
            raise ValueError(
                f"damping_factor must be in [0, 1], got {damping_factor}"
            )
        self.damping_factor = damping_factor
```

### Violation: Using Emojis

```python
# BAD
logger.info("Processing complete!")  # Unicode check mark

# GOOD
logger.info("processing_complete", status="success")
```

### Violation: Not Following TDD

```python
# BAD: Writing implementation before tests
def new_feature():
    # Implementation here
    pass

# Later... write tests
def test_new_feature():
    pass
```

```python
# GOOD: Write test first (TDD)
def test_new_feature_returns_filtered_results():
    """
    GIVEN: A list of items
    WHEN: Filtering by criteria
    THEN: Only matching items are returned
    """
    # Test implementation
    pass

# Then implement to make test pass
def new_feature():
    # Implementation
    pass
```

---

## Template for New Classes

Use this template when creating new classes:

```python
"""
Module name.

Purpose:
[What problem does this module solve?]

Design Decisions:
1. [First major design decision and reasoning]
2. [Second major design decision and reasoning]

Key Dependencies:
- [Dependency 1]: [Why it's needed]
- [Dependency 2]: [Why it's needed]
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID


class ClassName(BaseClass):
    """
    One-line summary of class purpose.

    Detailed description of what this class does and why it exists.

    Design Decisions:
    1. [First design decision]: [Reasoning]
    2. [Second design decision]: [Reasoning]

    Attributes:
        attribute_name: Description of what this attribute stores
        another_attribute: Description

    Performance:
    Time Complexity: O(?)
    Space Complexity: O(?)

    Usage:
        instance = ClassName(arg1, arg2)
        result = instance.method_name()

    See Also:
        - RelatedClass: Related functionality
        - module_name: Where this is used
    """

    def __init__(self, param1: Type1, param2: Type2):
        """
        Initialize the class.

        Args:
            param1: Description of param1
            param2: Description of param2

        Raises:
            ValueError: If param1 is invalid

        Design Decision:
        [Why this initialization approach?]

        Reasoning:
        [Explanation of the decision]
        """
        self.attribute1 = param1
        self.attribute2 = param2

    def public_method(self, arg: Type) -> ReturnType:
        """
        One-line summary of what this method does.

        Detailed description if needed.

        Args:
            arg: Description of argument

        Returns:
            Description of return value

        Raises:
            ExceptionType: When this exception is raised

        Design Decision:
        [If method has non-trivial design decision]

        Reasoning:
        [Explanation]

        Examples:
            result = instance.public_method(value)
        """
        pass
```

---

## Conclusion

These standards ensure:

- Code is maintainable and understandable
- Design decisions are preserved for future developers
- Tests serve as living documentation
- Code is professional and accessible
- New features are built on solid foundations

All new code must follow these standards. Existing code should be refactored
to meet these standards when modified.
