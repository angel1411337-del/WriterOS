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

        # Check if it's a Pydantic model with events (TimelineExtraction)
        if hasattr(timeline, 'events'):
            lines = ["## Timeline Analysis\n"]

            # Add continuity notes if present
            if hasattr(timeline, 'continuity_notes') and timeline.continuity_notes:
                lines.append(f"**Continuity Notes:** {timeline.continuity_notes}\n")

            # Format events
            if timeline.events:
                for i, event in enumerate(timeline.events, 1):
                    # Add event number and title
                    title = getattr(event, 'title', f'Event {i}')
                    lines.append(f"### {i}. {title}")

                    # Add timestamp if present
                    if hasattr(event, 'timestamp') and event.timestamp:
                        lines.append(f"**When:** {event.timestamp}")

                    # Add order if present
                    if hasattr(event, 'order'):
                        lines.append(f"**Order:** {event.order}")

                    # Add summary
                    if hasattr(event, 'summary') and event.summary:
                        lines.append(f"\n{event.summary}")

                    # Add impact if present
                    if hasattr(event, 'impact') and event.impact:
                        lines.append(f"\n**Impact:** {event.impact}")

                    lines.append("")  # Blank line between events
            else:
                lines.append("_No events found in this timeline._")

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

        # If it's a Pydantic model with profiles (PsychologyExtraction)
        if hasattr(psychology, 'profiles') and psychology.profiles:
            lines = ["## Psychological Analysis\n"]
            for profile in psychology.profiles:
                if hasattr(profile, 'name'):
                    lines.append(f"### {profile.name}")

                if hasattr(profile, 'archetype') and profile.archetype:
                    lines.append(f"**Archetype:** {profile.archetype}")

                if hasattr(profile, 'moral_alignment') and profile.moral_alignment:
                    lines.append(f"**Moral Alignment:** {profile.moral_alignment}")

                if hasattr(profile, 'core_desire') and profile.core_desire:
                    lines.append(f"\n**Core Desire:** {profile.core_desire}")

                if hasattr(profile, 'core_fear') and profile.core_fear:
                    lines.append(f"\n**Core Fear:** {profile.core_fear}")

                if hasattr(profile, 'lie_believed') and profile.lie_believed:
                    lines.append(f"\n**Lie Believed:** {profile.lie_believed}")

                if hasattr(profile, 'truth_to_learn') and profile.truth_to_learn:
                    lines.append(f"\n**Truth to Learn:** {profile.truth_to_learn}")

                if hasattr(profile, 'active_wounds') and profile.active_wounds:
                    lines.append("\n**Active Wounds:**")
                    for wound in profile.active_wounds:
                        lines.append(f"- {wound}")

                if hasattr(profile, 'decision_making_style') and profile.decision_making_style:
                    lines.append(f"\n**Decision-Making Style:** {profile.decision_making_style}")

                lines.append("")  # Blank line
            return "\n".join(lines)

        # Backwards compatibility: If it's a Pydantic model with characters
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
        """
        Format character profile into markdown.

        Design Decision: Extract structured data from WorldExtractionSchema instead of dumping raw objects.

        Reasoning:
        - Profiler returns WorldExtractionSchema with characters/organizations/locations
        - Need to extract and format each type properly
        - Avoid str(profile) which creates blob: "WorldExtractionSchema(characters=[...])"
        """
        if not profile:
            return "_No character profiles identified._"

        if isinstance(profile, str):
            return f"## Character Profiles\n\n{profile}"

        # Handle WorldExtractionSchema (from ProfilerAgent)
        lines = ["## Character Profiles\n"]

        # Extract characters
        if hasattr(profile, 'characters') and profile.characters:
            for char in profile.characters:
                lines.append(f"### {char.name}")
                if hasattr(char, 'role'):
                    lines.append(f"**Role:** {char.role}")

                # Visual traits
                if hasattr(char, 'visual_traits') and char.visual_traits:
                    lines.append("\n**Appearance:**")
                    for trait in char.visual_traits:
                        lines.append(f"- {trait.feature}: {trait.description}")

                # Relationships
                if hasattr(char, 'relationships') and char.relationships:
                    lines.append("\n**Relationships:**")
                    for rel in char.relationships:
                        detail = f" ({rel.details})" if hasattr(rel, 'details') and rel.details else ""
                        lines.append(f"- {rel.target} ({rel.rel_type}){detail}")

                lines.append("")

        # Extract organizations
        if hasattr(profile, 'organizations') and profile.organizations:
            lines.append("\n## Organizations\n")
            for org in profile.organizations:
                lines.append(f"### {org.name}")
                if hasattr(org, 'org_type'):
                    lines.append(f"**Type:** {org.org_type}")
                if hasattr(org, 'leader') and org.leader:
                    lines.append(f"**Leader:** {org.leader}")
                if hasattr(org, 'ideology'):
                    lines.append(f"**Ideology:** {org.ideology}")
                lines.append("")

        # Extract locations
        if hasattr(profile, 'locations') and profile.locations:
            lines.append("\n## Locations\n")
            for loc in profile.locations:
                lines.append(f"### {loc.name}")
                if hasattr(loc, 'geography'):
                    lines.append(f"**Geography:** {loc.geography}")
                if hasattr(loc, 'visual_signature'):
                    lines.append(f"**Appearance:** {loc.visual_signature}")
                lines.append("")

        # If nothing was extracted, return simple message
        if len(lines) == 1:  # Only header
            return "_No character profiles identified._"

        return "\n".join(lines)

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
            # Agent already returns markdown, just ensure proper header level
            text = analysis.strip()
            # If text already has headers, adjust them to be subsections
            if text.startswith('##'):
                text = text.replace('##', '###', 1)  # Make first header h3
            elif not text.startswith('#'):
                # No headers, add a main header
                text = f"## Dramatic Analysis\n\n{text}"
            return text

        # If it's a dict (from DramatistAgent.run())
        if isinstance(analysis, dict):
            lines = ["## Dramatic Analysis\n"]

            # Add pacing info
            if 'pacing' in analysis and analysis['pacing']:
                pacing = analysis['pacing']
                lines.append("### Pacing")
                lines.append(f"**Average Tension:** {pacing.get('average_tension', 'N/A')}/10")
                lines.append(f"**Tension Range:** {pacing.get('tension_range', 'N/A')}")
                lines.append(f"**Rhythm:** {pacing.get('rhythm', 'N/A')}")
                lines.append("")

            # Add validation insights
            if 'validation' in analysis and analysis['validation']:
                validation = analysis['validation']
                lines.append("### Analysis")
                if validation.get('strengths'):
                    lines.append("**Strengths:**")
                    for strength in validation['strengths']:
                        lines.append(f"- {strength}")
                if validation.get('issues'):
                    lines.append("\n**Areas for Improvement:**")
                    for issue in validation['issues']:
                        lines.append(f"- {issue}")
                lines.append("")

            # Add visualization if available
            if 'visualization' in analysis and analysis['visualization']:
                lines.append("### Tension Curve")
                lines.append("```")
                lines.append(analysis['visualization'])
                lines.append("```")

            return "\n".join(lines)

        return f"## Dramatic Analysis\n\n{str(analysis)}"

    @staticmethod
    def format_mechanic(analysis: Any) -> str:
        """Format mechanic analysis into markdown."""
        if not analysis:
            return "_No mechanics analysis available._"

        if isinstance(analysis, str):
            # Agent already returns markdown, just ensure proper header level
            text = analysis.strip()
            # If text already has headers, adjust them to be subsections
            if text.startswith('##'):
                text = text.replace('##', '###', 1)  # Make first header h3
            elif not text.startswith('#'):
                # No headers, add a main header
                text = f"## Scene Mechanics\n\n{text}"
            return text

        # If it's a Pydantic model (MechanicOutput)
        if hasattr(analysis, 'verdict') and hasattr(analysis, 'reasoning'):
            lines = ["## Scene Mechanics\n"]

            # Add verdict
            verdict = getattr(analysis, 'verdict', None)
            if verdict:
                lines.append(f"### Verdict: {verdict}")

            # Add reasoning
            reasoning = getattr(analysis, 'reasoning', None)
            if reasoning:
                lines.append(f"\n{reasoning}\n")

            # Add confidence
            confidence = getattr(analysis, 'confidence', None)
            if confidence:
                lines.append(f"**Confidence:** {confidence}")

            # Add rules checked
            if hasattr(analysis, 'rules_checked') and analysis.rules_checked:
                lines.append("\n### Rules Checked")
                for rule in analysis.rules_checked:
                    status = "✓" if getattr(rule, 'passes', True) else "✗"
                    rule_name = getattr(rule, 'rule_name', 'Unknown')
                    lines.append(f"- {status} {rule_name}")
                    if hasattr(rule, 'details') and rule.details:
                        lines.append(f"  _{rule.details}_")

            return "\n".join(lines)

        return f"## Scene Mechanics\n\n{str(analysis)}"

    @staticmethod
    def format_theorist(analysis: Any) -> str:
        """Format thematic analysis into markdown."""
        if not analysis:
            return "_No thematic analysis available._"

        if isinstance(analysis, str):
            # Agent already returns markdown, just ensure proper header level
            text = analysis.strip()
            # If text already has headers, adjust them to be subsections
            if text.startswith('##'):
                text = text.replace('##', '###', 1)  # Make first header h3
            elif not text.startswith('#'):
                # No headers, add a main header
                text = f"## Thematic Analysis\n\n{text}"
            return text

        # If it's a CraftExtractionSchema model
        if hasattr(analysis, 'concepts') or hasattr(analysis, 'techniques') or hasattr(analysis, 'pitfalls'):
            lines = ["## Thematic Analysis\n"]

            # Format writing concepts
            if hasattr(analysis, 'concepts') and analysis.concepts:
                lines.append("### Writing Concepts")
                for concept in analysis.concepts:
                    lines.append(f"\n**{concept.name}** ({concept.genre_context})")
                    if hasattr(concept, 'definition'):
                        lines.append(f"{concept.definition}")
                    if hasattr(concept, 'why_it_matters'):
                        lines.append(f"\n_Why it matters:_ {concept.why_it_matters}")
                    if hasattr(concept, 'examples_mentioned') and concept.examples_mentioned:
                        lines.append(f"_Examples:_ {', '.join(concept.examples_mentioned)}")
                lines.append("")

            # Format actionable techniques
            if hasattr(analysis, 'techniques') and analysis.techniques:
                lines.append("### Techniques")
                for technique in analysis.techniques:
                    lines.append(f"\n**{technique.name}** ({technique.genre_context})")
                    if hasattr(technique, 'when_to_use'):
                        lines.append(f"_{technique.when_to_use}_")
                    if hasattr(technique, 'steps') and technique.steps:
                        lines.append("\nSteps:")
                        for i, step in enumerate(technique.steps, 1):
                            lines.append(f"{i}. {step}")
                lines.append("")

            # Format pitfalls
            if hasattr(analysis, 'pitfalls') and analysis.pitfalls:
                lines.append("### Common Pitfalls")
                for pitfall in analysis.pitfalls:
                    lines.append(f"\n**{pitfall.name}** ({pitfall.genre_context})")
                    if hasattr(pitfall, 'why_it_fails'):
                        lines.append(f"_Problem:_ {pitfall.why_it_fails}")
                    if hasattr(pitfall, 'fix_strategy'):
                        lines.append(f"_Solution:_ {pitfall.fix_strategy}")
                lines.append("")

            return "\n".join(lines)

        # Legacy support: If it's a model with themes
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
