import os
import sys
import re
import datetime
import logging
import asyncio
import json
import isodate
import argparse
from typing import List, Optional, Dict, Any
from pathlib import Path

# Third-party imports
import yt_dlp
import cv2
from openai import OpenAI as OpenAIClient
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi

# LangChain Imports
from langchain_core.documents import Document

# --- IMPORT THE SWARM ---
from agents import AgentSwarm

# --- Setup & Config ---
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OBSIDIAN_VAULT_PATH = Path(os.getenv("OBSIDIAN_VAULT_PATH", "./output"))
AUDIO_MODEL = "whisper-1"

if not YOUTUBE_API_KEY or not OPENAI_API_KEY:
    logger.error("❌ API Keys missing in .env file")

# --- Core Components ---

class YouTubeAPI:
    def __init__(self, api_key):
        self.youtube = build('youtube', 'v3', developerKey=api_key)

    def extract_video_id(self, url: str) -> str:
        patterns = [
            r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
            r"(?:youtu\.be\/)([0-9A-Za-z_-]{11})",
            r"(?:embed\/)([0-9A-Za-z_-]{11})",
            r"(?:shorts\/)([0-9A-Za-z_-]{11})"
        ]
        for regex in patterns:
            match = re.search(regex, url)
            if match:
                return match.group(1)
        raise ValueError(f"Could not extract Video ID from URL: {url}")

    def get_metadata(self, video_id: str) -> Dict:
        try:
            request = self.youtube.videos().list(part="snippet,contentDetails", id=video_id)
            response = request.execute()
            if not response['items']: raise ValueError("Video not found")
            item = response['items'][0]
            duration_sec = int(isodate.parse_duration(item['contentDetails'].get('duration', 'PT0S')).total_seconds())
            return {
                "video_id": video_id,
                "title": item['snippet']['title'],
                "channel_title": item['snippet']['channelTitle'],
                "published_at": item['snippet']['publishedAt'],
                "thumbnail_url": item['snippet']['thumbnails'].get('high', {}).get('url'),
                "duration_formatted": str(datetime.timedelta(seconds=duration_sec)),
                "description": item['snippet']['description']
            }
        except HttpError as e:
            logger.error(f"YouTube API Error: {e}")
            return {"video_id": video_id, "title": "Unknown Video", "description": ""}

class ProcessingEngine:
    def __init__(self):
        self.audio_client = OpenAIClient(api_key=OPENAI_API_KEY)

    def _download_audio_fallback(self, video_id: str) -> Optional[str]:
        logger.info("⬇️ Downloading audio for transcription (Fallback)...")
        temp_filename = f"temp_{video_id}"
        ffmpeg_local = os.path.join(os.getcwd(), "ffmpeg.exe")

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': temp_filename,
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '32'}],
            'postprocessor_args': ['-ac', '1'],
            'quiet': True,
        }
        if os.path.exists(ffmpeg_local):
            ydl_opts['ffmpeg_location'] = os.getcwd()

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
            final_path = f"{temp_filename}.mp3"
            if os.path.exists(final_path):
                return final_path
            return None
        except Exception as e:
            logger.error(f"Audio download failed: {e}")
            return None

    def _transcribe_audio(self, audio_path: str) -> List[Dict]:
        logger.info(f"🎙️ Transcribing audio with {AUDIO_MODEL}...")
        try:
            with open(audio_path, "rb") as audio_file:
                transcript = self.audio_client.audio.transcriptions.create(
                    model=AUDIO_MODEL, file=audio_file, response_format="verbose_json", timestamp_granularities=["segment"]
                )
            return [{"text": s.text, "start": s.start} for s in transcript.segments]
        except Exception:
            return []
        finally:
            if os.path.exists(audio_path): os.remove(audio_path)

    def get_transcript(self, video_id: str) -> str:
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            try: t = transcript_list.find_manually_created_transcript(['en'])
            except:
                try: t = transcript_list.find_generated_transcript(['en'])
                except: t = transcript_list.find_transcript(['en'])
            data = t.fetch()
            return " ".join([i['text'] for i in data])
        except Exception:
            logger.warning(f"⚠️ Transcript API failed. Engaging Audio Fallback...")
            audio_path = self._download_audio_fallback(video_id)
            if audio_path:
                data = self._transcribe_audio(audio_path)
                return " ".join([i['text'] for i in data])
            return ""

# --- Obsidian Writer ---

class ObsidianWriter:
    def __init__(self, vault_path: Path):
        self.vault_path = vault_path
        self.dirs = {
            "craft": self.vault_path / "Writing_Bible",
            "chars": self.vault_path / "Story_Bible" / "Characters",
            "locs": self.vault_path / "Story_Bible" / "Locations",
            "orgs": self.vault_path / "Story_Bible" / "Organizations",
            "systems": self.vault_path / "Story_Bible" / "Systems",
        }
        for d in self.dirs.values():
            d.mkdir(parents=True, exist_ok=True)

        self.history_file = self.vault_path / "processed_videos.json"
        self.processed_ids = self._load_history()

    def _load_history(self) -> List[str]:
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f: return json.load(f)
            except: return []
        return []

    def mark_as_processed(self, video_id: str):
        if video_id not in self.processed_ids:
            self.processed_ids.append(video_id)
            with open(self.history_file, 'w') as f: json.dump(self.processed_ids, f)

    def is_processed(self, video_id: str) -> bool:
        return video_id in self.processed_ids

    def _sanitize(self, title: str) -> str:
        return re.sub(r'[<>:"/\\|?*]', '', title)[:100].strip()

    def get_existing_notes(self) -> str:
        existing = []
        for root, dirs, files in os.walk(self.vault_path):
            for file in files:
                if file.endswith(".md"): existing.append(file[:-3])
        return ", ".join(existing[:500])

    def update_craft_bible(self, craft_data, url, title):
        if not craft_data: return
        for c in craft_data.concepts:
            path = self.dirs['craft'] / c.genre_context / "Concepts" / f"{self._sanitize(c.name)}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            content = f"# {c.name}\n\n> [!tip] Definition\n> {c.definition}\n\n**Why it matters:** {c.why_it_matters}\n"
            with open(path, 'w', encoding='utf-8') as f: f.write(content)

        for t in craft_data.techniques:
            path = self.dirs['craft'] / t.genre_context / "Techniques" / f"{self._sanitize(t.name)}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            content = f"# {t.name}\n\n> [!abstract] Context\n> {t.when_to_use}\n\n### Steps\n" + "\n".join([f"1. {s}" for s in t.steps])
            with open(path, 'w', encoding='utf-8') as f: f.write(content)

        for p in craft_data.pitfalls:
            path = self.dirs['craft'] / p.genre_context / "Pitfalls" / f"{self._sanitize(p.name)}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            content = f"# {p.name}\n\n> [!failure] Trap\n> {p.why_it_fails}\n\n**Fix:** {p.fix_strategy}\n"
            with open(path, 'w', encoding='utf-8') as f: f.write(content)

    def update_story_bible(self, story_data, source_title):
        if not story_data: return

        # 1. Characters
        for char in story_data.characters:
            path = self.dirs['chars'] / f"{self._sanitize(char.name)}.md"
            visuals = "\n".join([f"| **{t.feature}** | {t.description} |" for t in char.visual_traits]) if char.visual_traits else "_No visual data._"

            # --- 🕸️ NEW GRAPH LOGIC (V2) ---
            mermaid_lines = []
            if hasattr(char, 'relationships') and char.relationships:
                for r in char.relationships:
                    # Handle Pydantic object (V2)
                    if hasattr(r, 'target'):
                        target = r.target.replace(" ", "_")
                        source = char.name.replace(" ", "_")
                        rel_type = r.rel_type.lower() if r.rel_type else "related"

                        # Family = Thick Line (==>)
                        if rel_type in ["parent", "sibling", "child", "spouse", "mother", "father", "son", "daughter"]:
                            arrow = f"{source} =={r.rel_type}==> {target}"
                        # Enemy = Dotted Line (-.->)
                        elif rel_type in ["enemy", "rival", "nemesis"]:
                            arrow = f"{source} -. {r.rel_type} .-> {target}"
                        # Default = Normal Line (-->)
                        else:
                            arrow = f"{source} --{r.rel_type}--> {target}"

                        mermaid_lines.append(f"    {arrow}")
                    # Handle old string format
                    elif isinstance(r, str):
                        target = r.replace(" ", "_")
                        source = char.name.replace(" ", "_")
                        mermaid_lines.append(f"    {source} --> {target}")

            mermaid = ""
            if mermaid_lines:
                mermaid = "```mermaid\ngraph TD;\n" + "\n".join(mermaid_lines) + "\n```"
            # ---------------------------

            if not path.exists():
                template = f"""---
tags: [Character, Status/Unknown]
aliases: []
---
# {char.name}

> [!infobox]
> | | |
> |---|---|
> | **Role** | {char.role} |
> | **Source** | [[{source_title}]] |

## 🧬 Visual Profile
| Feature | Description |
|---|---|
{visuals}

## 🕸️ Relationships
{mermaid}

## 🧠 Psychology
*(Run the Psychologist Agent to populate this)*
"""
                with open(path, 'w', encoding='utf-8') as f: f.write(template)

        # 2. Organizations
        for org in story_data.organizations:
            path = self.dirs['orgs'] / f"{self._sanitize(org.name)}.md"
            if not path.exists():
                content = f"# {org.name}\n\n**Type:** {org.org_type}\n**Leader:** {org.leader}\n**Ideology:** {org.ideology}\n"
                with open(path, 'w', encoding='utf-8') as f: f.write(content)

        # 3. Locations
        for loc in story_data.locations:
            path = self.dirs['locs'] / f"{self._sanitize(loc.name)}.md"
            if not path.exists():
                content = f"# {loc.name}\n\n**Geography:** {loc.geography}\n**Visuals:** {loc.visual_signature}\n"
                with open(path, 'w', encoding='utf-8') as f: f.write(content)

    def update_psych_profiles(self, psych_data):
        if not psych_data: return

        for profile in psych_data.profiles:
            path = self.dirs['chars'] / f"{self._sanitize(profile.name)}.md"

            psych_block = f"""
## 🧠 Psychology
> [!note] Internal State
> **Archetype:** {profile.archetype}
> **Moral Alignment:** {profile.moral_alignment}
> **Decision Style:** {profile.decision_making_style}
>
> **Core Desire:** {profile.core_desire}
> **Core Fear:** {profile.core_fear}
"""
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()

                if "## 🧠 Psychology" in content:
                    content = content.replace("*(Run the Psychologist Agent to populate this)*", psych_block.replace("## 🧠 Psychology", "").strip())
                else:
                    content += psych_block

                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)
                logger.info(f"🧠 Updated Psychology for: {profile.name}")

    # --- NEW: MECHANIC WRITER ---
    def update_systems(self, mech_data, source_title):
        if not mech_data: return

        for sys in mech_data.systems:
            path = self.dirs['systems'] / f"{self._sanitize(sys.name)}.md"

            # Ability Table
            ability_rows = []
            for a in sys.abilities:
                row = f"| **{a.name}** | {a.cost} | {a.limitations} |"
                ability_rows.append(row)
            ability_table = "\n".join(ability_rows)

            # Tech Tree (Mermaid)
            mermaid_lines = []
            for a in sys.abilities:
                if a.prerequisites:
                    # Clean names
                    src = self._sanitize(a.prerequisites).replace(" ", "_")
                    tgt = self._sanitize(a.name).replace(" ", "_")
                    mermaid_lines.append(f"    {src} --> {tgt}")

            tech_tree = ""
            if mermaid_lines:
                tech_tree = "### 🌳 Tech Tree\n```mermaid\ngraph TD;\n" + "\n".join(mermaid_lines) + "\n```\n"

            content = f"""---
tags: [System, Type/{sys.type}]
---
# {sys.name}

> [!summary] System Core
> **Type:** {sys.type}
> **Origin:** {sys.origin}
> **Source:** [[{source_title}]]

## 📜 Hard Rules
{chr(10).join([f"- **{r.name}**: {r.description} *(Cost: {r.consequence or 'None'})*" for r in sys.rules])}

## ⚡ Abilities
| Ability | Cost | Limits |
|---|---|---|
{ability_table}

{tech_tree}
"""
            if not path.exists():
                with open(path, 'w', encoding='utf-8') as f: f.write(content)
            logger.info(f"   ⚙️ Updated System: {sys.name}")


# --- REFACTORED PROCESSING LOGIC (DEBUG MODE) ---

async def process_video(url: str, yt_api, processor, writer, swarm):
    print(f"\n🔎 DIAGNOSTIC: Starting process for {url}")
    print(f"📂 Vault Path: {writer.vault_path.absolute()}")

    try:
        # A. Metadata
        try:
            video_id = yt_api.extract_video_id(url)
        except Exception as e:
            logger.error(f"❌ Invalid URL: {e}")
            return

        if writer.is_processed(video_id):
            print(f"⏩ Skipping {video_id} (Already Processed)")
            return

        print(f"▶️ Processing Video ID: {video_id}")
        meta = yt_api.get_metadata(video_id)
        print(f"   Title: {meta['title']}")

        # B. Transcript
        full_text = processor.get_transcript(video_id)
        if not full_text:
            logger.warning("❌ Skipping: No Transcript found/extracted.")
            return

        print(f"   📝 Transcript extracted: {len(full_text)} characters")

        # C. Run Agents
        existing_context = writer.get_existing_notes()

        # 1. Theorist
        print("   🧠 Running Theorist...")
        try:
            craft_data = await swarm.theorist.run(full_text, existing_context, meta['title'])
            if craft_data:
                print(f"      ✅ Theorist returned: {len(craft_data.concepts)} concepts")
                writer.update_craft_bible(craft_data, url, meta['title'])
            else:
                print("      ⚠️ Theorist returned EMPTY data.")
        except Exception as e:
            print(f"      ❌ Theorist Crashed: {e}")

        # 2. Profiler (THE IMPORTANT ONE)
        print("   🕵️ Running Profiler...")
        try:
            lore_data = await swarm.profiler.run(full_text, existing_context, meta['title'])
            if lore_data:
                print(f"      ✅ Profiler found: {len(lore_data.characters)} Chars, {len(lore_data.locations)} Locs")
                writer.update_story_bible(lore_data, meta['title'])
            else:
                print("      ⚠️ Profiler returned EMPTY data.")
        except Exception as e:
            print(f"      ❌ Profiler Crashed: {e}")

        # 3. Psychologist
        print("   🧠 Running Psychologist...")
        try:
            psych_data = await swarm.psychologist.run(full_text, existing_context, meta['title'])
            if psych_data:
                print(f"      ✅ Psychologist found: {len(psych_data.profiles)} Profiles")
                writer.update_psych_profiles(psych_data)
            else:
                print("      ⚠️ Psychologist returned EMPTY data.")
        except Exception as e:
            print(f"      ❌ Psychologist Crashed: {e}")

        # 4. Navigator
        print("   🗺️ Running Navigator...")
        try:
            nav_data = await swarm.navigator.run(full_text, existing_context, meta['title'])
            if nav_data:
                print(f"      ✅ Navigator found: {len(nav_data.locations)} locations")
                writer.update_navigation_data(nav_data, meta['title'])
            else:
                print("      ⚠️ Navigator returned EMPTY data.")
        except Exception as e:
            print(f"      ❌ Navigator Crashed: {e}")

        # 5. Mechanic
        print("   ⚙️ Running Mechanic...")
        try:
            mech_data = await swarm.mechanic.run(full_text, existing_context, meta['title'])
            if mech_data:
                writer.update_systems(mech_data, meta['title'])
                print(f"      ✅ Mechanic found: {len(mech_data.systems)} systems")
        except Exception as e:
            print(f"      ❌ Mechanic Crashed: {e}")

        # D. Mark Complete
        writer.mark_as_processed(video_id)
        print("   ✅ Processing Complete!")

    except Exception as e:
        logger.error(f"❌ CRITICAL FAILURE on {url}: {e}")

# --- MAIN EXECUTION ---

async def main():
    print("========================================")
    print("   WriterOS v3.0 - Ingestion Engine")
    print("========================================")

    # 1. Init
    swarm = AgentSwarm()
    yt_api = YouTubeAPI(YOUTUBE_API_KEY)
    processor = ProcessingEngine()
    writer = ObsidianWriter(OBSIDIAN_VAULT_PATH)

    # 2. Handle Arguments (New Single Shot Logic)
    parser = argparse.ArgumentParser(description="Ingest YouTube videos into WriterOS")
    parser.add_argument("url", nargs="?", help="Single YouTube URL to process")
    args = parser.parse_args()

    urls = []

    # 3. Determine Source
    if args.url:
        print(f"🔗 Single URL mode detected.")
        urls.append(args.url)
    else:
        # Fallback to urls.txt
        url_file = Path("urls.txt")
        if url_file.exists():
            with open(url_file, "r") as f:
                urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            print(f"📋 Found {len(urls)} videos in urls.txt")
        else:
            print("❌ No URL provided and urls.txt not found.")
            return

    # 4. Process
    for url in urls:
        await process_video(url, yt_api, processor, writer, swarm)

if __name__ == "__main__":
    asyncio.run(main())