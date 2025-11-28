"""
Response formatters for agent outputs.

Converts structured Pydantic models into readable markdown format
instead of using str() which produces ugly repr() strings.
"""

from typing import Any, TYPE_CHECKING

# Import actual extraction models from agent files
if TYPE_CHECKING:
    from writeros.agents.chronologist import TimelineExtraction
    from writeros.agents.psychologist import PsychologyExtraction
    from writeros.agents.profiler import WorldExtractionSchema
    from writeros.agents.theorist import CraftExtractionSchema


class AgentResponseFormatter:
    """
    Converts agent Pydantic outputs to readable markdown.

    Each format_* method handles one agent's structured output type.
    """

    @staticmethod
    def format_timeline(timeline: Any) -> str:
        """Format timeline analysis into markdown."""
        if not timeline:
            return "_No timeline events identified._"

        # Check if it's a Pydantic model with events
        if hasattr(timeline, 'events') and timeline.events:
            lines = ["## Timeline Analysis\n"]
            for event in timeline.events:
                lines.append(f"### {event.title}")
                if hasattr(event, 'timestamp') and event.timestamp:
                    lines.append(f"**When:** {event.timestamp}")
                if hasattr(event, 'summary'):
                    lines.append(f"\n{event.summary}")
                if hasattr(event, 'impact') and event.impact:
                    lines.append(f"\n**Impact:** {event.impact}")
                lines.append("")  # Blank line between events
            return "\n".join(lines)

        # If it's a string, return as-is wrapped in section
        if isinstance(timeline, str):
            return f"## Timeline Analysis\n\n{timeline}"

        return "_No timeline events identified._"

    @staticmethod
    def format_psychology(psychology: Any) -> str:
        """Format psychology analysis into markdown."""
        if not psychology:
            return "_No psychological analysis available._"

        # If it's a string, return wrapped in section
        if isinstance(psychology, str):
            return f"## Psychological Analysis\n\n{psychology}"

        # If it's a Pydantic model with characters
        if hasattr(psychology, 'characters') and psychology.characters:
            lines = ["## Psychological Analysis\n"]
            for char in psychology.characters:
                if hasattr(char, 'name'):
                    lines.append(f"### {char.name}")

                if hasattr(char, 'core_traits') and char.core_traits:
                    lines.append(f"**Core Traits:** {', '.join(char.core_traits)}")

                if hasattr(char, 'motivations') and char.motivations:
                    lines.append("\n**Motivations:**")
                    for motivation in char.motivations:
                        lines.append(f"- {motivation}")

                if hasattr(char, 'arc_stage') and char.arc_stage:
                    lines.append(f"\n**Arc Stage:** {char.arc_stage}")

                lines.append("")  # Blank line
            return "\n".join(lines)

        return "_No psychological analysis available._"

    @staticmethod
    def format_profiler(profile: Any) -> str:
        """Format character profile into markdown."""
        if not profile:
            return "_No character profiles identified._"

        if isinstance(profile, str):
            return f"## Character Profiles\n\n{profile}"

        # If it's a Pydantic model, try to extract data
        if hasattr(profile, 'entities') and profile.entities:
            lines = ["## Character Profiles\n"]
            for entity in profile.entities:
                if hasattr(entity, 'name'):
                    lines.append(f"### {entity.name}")
                if hasattr(entity, 'description') and entity.description:
                    lines.append(f"\n{entity.description}")
                lines.append("")
            return "\n".join(lines)

        return f"## Character Profiles\n\n{str(profile)}"

    @staticmethod
    def format_architect(analysis: Any) -> str:
        """Format architect/plot analysis into markdown."""
        if not analysis:
            return "_No plot analysis available._"

        if isinstance(analysis, str):
            return f"## Plot & Structure Analysis\n\n{analysis}"

        return f"## Plot & Structure Analysis\n\n{str(analysis)}"

    @staticmethod
    def format_dramatist(analysis: Any) -> str:
        """Format dramatic analysis into markdown."""
        if not analysis:
            return "_No dramatic analysis available._"

        if isinstance(analysis, str):
            return f"## Dramatic Analysis\n\n{analysis}"

        return f"## Dramatic Analysis\n\n{str(analysis)}"

    @staticmethod
    def format_mechanic(analysis: Any) -> str:
        """Format mechanic analysis into markdown."""
        if not analysis:
            return "_No mechanics analysis available._"

        if isinstance(analysis, str):
            return f"## Scene Mechanics\n\n{analysis}"

        return f"## Scene Mechanics\n\n{str(analysis)}"

    @staticmethod
    def format_theorist(analysis: Any) -> str:
        """Format thematic analysis into markdown."""
        if not analysis:
            return "_No thematic analysis available._"

        if isinstance(analysis, str):
            return f"## Thematic Analysis\n\n{analysis}"

        # If it's a Pydantic model with craft insights
        if hasattr(analysis, 'themes') and analysis.themes:
            lines = ["## Thematic Analysis\n"]
            for theme in analysis.themes:
                if isinstance(theme, str):
                    lines.append(f"- {theme}")
                elif hasattr(theme, 'theme'):
                    lines.append(f"### {theme.theme}")
                    if hasattr(theme, 'evidence') and theme.evidence:
                        lines.append("\n**Evidence:**")
                        for evidence in theme.evidence:
                            lines.append(f"- {evidence}")
                    lines.append("")
            return "\n".join(lines)

        return f"## Thematic Analysis\n\n{str(analysis)}"

    @staticmethod
    def format_navigator(analysis: Any) -> str:
        """Format navigation/journey analysis into markdown."""
        if not analysis:
            return "_No navigation analysis available._"

        if isinstance(analysis, str):
            return f"## Travel & Journey Analysis\n\n{analysis}"

        return f"## Travel & Journey Analysis\n\n{str(analysis)}"

    @staticmethod
    def format_chronologist(analysis: Any) -> str:
        """Format chronological analysis into markdown."""
        # Chronologist returns same structure as timeline
        return AgentResponseFormatter.format_timeline(analysis)

    @staticmethod
    def format_stylist(critique: Any) -> str:
        """Format stylist/prose critique into markdown."""
        if not critique:
            return "_No style analysis available._"

        # If it's a string, return wrapped
        if isinstance(critique, str):
            return f"## Style Analysis\n\n{critique}"

        # If it's a ProseCritique Pydantic model
        if hasattr(critique, 'general_feedback'):
            lines = ["## Style Analysis\n"]

            if hasattr(critique, 'concepts_applied') and critique.concepts_applied:
                lines.append("### Craft Concepts Applied")
                for concept in critique.concepts_applied:
                    lines.append(f"- {concept}")
                lines.append("")

            if hasattr(critique, 'general_feedback'):
                lines.append(f"### Overall Feedback\n{critique.general_feedback}\n")

            if hasattr(critique, 'line_edits') and critique.line_edits:
                lines.append("### Suggested Edits")
                for edit in critique.line_edits:
                    if hasattr(edit, 'fix') and hasattr(edit, 'reason'):
                        lines.append(f"- {edit.fix}")
                        lines.append(f"  _Reason: {edit.reason}_")
                lines.append("")

            return "\n".join(lines)

        return f"## Style Analysis\n\n{str(critique)}"

    @staticmethod
    def format_generic(analysis: dict) -> str:
        """Fallback formatter for generic agent responses."""
        if isinstance(analysis, str):
            return analysis

        # If it's a dict, try to format nicely
        if isinstance(analysis, dict):
            lines = []
            for key, value in analysis.items():
                lines.append(f"**{key.replace('_', ' ').title()}:** {value}")
            return "\n".join(lines)

        return str(analysis)
