# agents/corrector_agent.py

from google import genai
from google.genai import types

class CorrectorAgent:
    """
    Agent responsible for correcting user input and providing a short "What to improve" note.

    According to AGENTS_README, this agent should NOT suggest or pick the target phrase to learn.
    It should return a corrected version of the user's text and a brief note about what to improve
    (grammar, word choice, phrasing). Output should be plain text with two labeled sections:
    - Corrected context:
    - What to improve:
    """
    def __init__(self, client: genai.Client):
        self.client = client
        self.system_instruction = (
            "You are an expert English corrector.\n"
            "Given a user's sentence, return a corrected plain-text version and a brief 'What to improve' note.\n"
            "Output TWO labeled sections (plain text only) exactly as shown below, and do NOT suggest or pick any phrase to learn:\n"
            "Corrected context: <the corrected sentence>\n"
            "What to improve: <one-line note about grammar/word choice/phrasing>\n"
            "Do NOT include the user's original raw sentence or any phrase suggestions."
        )

    def run(self, user_text: str) -> str:
        """
        Runs the model to process the user's text and returns the plain-text result.
        """
        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash-preview-09-2025',
                contents=[user_text],
                config=types.GenerateContentConfig(
                    system_instruction=self.system_instruction
                )
            )
            return response.text
        except Exception as e:
            return f"Error in Corrector Agent: {e}"

# Note: You will initialize the client and the agent in main.py