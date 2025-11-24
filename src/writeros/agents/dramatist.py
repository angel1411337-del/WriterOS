"""
Dramatist Agent - Tracks emotional beats, pacing, and tension curves
"""
import json
from typing import List, Dict, Any, Optional
from uuid import uuid4
from sqlmodel import Session, select
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from .base import BaseAgent, logger
from writeros.schema import Document
from writeros.utils.db import engine


class DramatistAgent(BaseAgent):
    """Analyzes tension, emotion, and pacing in narrative scenes"""
    
    def __init__(self, model_name="gpt-5.1"):
        super().__init__(model_name)
        self.log.info("dramatist_initialized")
        
        # Genre-specific tension curve templates
        self.genre_templates = {
            "thriller": {"pattern": "rising", "baseline": 6.0, "peak_frequency": "high"},
            "romance": {"pattern": "wave", "baseline": 5.0, "peak_frequency": "medium"},
            "mystery": {"pattern": "gradual", "baseline": 5.5, "peak_frequency": "low"},
            "action": {"pattern": "spikes", "baseline": 7.0, "peak_frequency": "very_high"},
            "drama": {"pattern": "wave", "baseline": 4.5, "peak_frequency": "medium"},
            "horror": {"pattern": "rising", "baseline": 6.5, "peak_frequency": "high"},
        }

    async def run(self, full_text: str, existing_notes: str, title: str, genre: str = "general"):
        """Standard entry point: analyze a single scene for tension and emotion."""
        self.log.info("running_dramatist", title=title)

        scene = Document(
            vault_id=uuid4(),
            title=title,
            content=full_text,
            doc_type="scene",
            metadata_={"notes": existing_notes},
        )

        analyzed_scene = await self.analyze_scene(scene, genre)
        pacing = await self.analyze_pacing([analyzed_scene])
        validation = await self.validate_tension_curve([analyzed_scene], genre)
        visualization = self.visualize_tension_arc([analyzed_scene])

        return {
            "title": title,
            "genre": genre,
            "pacing": pacing,
            "validation": validation,
            "visualization": visualization,
            "scene": analyzed_scene,
        }
    
    async def score_tension(self, scene_text: str, genre: str = "general") -> float:
        """Score scene tension on a 1-10 scale using LLM analysis"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a narrative tension analyst. Score the tension in this scene on a scale of 1-10.

Tension indicators:
- 1-3: Calm, reflective, low stakes
- 4-6: Moderate conflict, building stakes
- 7-8: High stakes, clear danger, urgency
- 9-10: Extreme peril, climactic moments

Consider: conflict, pacing, stakes, danger, urgency, and unresolved questions.

Return ONLY a number between 1.0 and 10.0 (e.g., "7.5")"""),
            ("user", f"Genre: {genre}\n\nScene:\n{scene_text[:2000]}")  # Limit to 2000 chars
        ])
        
        chain = prompt | self.llm | StrOutputParser()
        result = await chain.ainvoke({})
        
        try:
            score = float(result.strip())
            return max(1.0, min(10.0, score))  # Clamp to 1-10
        except ValueError:
            self.log.warning("invalid_tension_score", result=result)
            return 5.0
    
    async def score_emotion(self, scene_text: str) -> float:
        """Score emotional intensity on a 1-10 scale"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an emotional intensity analyst. Score the emotional intensity in this scene on a scale of 1-10.

Emotion indicators:
- 1-3: Subtle emotions, introspection
- 4-6: Moderate emotional engagement
- 7-8: Strong emotions (joy, anger, fear, love)
- 9-10: Overwhelming emotions, cathartic moments

Consider: character reactions, dialogue intensity, internal conflict, and emotional stakes.

Return ONLY a number between 1.0 and 10.0 (e.g., "6.8")"""),
            ("user", f"Scene:\n{scene_text[:2000]}")
        ])
        
        chain = prompt | self.llm | StrOutputParser()
        result = await chain.ainvoke({})
        
        try:
            score = float(result.strip())
            return max(1.0, min(10.0, score))
        except ValueError:
            self.log.warning("invalid_emotion_score", result=result)
            return 5.0
    
    async def analyze_pacing(self, scenes: List[Document]) -> Dict[str, Any]:
        """Analyze pacing rhythm across multiple scenes"""
        if not scenes:
            return {"error": "No scenes provided"}
        
        # Extract tension scores from metadata
        tension_scores = []
        for scene in scenes:
            metadata = scene.metadata_ or {}
            tension = metadata.get("tension", 5.0)
            tension_scores.append(tension)
        
        # Calculate pacing metrics
        avg_tension = sum(tension_scores) / len(tension_scores)
        max_tension = max(tension_scores)
        min_tension = min(tension_scores)
        tension_range = max_tension - min_tension
        
        # Calculate variation (standard deviation)
        variance = sum((t - avg_tension) ** 2 for t in tension_scores) / len(tension_scores)
        std_dev = variance ** 0.5
        
        # Detect rhythm pattern
        rhythm = "steady" if std_dev < 1.5 else "varied" if std_dev < 3.0 else "dramatic"
        
        return {
            "scene_count": len(scenes),
            "average_tension": round(avg_tension, 2),
            "max_tension": round(max_tension, 2),
            "min_tension": round(min_tension, 2),
            "tension_range": round(tension_range, 2),
            "variation": round(std_dev, 2),
            "rhythm": rhythm,
            "scores": [round(t, 2) for t in tension_scores]
        }
    
    async def validate_tension_curve(self, scenes: List[Document], genre: str) -> Dict[str, Any]:
        """Validate whether tension curve matches genre expectations"""
        pacing = await self.analyze_pacing(scenes)
        
        if "error" in pacing:
            return pacing
        
        template = self.genre_templates.get(genre.lower(), self.genre_templates["drama"])
        scores = pacing["scores"]
        
        # Validate based on genre pattern
        issues = []
        strengths = []
        
        # Check baseline
        if pacing["average_tension"] < template["baseline"] - 1.5:
            issues.append(f"Average tension ({pacing['average_tension']}) below expected baseline ({template['baseline']}) for {genre}")
        elif pacing["average_tension"] > template["baseline"] - 0.5:
            strengths.append(f"Tension baseline appropriate for {genre}")
        
        # Check pattern
        if template["pattern"] == "rising":
            # Should trend upward
            if scores[-1] <= scores[0]:
                issues.append("Tension should rise for thriller/horror genres")
            else:
                strengths.append("Rising tension pattern detected")
        
        elif template["pattern"] == "wave":
            # Should have ups and downs
            if pacing["variation"] < 1.5:
                issues.append("Romance/drama needs more emotional variation")
            else:
                strengths.append("Good emotional wave pattern")
        
        # Check for flatness
        if pacing["tension_range"] < 2.0:
            issues.append("Tension curve is too flat - needs more peaks and valleys")
        
        return {
            "genre": genre,
            "pattern": template["pattern"],
            "expected_baseline": template["baseline"],
            "actual_average": pacing["average_tension"],
            "variation": pacing["variation"],
            "issues": issues,
            "strengths": strengths,
            "valid": len(issues) == 0
        }
    
    def visualize_tension_arc(self, scenes: List[Document], width: int = 60) -> str:
        """Create ASCII visualization of tension arc"""
        if not scenes:
            return "No scenes to visualize"
        
        # Extract scores
        scores = []
        labels = []
        for i, scene in enumerate(scenes):
            metadata = scene.metadata_ or {}
            tension = metadata.get("tension", 5.0)
            emotion = metadata.get("emotion", 5.0)
            scores.append((tension, emotion))
            labels.append(f"S{i+1}")
        
        # Build ASCII graph
        lines = []
        lines.append("Tension & Emotion Arc")
        lines.append("=" * width)
        lines.append("")
        
        # Scale: 1-10 mapped to height
        height = 12
        for level in range(10, 0, -1):
            line = f"{level:2d} |"
            
            for tension, emotion in scores:
                if abs(tension - level) < 0.5:
                    line += "T"
                elif abs(emotion - level) < 0.5:
                    line += "e"
                else:
                    line += " "
                line += " "
            
            lines.append(line)
        
        # X-axis
        lines.append("   +" + "-" * (len(scores) * 2))
        label_line = "    "
        for label in labels:
            label_line += f"{label} "
        lines.append(label_line)
        lines.append("")
        lines.append("Legend: T=Tension  e=Emotion")
        
        return "\n".join(lines)
    
    async def analyze_scene(self, scene: Document, genre: str = "general") -> Document:
        """Analyze a scene and update its metadata with scores"""
        self.log.info("analyzing_scene", title=scene.title)
        
        # Score tension and emotion
        tension = await self.score_tension(scene.content, genre)
        emotion = await self.score_emotion(scene.content)
        
        # Update metadata
        if not scene.metadata_:
            scene.metadata_ = {}
        
        scene.metadata_["tension"] = round(tension, 2)
        scene.metadata_["emotion"] = round(emotion, 2)
        scene.metadata_["analyzed_by"] = "dramatist"
        
        self.log.info("scene_analyzed", tension=tension, emotion=emotion)
        
        return scene
    
    async def analyze_chapter(self, chapter_scenes: List[Document], genre: str = "general") -> Dict[str, Any]:
        """Comprehensive analysis of a chapter's scenes"""
        self.log.info("analyzing_chapter", scene_count=len(chapter_scenes))
        
        # Analyze each scene
        analyzed_scenes = []
        for scene in chapter_scenes:
            analyzed = await self.analyze_scene(scene, genre)
            analyzed_scenes.append(analyzed)
        
        # Get pacing analysis
        pacing = await self.analyze_pacing(analyzed_scenes)
        
        # Validate tension curve
        validation = await self.validate_tension_curve(analyzed_scenes, genre)
        
        # Generate visualization
        visualization = self.visualize_tension_arc(analyzed_scenes)
        
        return {
            "scenes_analyzed": len(analyzed_scenes),
            "pacing": pacing,
            "validation": validation,
            "visualization": visualization,
        }