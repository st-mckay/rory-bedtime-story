import json
import os
import re
import urllib.request
from datetime import datetime
from google import genai
from google.genai import types

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable is missing!")

client = genai.Client(api_key=api_key)

# Load existing archive early so we can cross-reference liked/disliked story structures
archive = []
if os.path.exists("stories.json"):
    try:
        with open("stories.json", "r", encoding="utf-8") as f:
            archive = json.load(f)
    except Exception:
        archive = []

# Helper: Rough detection of rhyme pattern from stored story verses
def inspect_story_rhyme(story_obj):
    """Inspects a story's verses to identify if it leans AABB, ABCB, or ABAB."""
    verses = story_obj.get("verses", [])
    if not verses or not isinstance(verses, list):
        return None
    # We can inspect the end word vowels/patterns or check metadata if tagged
    # Default to balanced toddler-friendly patterns
    return "gentle couplets (AABB) or soothing nursery ballad rhyme (ABCB)"

# 1. Fetch User Feedback & Story Preferences from Cloudflare Worker (D1)
PREFERENCES_URL = "https://rory-trigger.stuartmckay.workers.dev/preferences"
feedback_guidance = ""

try:
    req = urllib.request.Request(
        PREFERENCES_URL,
        headers={"User-Agent": "Rory-Bedtime-Story-Generator"}
    )
    with urllib.request.urlopen(req, timeout=8) as response:
        if response.status == 200:
            pref_data = json.loads(response.read().decode("utf-8"))
            liked = pref_data.get("liked_titles", [])
            disliked = pref_data.get("disliked_titles", [])

            guidance_lines = []
            if liked:
                liked_str = ", ".join(f'"{t}"' for t in liked)
                guidance_lines.append(
                    f"- High-performing favorite stories: {liked_str}. "
                    f"Emulate the rhythmic charm, bedtime cadence, and comfortable rhyme scheme that made these tales captivating."
                )
            if disliked:
                disliked_str = ", ".join(f'"{t}"' for t in disliked)
                guidance_lines.append(
                    f"- Poorly rated stories: {disliked_str}. "
                    f"Avoid plotlines, awkward rhyme pairings, or pacing resembling these."
                )

            if guidance_lines:
                feedback_guidance = "\nChild Feedback & Musicality Directives:\n" + "\n".join(guidance_lines)
                print(f"Loaded {len(liked)} liked and {len(disliked)} disliked preferences from D1.")
except Exception as e:
    print(f"Notice: Could not fetch preferences from D1 (proceeding with base prompt): {e}")

SYSTEM_INSTRUCTION = """
You are a master children's bedtime story author crafting verses for toddlers (ages 1 to 3).
Your core cast:
- Rory: Main protagonist, should be the center of every story. A friendly, gentle green Tyrannosaurus rex.
- Tilly: A calm, supportive herbivore triceratops friend.
- Benny: A heavy, comforting, and grounded diplodocus friend.
- Ricky: An energetic velociraptor who loves to get into mischief.
- Nia: A graceful pterodactyl who swoops and keeps watch.
- Psittaco: A tiny psittacosaurus, chirpy, energetic guide who loves nesting in leaves or wings.

Formatting & Style Rules (NON-NEGOTIABLE):
1. Exactly 6 verses (stanzas).
2. Exactly 4 lines per verse (quatrain).
3. Meter & Cadence: Strict, rolling anapestic or dactylic bedtime bounce (approx 8-12 syllables per line, e.g. "da-da-DUM da-da-DUM da-da-DUM da-da-DUM"). Must be smooth, sing-song, and effortless to read aloud.
4. Toddler-Friendly Rhyme Scheme Flexibility:
   - Choose a consistent, musical rhyme scheme for the story: AABB (rhyming couplets), ABCB (nursery ballad), or ABAB (alternating).
   - Use simple, pure, ear-pleasing rhymes suitable for young children (e.g., night/bright, sleep/deep, sky/high, glow/slow). Avoid forced, imperfect, slant, or multisyllabic tongue-twisters.
   - Let the preference feedback guide your choice of cadence and rhyming rhythm.
5. NO CHARACTER ADJECTIVE PREFIXES: Use the character names directly ("Rory", "Tilly", "Benny", "Ricky", "Nia", "Psittaco"). NEVER prefix their names with descriptive filler adjectives (e.g., DO NOT write "Sweet Nia", "Brave Tilly", "Soft Rory", "Young Psittaco", "Small Psittaco", "Little Benny", "Gentle Ricky"). Let actions and natural dialogue convey their personality instead.
6. Narrative: Keep it varied. Vary the setting (groves, caves, rivers, starry ridges), initial discovery, teamwork actions, and cozy closing scenes so it never reuses repetitive template phrasing across stories.
7. Tone: Calming, serene, warm, melodic, and distinctly bedtime-oriented.
"""

FEW_SHOT_EXAMPLE = """
Example of Toddler-Appropriate Flow:

Option A (Soothing Ballad ABCB):
The moon climbed high above the trees,
And lit the sleepy ground,
Where Rory walked with gentle steps,
Without a single sound.

Option B (Musical Couplets AABB):
The starry night was deep and blue,
The grass was damp with evening dew.
Then Ricky found a quiet nest,
Where all the friends could lie and rest.
"""

USER_PROMPT = f"""
Write tonight's unique bedtime story featuring Rory and his friends following the system instructions.
{FEW_SHOT_EXAMPLE}
{feedback_guidance}

Output schema requirements:
Return a JSON object containing:
- "title": A lyrical, evocative title (e.g., "Rory and the Whispering Falls")
- "verses": An array of exactly 6 strings, where each string contains exactly 4 lines separated by newlines.
- "rhyme_scheme": The primary scheme used ("AABB", "ABCB", or "ABAB").
"""

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=USER_PROMPT,
    config=types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        temperature=0.75,
    ),
)

raw_text = response.text.strip()
if "```" in raw_text:
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if match:
        raw_text = match.group(0)

now = datetime.now()
base_date = now.strftime("%A, %B %d, %Y")

# Count existing stories generated today to calculate incremental number
today_count = sum(1 for s in archive if s.get("date_raw") == now.strftime("%Y-%m-%d"))

if today_count > 0:
    formatted_date = f"{base_date} (Story {today_count + 1})"
else:
    formatted_date = base_date

new_story = json.loads(raw_text)
new_story["id"] = now.strftime("%Y-%m-%d-%H%M%S")
new_story["date_raw"] = now.strftime("%Y-%m-%d")
new_story["date"] = formatted_date
new_story["month_group"] = now.strftime("%b-%y")
new_story["timestamp"] = now.isoformat()

# Prepend newest story to archive
archive.insert(0, new_story)

with open("stories.json", "w", encoding="utf-8") as f:
    json.dump(archive, f, indent=2, ensure_ascii=False)

with open("story.json", "w", encoding="utf-8") as f:
    json.dump(new_story, f, indent=2, ensure_ascii=False)

print(f"Generated & Archived: {new_story.get('title')} [{new_story.get('rhyme_scheme', 'ABAB')}] as '{formatted_date}'")FEW_SHOT_EXAMPLE = """
Target Meter & Structure Reference (ABAB):
The sun dipped away behind ridges of blue,
When Nia swooped low with a chirp of delight.
She led all her friends through the shimmering dew,
To find where the waterfall glowed in the night.

Behind the cool spray was a wide, hidden shelf,
Where giant soft ferns caught the mist in the air.
Each dinosaur found a dry spot for itself,
Content with the magical calm waiting there.
"""

USER_PROMPT = f"""
Write tonight's unique bedtime story featuring Rory and his friends following the system instructions.
{FEW_SHOT_EXAMPLE}
{feedback_guidance}

Output schema requirements:
Return a JSON object containing:
- "title": A lyrical, evocative title (e.g., "Rory and the Whispering Falls")
- "verses": An array of exactly 6 strings, where each string contains exactly 4 lines separated by newlines.
"""

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=USER_PROMPT,
    config=types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        temperature=0.75,
    ),
)

raw_text = response.text.strip()
if "```" in raw_text:
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if match:
        raw_text = match.group(0)

now = datetime.now()
base_date = now.strftime("%A, %B %d, %Y")

# Load existing archive
archive = []
if os.path.exists("stories.json"):
    try:
        with open("stories.json", "r", encoding="utf-8") as f:
            archive = json.load(f)
    except Exception:
        archive = []

# Count existing stories generated today to calculate incremental number
today_count = sum(1 for s in archive if s.get("date_raw") == now.strftime("%Y-%m-%d"))

if today_count > 0:
    formatted_date = f"{base_date} (Story {today_count + 1})"
else:
    formatted_date = base_date

new_story = json.loads(raw_text)
new_story["id"] = now.strftime("%Y-%m-%d-%H%M%S")
new_story["date_raw"] = now.strftime("%Y-%m-%d")
new_story["date"] = formatted_date
new_story["month_group"] = now.strftime("%b-%y")
new_story["timestamp"] = now.isoformat()

# Prepend newest story to archive
archive.insert(0, new_story)

with open("stories.json", "w", encoding="utf-8") as f:
    json.dump(archive, f, indent=2, ensure_ascii=False)

with open("story.json", "w", encoding="utf-8") as f:
    json.dump(new_story, f, indent=2, ensure_ascii=False)

print(f"Generated & Archived: {new_story.get('title')} as '{formatted_date}'")if "```" in raw_text:
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if match:
        raw_text = match.group(0)

now = datetime.now()
base_date = now.strftime("%A, %B %d, %Y")

# Load existing archive
archive = []
if os.path.exists("stories.json"):
    try:
        with open("stories.json", "r", encoding="utf-8") as f:
            archive = json.load(f)
    except Exception:
        archive = []

# Count existing stories generated today to calculate incremental number
today_count = sum(1 for s in archive if s.get("date_raw") == now.strftime("%Y-%m-%d"))

if today_count > 0:
    formatted_date = f"{base_date} (Story {today_count + 1})"
else:
    formatted_date = base_date

new_story = json.loads(raw_text)
new_story["id"] = now.strftime("%Y-%m-%d-%H%M%S")
new_story["date_raw"] = now.strftime("%Y-%m-%d")
new_story["date"] = formatted_date
new_story["month_group"] = now.strftime("%b-%y")
new_story["timestamp"] = now.isoformat()

# Prepend newest story to archive
archive.insert(0, new_story)

with open("stories.json", "w", encoding="utf-8") as f:
    json.dump(archive, f, indent=2, ensure_ascii=False)

with open("story.json", "w", encoding="utf-8") as f:
    json.dump(new_story, f, indent=2, ensure_ascii=False)

print(f"Generated & Archived: {new_story.get('title')} as '{formatted_date}'")
