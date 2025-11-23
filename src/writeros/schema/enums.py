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

class RelationType(str, Enum):
    FRIEND = "friend"
    ENEMY = "enemy"
    ALLY = "ally"
    RIVAL = "rival"
    FAMILY = "family"
    PARENT = "parent"
    CHILD = "child"
    SIBLING = "sibling"
    LOCATED_IN = "located_in"
    CONNECTED_TO = "connected_to"
    MEMBER_OF = "member_of"
    LEADS = "leads"
    HAS_ABILITY = "has_ability"
    REQUIRES = "requires"
    CAUSES = "causes"
    RELATED_TO = "related_to"
    REFERENCES = "references"
    APPEARS_IN = "appears_in" # ⭐ NEW: Character -> Scene

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
