from enum import Enum

class EntityType(str, Enum):
    CHARACTER = "character"
    LOCATION = "location"
    FACTION = "faction"
    ORGANIZATION = "organization"  # ⭐ NEW (Phase 2.5): Structured institutions (The Citadel, The Faith)
    GROUP = "group"  # ⭐ NEW (Phase 2.5): Informal groups (smallfolk, merchants, bandits)
    ITEM = "item"
    ABILITY = "ability"
    MAGIC_SYSTEM = "magic_system"
    TECH_SYSTEM = "tech_system"
    EVENT = "event"
    PLOT_THREAD = "plot_thread"
    NOTE = "note"
    SCENE = "scene"  # ⭐ NEW: Allows Graph to link Characters to Scenes


class EntityStatus(str, Enum):
    """Character/Entity lifecycle status - CRITICAL for story logic."""
    ALIVE = "alive"
    DEAD = "dead"
    MISSING = "missing"
    UNKNOWN = "unknown"
    UNDEAD = "undead"  # Zombies, vampires, liches
    DORMANT = "dormant"  # Sleeping dragons, cryosleep
    ASCENDED = "ascended"  # Became a god, transcended
    IMPRISONED = "imprisoned"
    EXILED = "exiled"

    # Location / Structure
    INTACT = "intact"
    DESTROYED = "destroyed"
    ABANDONED = "abandoned"
    OCCUPIED = "occupied"
    CONTESTED = "contested"

    # Item / Object
    DAMAGED = "damaged"
    LOST = "lost"
    TRANSFORMED = "transformed"

class NodeSignificance(str, Enum):
    PROTAGONIST = "protagonist"
    MAJOR = "major"
    SUPPORTING = "supporting"
    MINOR = "minor"
    MENTIONED = "mentioned"

class RelationType(str, Enum):
    # Social relationships
    FRIEND = "friend"
    ENEMY = "enemy"
    ALLY = "ally"
    RIVAL = "rival"

    # Family relationships
    FAMILY = "family"
    PARENT = "parent"
    CHILD = "child"
    SIBLING = "sibling"
    SPOUSE = "spouse"  # ⭐ CRITICAL: Marriage, political alliances

    # Hierarchical relationships
    MENTOR = "mentor"
    MENTEE = "mentee"
    EMPLOYED_BY = "employed_by"
    LEADS = "leads"
    MEMBER_OF = "member_of"

    # Romantic relationships
    ROMANTIC_INTEREST = "romantic_interest"
    EX_PARTNER = "ex_partner"

    # Story-critical relationships
    BETRAYED = "betrayed"  # ⭐ CRITICAL: Plot betrayals
    OWES_DEBT_TO = "owes_debt_to"
    SAVED_BY = "saved_by"
    KILLED = "killed"

    # Metaphysical relationships
    CREATED_BY = "created_by"  # Clones, magical constructs, AI
    WORSHIPS = "worships"  # Religious dynamics
    BLESSED_BY = "blessed_by"
    CURSED_BY = "cursed_by"

    # Spatial relationships
    LOCATED_IN = "located_in"
    CONNECTED_TO = "connected_to"
    OWNS = "owns"

    # Functional relationships
    HAS_ABILITY = "has_ability"
    REQUIRES = "requires"
    CAUSES = "causes"
    RELATED_TO = "related_to"
    REFERENCES = "references"
    APPEARS_IN = "appears_in"  # Character -> Scene

    @property
    def is_bidirectional(self) -> bool:
        return self in BIDIRECTIONAL_TYPES

BIDIRECTIONAL_TYPES = {
    RelationType.FRIEND,
    RelationType.SIBLING,
    RelationType.SPOUSE,
    RelationType.ALLY,
    RelationType.RIVAL
}

def is_bidirectional(relation_type: RelationType) -> bool:
    return relation_type in BIDIRECTIONAL_TYPES

class CanonLayer(str, Enum):
    PRIMARY = "primary"
    ALTERNATE = "alternate"
    DRAFT = "draft"
    RETCONNED = "retconned"

class CanonStatus(str, Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    PENDING = "pending"

class FactType(str, Enum):
    TRAIT = "trait"
    ABILITY = "ability"
    RELATIONSHIP = "relationship"
    EVENT = "event"
    FEAR = "fear"
    DESIRE = "desire"
    TRAUMA = "trauma"
    MOTIVATION = "motivation"

class ArcType(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    FLAT = "flat"
    CORRUPTION = "corruption"
    REDEMPTION = "redemption"
    DISILLUSIONMENT = "disillusionment"
    COMING_OF_AGE = "coming_of_age"

class AnchorStatus(str, Enum):
    PENDING = "pending"
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    COMPLETED = "completed"

class PacingType(str, Enum):
    SLOW = "slow"
    MEDIUM = "medium"
    FAST = "fast"

class DraftStatus(str, Enum):
    OUTLINE = "outline"
    DRAFT = "draft"
    REVISED = "revised"
    FINAL = "final"

class UserRating(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    
class AgentType(str, Enum):
    PROFILER = "profiler"
    ARCHIVIST = "archivist"
    PSYCHOLOGIST = "psychologist"
    ARCHITECT = "architect"
    DRAMATIST = "dramatist"
    STYLIST = "stylist"
    MECHANIC = "mechanic"
    THEORIST = "theorist"
    NAVIGATOR = "navigator"
    CHRONOLOGIST = "chronologist"
    PRODUCER = "producer"

class ConflictType(str, Enum):
    PERSON_VS_PERSON = "person_vs_person"
    PERSON_VS_SELF = "person_vs_self"
    PERSON_VS_NATURE = "person_vs_nature"
    PERSON_VS_SOCIETY = "person_vs_society"
    PERSON_VS_SUPERNATURAL = "person_vs_supernatural"
    PERSON_VS_TECHNOLOGY = "person_vs_technology"

class ConflictStatus(str, Enum):
    SETUP = "setup"
    INCITING_INCIDENT = "inciting_incident"
    RISING_ACTION = "rising_action"
    CLIMAX = "climax"
    FALLING_ACTION = "falling_action"
    RESOLUTION = "resolution"

class ConflictRole(str, Enum):
    PROTAGONIST = "protagonist"
    ANTAGONIST = "antagonist"
    INSTIGATOR = "instigator"
    BYSTANDER = "bystander"

# ============================================
# QUICK WIN ENUMS (Architectural Improvements)
# ============================================

class SceneOutcomeType(str, Enum):
    """Tracks whether scene goals were achieved."""
    ACHIEVED = "achieved"  # Character got what they wanted
    FAILED = "failed"  # Character did not achieve goal
    SUBVERTED = "subverted"  # Got something unexpected instead
    MODIFIED = "modified"  # Partially achieved or changed during scene
    ABANDONED = "abandoned"  # Goal became irrelevant

class DramaticFunction(str, Enum):
    """Scene's role in overall story structure."""
    EXPOSITION = "exposition"  # Introduces characters/world/setup
    INCITING_INCIDENT = "inciting_incident"  # Kicks off the main story
    RISING_ACTION = "rising_action"  # Builds tension toward climax
    MIDPOINT = "midpoint"  # Major revelation or turning point
    CRISIS = "crisis"  # Character's darkest moment
    CLIMAX = "climax"  # Peak of story tension
    FALLING_ACTION = "falling_action"  # Aftermath of climax
    RESOLUTION = "resolution"  # Ties up loose ends
    DENOUEMENT = "denouement"  # Final reflection/epilogue

class SubplotStatus(str, Enum):
    """Tracks subplot lifecycle."""
    SETUP = "setup"  # Introducing the subplot
    RISING = "rising"  # Building tension in subplot
    CLIMAX = "climax"  # Subplot reaches peak
    RESOLUTION = "resolution"  # Subplot resolved
    ABANDONED = "abandoned"  # Subplot dropped (may be intentional)

class ThreadRole(str, Enum):
    """How much a scene contributes to a plot thread."""
    PRIMARY = "primary"  # Scene primarily about this thread
    SECONDARY = "secondary"  # Scene touches on this thread
    REFERENCE = "reference"  # Brief mention/callback

class GoalLevel(str, Enum):
    """Hierarchy of character goals."""
    STORY_GOAL = "story_goal"  # Overarching goal for entire story
    ACT_GOAL = "act_goal"  # Goal for this act/section
    SCENE_GOAL = "scene_goal"  # Immediate goal in this scene

class GoalStatus(str, Enum):
    """Tracking goal progress."""
    PENDING = "pending"  # Not yet attempted
    IN_PROGRESS = "in_progress"  # Currently being pursued
    ACHIEVED = "achieved"  # Goal accomplished
    FAILED = "failed"  # Goal failed permanently
    ABANDONED = "abandoned"  # Character gave up or goal became irrelevant

# ============================================
# PROVENANCE SYSTEM ENUMS
# ============================================

class StateChangeEventType(str, Enum):
    """Types of state changes that can happen to entities."""
    INVENTORY_ADD = "inventory_add"
    INVENTORY_REMOVE = "inventory_remove"
    LOCATION_MOVE = "location_move"
    STATUS_CHANGE = "status_change"
    HEALTH_CHANGE = "health_change"
    ABILITY_GAIN = "ability_gain"
    ABILITY_LOSS = "ability_loss"
    RELATIONSHIP_CHANGE = "relationship_change"
    ATTRIBUTE_CHANGE = "attribute_change"

class KnowledgeSourceType(str, Enum):
    """How a character learned a piece of information."""
    WITNESSED = "witnessed"  # Saw it firsthand
    TOLD_BY = "told_by"  # Someone told them
    READ = "read"  # Read in a book/letter
    DEDUCED = "deduced"  # Figured it out logically
    DREAMED = "dreamed"  # Vision or prophetic dream
    OVERHEARD = "overheard"  # Eavesdropped
    RUMOR = "rumor"  # Heard through gossip
    UNKNOWN = "unknown"  # Source unclear

class DependencyType(str, Enum):
    """Types of dependencies between content and facts."""
    REFERENCES_EVENT = "references_event"  # Scene references a past event
    ASSUMES_ALIVE = "assumes_alive"  # Assumes character is alive
    ASSUMES_DEAD = "assumes_dead"  # Assumes character is dead
    ASSUMES_LOCATION = "assumes_location"  # Assumes entity is at location
    ASSUMES_RELATIONSHIP = "assumes_relationship"  # Assumes relationship exists
    ASSUMES_KNOWLEDGE = "assumes_knowledge"  # Assumes character knows something
    ASSUMES_POSSESSION = "assumes_possession"  # Assumes character has item
    ASSUMES_ABILITY = "assumes_ability"  # Assumes character has ability

class PresenceType(str, Enum):
    """How an entity is present in a scene."""
    ACTIVE = "active"  # Directly participating
    PASSIVE = "passive"  # Present but not active
    MENTIONED = "mentioned"  # Talked about but not present
    FLASHBACK = "flashback"  # Appears in memory/flashback
    VISION = "vision"  # Appears in dream/vision
    OFFSCREEN = "offscreen"  # Actions happen but not shown

class IngestionSourceType(str, Enum):
    """How data entered the system."""
    MANUAL = "manual"  # User manually entered
    FILE_UPLOAD = "file_upload"  # Uploaded document
    API = "api"  # External API
    INFERENCE = "inference"  # AI inferred from text
    IMPORT = "import"  # Bulk import operation

