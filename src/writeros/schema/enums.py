from enum import Enum

class EntityType(str, Enum):
    CHARACTER = "character"
    LOCATION = "location"
    FACTION = "faction"
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
