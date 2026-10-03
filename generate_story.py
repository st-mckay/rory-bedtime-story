import json
import os
import random
import re
import time
import urllib.request
from datetime import datetime
from google import genai
from google.genai import types
from google.genai.errors import ServerError

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable is missing!")

client = genai.Client(api_key=api_key)

# Load existing archive early
archive = []
if os.path.exists("stories.json"):
    try:
        with open("stories.json", "r", encoding="utf-8") as f:
            archive = json.load(f)
    except Exception:
        archive = []

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

# 2. Dynamic Rhyme Scheme Rotation
SCHEMES = ["AABB", "ABCB", "ABAB"]
recent_schemes = [
    s.get("rhyme_scheme") for s in archive[:3] if s.get("rhyme_scheme") in SCHEMES
]

# Filter out the most recent scheme so two consecutive days never repeat the same meter
candidates = [s for s in SCHEMES if not (recent_schemes and s == recent_schemes[0])]
target_rhyme_scheme = random.choice(candidates if candidates else SCHEMES)
print(f"Assigned rhyme scheme for tonight: {target_rhyme_scheme} (Recent history: {recent_schemes})")

SYSTEM_INSTRUCTION = f"""
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
4. Meter & Rhyme Scheme (STRICTLY REQUIRED):
   - You MUST compose all 6 verses in the {target_rhyme_scheme} rhyme scheme.
   - If AABB: Lines 1 & 2 rhyme, lines 3 & 4 rhyme.
   - If ABCB: Lines 2 & 4 rhyme; lines 1 & 3 do not need to rhyme.
   - If ABAB: Lines 1 & 3 rhyme, lines 2 & 4 rhyme.
   - Use simple, pure, ear-pleasing rhymes suitable for young children (e.g., night/bright, sleep/deep, sky/high, glow/slow). Avoid forced, imperfect, slant, or multisyllabic tongue-twisters.
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

Option C (Alternating Cadence ABAB):
The stars began to softly shine,
Across the quiet sky,
The sleeping ferns were sweet and fine,
As Rory drifted by.
"""

USER_PROMPT = f"""
Write tonight's unique bedtime story featuring Rory and his friends following the system instructions.
Every stanza MUST strictly follow the {target_rhyme_scheme} rhyme scheme.
{FEW_SHOT_EXAMPLE}
{feedback_guidance}

Output schema requirements:
Return a JSON object containing:
- "title": A lyrical, evocative title (e.g., "Rory and the Whispering Falls")
- "verses": An array of exactly 6 strings, where each string contains exactly 4 lines separated by newlines.
- "rhyme_scheme": Exactly "{target_rhyme_scheme}"
"""

# 3. Dynamic Model Discovery and Prioritization
def get_candidate_models():
    preferred_order = [
        "gemini-3.8-flash",
        "gemini-3.8-pro",
        "gemini-3.5-flash",
        "gemini-3.0-flash",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
    ]
    
    discovered = []
    try:
        for m in client.models.list():
            model_id = getattr(m, "name", "")
            clean_id = model_id.split("/")[-1] if "/" in model_id else model_id
            
            methods = getattr(m, "supported_actions", None) or getattr(m, "supported_generation_methods", [])
            supports_generate = any("generateContent" in str(act) for act in methods) if methods else True
            
            if supports_generate and not any(x in clean_id.lower() for x in ["embed", "aqa", "imagen", "veo"]):
                discovered.append(clean_id)
    except Exception as e:
        print(f"Notice: Failed to fetch live models from API: {e}. Using preference list.")

    ordered_models = []
    for pref in preferred_order:
        if pref in discovered:
            ordered_models.append(pref)

    for m in discovered:
        if "flash" in m and m not in ordered_models:
            ordered_models.append(m)

    if not ordered_models:
        ordered_models = [m for m in preferred_order if m != "gemini-2.5-flash"] + ["gemini-2.5-flash"]

    return ordered_models

models_to_try = get_candidate_models()
print(f"Identified candidate models for generation: {models_to_try}")

response = None
used_model = None

for model_name in models_to_try:
    for attempt in range(1, 4):
        try:
            print(f"Generating story with {model_name} (Attempt {attempt}/3)...")
            response = client.models.generate_content(
                model=model_name,
                contents=USER_PROMPT,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    temperature=0.75,
                ),
            )
            used_model = model_name
            break
        except ServerError as e:
            print(f"503 Server Error on {model_name}: {e}. Waiting to retry...")
            if attempt < 3:
                time.sleep(attempt * 4)
            else:
                print(f"Exhausted retries for {model_name}.")
        except Exception as e:
            print(f"Error encountered with {model_name}: {e}")
            break
    if response:
        break

if not response:
    raise RuntimeError("Failed to generate bedtime story after trying all candidate models.")

raw_text = response.text.strip()
if "```" in raw_text:
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if match:
        raw_text = match.group(0)

now = datetime.now()
base_date = now.strftime("%A, %B %d, %Y")

today_count = sum(1 for s in archive if s.get("date_raw") == now.strftime("%Y-%m-%d"))
formatted_date = f"{base_date} (Story {today_count + 1})" if today_count > 0 else base_date

new_story = json.loads(raw_text)
new_story["id"] = now.strftime("%Y-%m-%d-%H%M%S")
new_story["date_raw"] = now.strftime("%Y-%m-%d")
new_story["date"] = formatted_date
new_story["month_group"] = now.strftime("%b-%y")
new_story["timestamp"] = now.isoformat()
new_story["model"] = used_model
# Ensure the assigned scheme is accurately recorded in metadata
new_story["rhyme_scheme"] = target_rhyme_scheme

archive.insert(0, new_story)

with open("stories.json", "w", encoding="utf-8") as f:
    json.dump(archive, f, indent=2, ensure_ascii=False)

with open("story.json", "w", encoding="utf-8") as f:
    json.dump(new_story, f, indent=2, ensure_ascii=False)

print(f"Generated & Archived: {new_story.get('title')} [{target_rhyme_scheme}] using {used_model} as '{formatted_date}'")
