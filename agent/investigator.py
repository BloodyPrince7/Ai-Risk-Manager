import json
import os

from dotenv import load_dotenv
from google import genai

from .prompts import SYSTEM_PROMPT


# ============================================================
# Load environment variables
# ============================================================

load_dotenv()


# ============================================================
# Gemini configuration
# ============================================================

GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY"
)

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY not found."
    )


client = genai.Client(
    api_key=GEMINI_API_KEY
)


# ============================================================
# Model
# ============================================================

MODEL_NAME = "gemini-3.6-flash"


# ============================================================
# Investigator
# ============================================================

def investigate_case(case):
    """
    Investigate a risk case using Gemini.

    Parameters
    ----------
    case : dict
        Risk case information.

    Returns
    -------
    dict
        Structured AI investigation.
    """

    # --------------------------------------------------------
    # Convert case into readable JSON
    # --------------------------------------------------------

    case_json = json.dumps(
        case,
        indent=2,
        default=str
    )


    # --------------------------------------------------------
    # Build investigation prompt
    # --------------------------------------------------------

    prompt = f"""
{SYSTEM_PROMPT}

Here is the case you need to investigate:

CASE DATA:

{case_json}

Analyze this case using ONLY the information above.

Return ONLY valid JSON.
"""


    # --------------------------------------------------------
    # Ask Gemini
    # --------------------------------------------------------

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )


    # --------------------------------------------------------
    # Extract response
    # --------------------------------------------------------

    text = response.text.strip()


    # --------------------------------------------------------
    # Remove markdown code fences if Gemini adds them
    # --------------------------------------------------------

    if text.startswith("```json"):
        text = text[7:]

    elif text.startswith("```"):
        text = text[3:]


    if text.endswith("```"):
        text = text[:-3]


    text = text.strip()


    # --------------------------------------------------------
    # Convert JSON → Python dictionary
    # --------------------------------------------------------

    try:

        result = json.loads(text)

    except json.JSONDecodeError as error:

        raise ValueError(
            "Gemini returned invalid JSON."
        ) from error


    # --------------------------------------------------------
    # Basic validation
    # --------------------------------------------------------

    required_fields = [
        "summary",
        "risk_factors",
        "evidence_to_check",
        "recommended_action",
        "confidence"
    ]


    for field in required_fields:

        if field not in result:

            raise ValueError(
                f"Missing field from Gemini response: {field}"
            )


    # --------------------------------------------------------
    # Validate confidence
    # --------------------------------------------------------

    confidence = float(
        result["confidence"]
    )


    if not 0 <= confidence <= 1:

        raise ValueError(
            "Confidence must be between 0 and 1."
        )


    result["confidence"] = confidence


    return result