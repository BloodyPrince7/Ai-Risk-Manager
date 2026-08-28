import os

from dotenv import load_dotenv
from google import genai


load_dotenv()


api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError(
        "GEMINI_API_KEY not found. "
        "Check your .env file."
    )


client = genai.Client(
    api_key=api_key
)


response = client.models.generate_content(
    model="gemini-3.6-flash",
    contents=(
        "You are testing the AI Risk Manager project. "
        "Reply with exactly: Gemini connection successful."
    )
)


print()
print("========== GEMINI TEST ==========")
print(response.text)