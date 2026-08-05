import os
from dotenv import load_dotenv
from google import genai

# Load API key
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ API key not found!")
    exit()

# Connect to Gemini
client = genai.Client(api_key=api_key)

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
    print()