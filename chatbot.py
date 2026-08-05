import os
import json
from dotenv import load_dotenv
from google import genai

from app import get_database

# Load API key
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ API key not found!")
    exit()

# Connect to Gemini
client = genai.Client(api_key=api_key)

with open("edc_database.json", "r") as file:
    text = file.read()

print(text) 

print("🌸 Shero AI is ready!")
print("Type 'quit' to exit.\n")

SYSTEM_PROMPT = """
You are Shero AI.

You were created by Team Shero.

Your purpose is to help users understand endocrine-disrupting chemicals (EDCs).

If someone asks your name, always answer:
"My name is Shero AI."

Never introduce yourself as Google Gemini.

Be friendly, scientific, and easy to understand.
"""

while True:
    question = input("You: ")

    if question.lower() == "quit":
        print("👋 Goodbye!")
        break

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=question,
        config={
            "system_instruction": SYSTEM_PROMPT
        }
    )

    print("\n🌸 Shero AI:")
    print(response.text)
    question = input("You: ")
    query = question.lower()

found = False

for chemical, info in get_database.items():
    aliases = [a.lower() for a in info.get("aliases", [])]

    if query == chemical.lower() or query in aliases:
        print("\n🌸 Shero AI\n")
        print(f"Chemical: {chemical}")
        print(f"Category: {info['category']}")
        print(f"Risk Level: {info['risk_level']}")
        print(f"Found In: {', '.join(info['found_in'])}")
        print(f"Health Effects: {', '.join(info['health_effects'])}")
        print(f"Scientific Summary: {info['scientific_summary']}")
        print(f"Regulatory Status: {info['regulatory_status']}")
        print()

        found = True
        break

if found:
    print()