import json
import os
import re
from datetime import datetime
from google import genai
from google.genai import types

# Initialize Gemini Client
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable is missing!")

client = genai.Client(api_key=api_key)

SYSTEM_INSTRUCTION = """
You are a master children's bedtime story author crafting verses for toddlers.
Your core cast:
- Rory: A friendly, gentle green Tyrannosaurus rex.
- Tilly: A calm, supportive herbivore friend.
- Benny: A heavy, comforting, and grounded friend.
- Ricky: A sturdy, protective armored dinosaur who rests with his chin on his paw.
- Nia: A graceful flyer who swoops and keeps watch.
- Psittaco: A tiny, chirpy, energetic guide who loves nesting in leaves or wings.

Formatting & Style Rules (NON-NEGOTIABLE):
1. Exactly 6 verses (stanzas).
2. Exactly 4 lines per verse (quatrain).
3. Meter & Cadence: Strict, rolling anapestic tetrameter (approx 10-12 syllables per line, e.g. "da-da-DUM da-da-DUM da-da-DUM da-da-DUM").
4. Rhyme Scheme: Strict ABAB in every single verse (Line 1 rhymes with Line 3, and Line 2 rhymes with Line 4). Never use AABB or unrhymed lines.
5. Narrative: Keep it varied. Vary the setting (groves, caves, rivers, starry ridges), initial discovery, teamwork actions, and cozy closing scenes so it never reuses repetitive template phrasing across stories.
6. Tone: Calming, serene, warm, and distinctly bedtime-oriented.
"""

FEW_SHOT_EXAMPLE = """
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

Output schema requirements:
Return a JSON object containing:
- "title": A lyrical, evocative title (e.g., "Rory and the Whispering Falls")
- "verses": An array of exactly 6 strings, where each string contains exactly 4 lines separated by newlines.
"""

response = client.models.generate_content(
    model="gemini-3.6-flash",
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
new_story = json.loads(raw_text)
new_story["id"] = now.strftime("%Y-%m-%d-%H%M%S")
new_story["date"] = now.strftime("%A, %B %d, %Y")
new_story["month_group"] = now.strftime("%b-%y")  # e.g., Aug-26
new_story["timestamp"] = now.isoformat()

archive = []
if os.path.exists("stories.json"):
    try:
        with open("stories.json", "r", encoding="utf-8") as f:
            archive = json.load(f)
    except Exception:
        archive = []

archive.insert(0, new_story)

with open("stories.json", "w", encoding="utf-8") as f:
    json.dump(archive, f, indent=2, ensure_ascii=False)

with open("story.json", "w", encoding="utf-8") as f:
    json.dump(new_story, f, indent=2, ensure_ascii=False)

print(f"Archived story: {new_story.get('title')} ({new_story['month_group']})")
raw_text = response.text.strip()

if "```" in raw_text:
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if match:
        raw_text = match.group(0)

data = json.loads(raw_text)
data["date"] = datetime.now().strftime("%A, %B %d, %Y")

with open("story.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"Generated story: {data.get('title')}")
