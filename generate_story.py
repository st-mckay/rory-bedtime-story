import json
import os
from datetime import datetime
from google import genai

# Initialize the Gemini client
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

prompt = """
Write a calming bedtime story featuring Rory and friends (Tilly, Benny, Ricky, Nia, and Psittaco).
Strict structural requirements:
1. Exactly 6 verses.
2. Exactly 4 lines per verse.
3. Use a steady, rolling anapestic cadence (~10-12 syllables per line).
4. Provide a creative, unique title and new plot/actions so it doesn't repeat old formulas.

Return ONLY a valid JSON object with the keys "title", "date", and "verses" (where verses is an array of 6 strings, each string containing 4 lines separated by newlines). Do not wrap in markdown backticks.
"""

response = client.models.generate_content(
    model="gemini-3.6-flash",
    contents=prompt,
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
    ),
)

raw_text = response.text.strip()
if raw_text.startswith("```json"):
    raw_text = raw_text.split("```json")[1].split("```")[0].strip()
elif raw_text.startswith("```"):
    raw_text = raw_text.split("```")[1].split("```")[0].strip()

data = json.loads(raw_text)
data["date"] = datetime.now().strftime("%A, %B %d, %Y")

with open("story.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Story generated and saved successfully!")
