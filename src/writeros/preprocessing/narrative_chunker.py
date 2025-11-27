"""
Narrative Chunker - Fiction-optimized chunking for WriterOS.

Preserves:
- Scene boundaries (author's structural markers)
- Dialogue exchanges (character interactions)
- Chronological order (narrative flow)
- Paragraph boundaries (natural units)

NEVER:
- Splits mid-sentence
- Splits mid-dialogue exchange
- Reorders content by semantic similarity
- Groups content from different scenes
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import re
import hashlib
from writeros.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Scene:
    """Represents a narrative scene with position tracking."""
    content: str
    line_start: int
    line_end: int
    char_start: int
    char_end: int
    scene_index: int


@dataclass
class NarrativeBlock:
    """Narrative unit that should stay together."""
    text: str
    block_type: str  # 'dialogue_exchange', 'paragraph', 'action_sequence'
    para_start: int
    para_end: int


@dataclass
class RawChunk:
    """Chunk with narrative metadata."""
    content: str
    file_path: str
    line_start: int
    line_end: int
    char_start: int
    char_end: int
    chunk_index: int
    scene_index: int
    section_type: Optional[str] = None
    has_overlap: bool = False

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode()).hexdigest()[:16]


class NarrativeChunker:
    """
    Fiction-optimized chunking.

    Priority order:
    1. Scene breaks (explicit author markers)
    2. Dialogue exchange boundaries
    3. Paragraph boundaries
    4. Sentence boundaries (last resort)
    """

    def __init__(
        self,
        target_tokens: int = 400,
        max_tokens: int = 800,
        min_tokens: int = 100,
        overlap_sentences: int = 2,
        scene_markers: Optional[List[str]] = None,
    ):
        self.target_tokens = target_tokens
        self.max_tokens = max_tokens
        self.min_tokens = min_tokens
        self.overlap_sentences = overlap_sentences
        self.scene_markers = scene_markers or [
            r"^###\s*$",           # ###
            r"^\*\s*\*\s*\*\s*$",  # * * *
            r"^---\s*$",           # ---
            r"^~~~\s*$",           # ~~~
            r"^#\s+Chapter",       # # Chapter X
            r"^##\s+Scene",        # ## Scene X
        ]

    async def chunk_text_async(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Async interface for compatibility with UnifiedChunker.

        Returns chunks in UnifiedChunker format: [{"text": "...", "metadata": {...}}]
        """
        metadata = metadata or {}
        file_path = metadata.get("file_path", "unknown")

        raw_chunks = self.chunk_file(
            content=text,
            file_path=file_path,
        )

        # Convert to UnifiedChunker format
        result = []
        for chunk in raw_chunks:
            result.append({
                "text": chunk.content,
                "metadata": {
                    **metadata,
                    "chunk_index": chunk.chunk_index,
                    "scene_index": chunk.scene_index,
                    "section_type": chunk.section_type,
                    "has_overlap": chunk.has_overlap,
                    "line_start": chunk.line_start,
                    "line_end": chunk.line_end,
                    "char_start": chunk.char_start,
                    "char_end": chunk.char_end,
                }
            })

        logger.info(
            "narrative_chunking_complete",
            num_chunks=len(result),
            num_scenes=len(set(c.scene_index for c in raw_chunks)),
        )

        return result

    def chunk_file(
        self,
        content: str,
        file_path: str,
    ) -> List[RawChunk]:
        """
        Main entry point. Chunks a manuscript file.
        """

        # 1. Split into scenes (respecting author's structure)
        scenes = self._split_into_scenes(content)

        chunks = []
        chunk_index = 0

        for scene in scenes:
            # 2. Chunk each scene independently
            scene_chunks = self._chunk_scene(
                scene=scene,
                file_path=file_path,
                start_index=chunk_index,
            )

            chunks.extend(scene_chunks)
            chunk_index += len(scene_chunks)

        # 3. Add overlap for context continuity
        chunks = self._add_overlap(chunks)

        return chunks

    def _split_into_scenes(self, content: str) -> List[Scene]:
        """
        Split on scene markers while tracking positions.
        """

        lines = content.split('\n')
        scenes = []

        current_scene_lines = []
        current_scene_start = 0
        current_char_pos = 0
        scene_char_start = 0
        scene_index = 0

        for line_num, line in enumerate(lines):
            is_scene_break = any(
                re.match(pattern, line.strip())
                for pattern in self.scene_markers
            )

            if is_scene_break and current_scene_lines:
                # Save current scene
                scenes.append(Scene(
                    content='\n'.join(current_scene_lines),
                    line_start=current_scene_start,
                    line_end=line_num - 1,
                    char_start=scene_char_start,
                    char_end=current_char_pos - 1,
                    scene_index=scene_index,
                ))
                scene_index += 1

                # Start new scene after the marker
                current_scene_lines = []
                current_scene_start = line_num + 1
                scene_char_start = current_char_pos + len(line) + 1

            elif not is_scene_break:
                current_scene_lines.append(line)

            current_char_pos += len(line) + 1  # +1 for newline

        # Don't forget the last scene
        if current_scene_lines:
            scenes.append(Scene(
                content='\n'.join(current_scene_lines),
                line_start=current_scene_start,
                line_end=len(lines) - 1,
                char_start=scene_char_start,
                char_end=current_char_pos,
                scene_index=scene_index,
            ))

        # If no scenes found, treat entire content as one scene
        if not scenes:
            scenes.append(Scene(
                content=content,
                line_start=0,
                line_end=len(lines) - 1,
                char_start=0,
                char_end=len(content),
                scene_index=0,
            ))

        return scenes

    def _chunk_scene(
        self,
        scene: Scene,
        file_path: str,
        start_index: int,
    ) -> List[RawChunk]:
        """
        Chunk a single scene. Never crosses scene boundaries.
        """

        scene_tokens = self._count_tokens(scene.content)

        # Scene fits in one chunk - keep it together
        if scene_tokens <= self.max_tokens:
            return [RawChunk(
                content=scene.content.strip(),
                file_path=file_path,
                line_start=scene.line_start,
                line_end=scene.line_end,
                char_start=scene.char_start,
                char_end=scene.char_end,
                chunk_index=start_index,
                scene_index=scene.scene_index,
                section_type=self._detect_section_type(scene.content),
            )]

        # Scene too long - split on dialogue/paragraph boundaries
        return self._split_long_scene(scene, file_path, start_index)

    def _split_long_scene(
        self,
        scene: Scene,
        file_path: str,
        start_index: int,
    ) -> List[RawChunk]:
        """
        Split a long scene while respecting narrative structure.

        Priority:
        1. Keep dialogue exchanges together
        2. Split on paragraph boundaries
        3. Split on sentence boundaries (last resort)
        """

        # Identify dialogue exchanges
        blocks = self._identify_narrative_blocks(scene.content)

        chunks = []
        current_blocks = []
        current_tokens = 0
        chunk_index = start_index

        for block in blocks:
            block_tokens = self._count_tokens(block.text)

            # Single block exceeds max - must split it
            if block_tokens > self.max_tokens:
                # Flush current
                if current_blocks:
                    chunks.append(self._blocks_to_chunk(
                        blocks=current_blocks,
                        scene=scene,
                        file_path=file_path,
                        chunk_index=chunk_index,
                    ))
                    chunk_index += 1
                    current_blocks = []
                    current_tokens = 0

                # Split the oversized block
                sub_chunks = self._split_block_by_sentences(
                    block, scene, file_path, chunk_index
                )
                chunks.extend(sub_chunks)
                chunk_index += len(sub_chunks)
                continue

            # Would adding this block exceed target?
            if current_tokens + block_tokens > self.target_tokens and current_blocks:
                # Flush current chunk
                chunks.append(self._blocks_to_chunk(
                    blocks=current_blocks,
                    scene=scene,
                    file_path=file_path,
                    chunk_index=chunk_index,
                ))
                chunk_index += 1
                current_blocks = []
                current_tokens = 0

            current_blocks.append(block)
            current_tokens += block_tokens

        # Flush remaining
        if current_blocks:
            chunks.append(self._blocks_to_chunk(
                blocks=current_blocks,
                scene=scene,
                file_path=file_path,
                chunk_index=chunk_index,
            ))

        return chunks

    def _identify_narrative_blocks(self, content: str) -> List[NarrativeBlock]:
        """
        Identify narrative units that should stay together.

        Types:
        - DIALOGUE_EXCHANGE: Multiple lines of dialogue between characters
        - PARAGRAPH: Narrative paragraph
        """

        blocks = []
        paragraphs = content.split('\n\n')

        i = 0
        while i < len(paragraphs):
            para = paragraphs[i].strip()

            if not para:
                i += 1
                continue

            # Check if this starts a dialogue exchange
            if self._is_dialogue(para):
                # Collect the full exchange
                exchange_paras = [para]
                j = i + 1

                while j < len(paragraphs):
                    next_para = paragraphs[j].strip()
                    if self._is_dialogue(next_para) or self._is_dialogue_continuation(next_para):
                        exchange_paras.append(next_para)
                        j += 1
                    else:
                        break

                blocks.append(NarrativeBlock(
                    text='\n\n'.join(exchange_paras),
                    block_type='dialogue_exchange',
                    para_start=i,
                    para_end=j - 1,
                ))
                i = j
            else:
                # Regular paragraph
                blocks.append(NarrativeBlock(
                    text=para,
                    block_type='paragraph',
                    para_start=i,
                    para_end=i,
                ))
                i += 1

        return blocks

    def _is_dialogue(self, text: str) -> bool:
        """Check if paragraph contains dialogue."""
        dialogue_patterns = [
            r'^["\'"]',  # Starts with quote
            r'"\s*(said|asked|replied|whispered|shouted|muttered)',
            r'(said|asked|replied)\s+\w+[,.]?\s*"',
        ]
        return any(re.search(p, text) for p in dialogue_patterns)

    def _is_dialogue_continuation(self, text: str) -> bool:
        """Check if this continues a dialogue exchange (dialogue tag or beat)."""
        # Short paragraph following dialogue, often action/reaction
        return len(text.split()) < 30

    def _blocks_to_chunk(
        self,
        blocks: List[NarrativeBlock],
        scene: Scene,
        file_path: str,
        chunk_index: int,
    ) -> RawChunk:
        """Convert narrative blocks to a chunk."""
        content = '\n\n'.join(block.text for block in blocks)

        return RawChunk(
            content=content,
            file_path=file_path,
            line_start=scene.line_start,
            line_end=scene.line_end,
            char_start=scene.char_start,
            char_end=scene.char_end,
            chunk_index=chunk_index,
            scene_index=scene.scene_index,
            section_type=self._detect_section_type(content),
        )

    def _split_block_by_sentences(
        self,
        block: NarrativeBlock,
        scene: Scene,
        file_path: str,
        start_index: int,
    ) -> List[RawChunk]:
        """Split an oversized block by sentences (last resort)."""
        sentences = re.split(r'(?<=[.!?])\s+', block.text)

        chunks = []
        current_sentences = []
        current_tokens = 0
        chunk_index = start_index

        for sentence in sentences:
            sent_tokens = self._count_tokens(sentence)

            if current_tokens + sent_tokens > self.target_tokens and current_sentences:
                # Flush current
                chunks.append(RawChunk(
                    content=' '.join(current_sentences),
                    file_path=file_path,
                    line_start=scene.line_start,
                    line_end=scene.line_end,
                    char_start=scene.char_start,
                    char_end=scene.char_end,
                    chunk_index=chunk_index,
                    scene_index=scene.scene_index,
                    section_type=self._detect_section_type(' '.join(current_sentences)),
                ))
                chunk_index += 1
                current_sentences = []
                current_tokens = 0

            current_sentences.append(sentence)
            current_tokens += sent_tokens

        # Flush remaining
        if current_sentences:
            chunks.append(RawChunk(
                content=' '.join(current_sentences),
                file_path=file_path,
                line_start=scene.line_start,
                line_end=scene.line_end,
                char_start=scene.char_start,
                char_end=scene.char_end,
                chunk_index=chunk_index,
                scene_index=scene.scene_index,
                section_type=self._detect_section_type(' '.join(current_sentences)),
            ))

        return chunks

    def _add_overlap(self, chunks: List[RawChunk]) -> List[RawChunk]:
        """
        Add sentence overlap between chunks for context continuity.
        """

        if self.overlap_sentences == 0:
            return chunks

        for i in range(1, len(chunks)):
            prev_chunk = chunks[i - 1]
            curr_chunk = chunks[i]

            # Only add overlap within same scene
            if prev_chunk.scene_index != curr_chunk.scene_index:
                continue

            # Get last N sentences from previous chunk
            prev_sentences = self._get_last_sentences(
                prev_chunk.content,
                self.overlap_sentences
            )

            if prev_sentences:
                # Prepend to current chunk with marker
                curr_chunk.content = f"[...] {prev_sentences}\n\n{curr_chunk.content}"
                curr_chunk.has_overlap = True

        return chunks

    def _get_last_sentences(self, text: str, n: int) -> str:
        """Extract last N sentences from text."""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        if len(sentences) <= n:
            return ""
        return ' '.join(sentences[-n:])

    def _detect_section_type(self, content: str) -> str:
        """Detect the type of narrative section."""

        dialogue_ratio = len(re.findall(r'["\'"]', content)) / max(len(content), 1)

        if dialogue_ratio > 0.05:
            return "dialogue"
        elif re.search(r'(remembered|recalled|years ago|back when)', content, re.I):
            return "flashback"
        elif re.search(r'(dear \w+|sincerely|yours truly)', content, re.I):
            return "letter"
        else:
            return "narrative"

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        try:
            import tiktoken
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except ImportError:
            # Fallback to word count approximation
            return len(text.split()) * 1.3  # Rough approximation
