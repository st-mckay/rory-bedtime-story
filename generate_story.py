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

prompt = """
Write a calming bedtime story featuring Rory and friends (Tilly, Benny, Ricky, Nia, and Psittaco).
Strict structural requirements:
1. Exactly 6 verses.
2. Exactly 4 lines per verse.
3. Use a steady, rolling anapestic cadence (~10-12 syllables per line).
4. Provide a creative, unique title and new plot/actions so it doesn't repeat old formulas.

Return a JSON object with:
- "title": string
- "verses": array of 6 strings (each string containing 4 lines separated by newlines)
"""

response = client.models.generate_content(
    model="gemini-3.6-flash",
    contents=prompt,
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
    ),
)

raw_text = response.text.strip()

# Clean any code block wrappers if returned
if "```" in raw_text:
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if match:
        raw_text = match.group(0)

data = json.loads(raw_text)
data["date"] = datetime.now().strftime("%A, %B %d, %Y")

with open("story.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Story generated and saved successfully!")
