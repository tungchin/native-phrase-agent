import os
from dotenv import load_dotenv
from google import genai
from agents.corrector_agent import CorrectorAgent
from agents.teacher_agent import TeacherAgent
from tools.memory_bank_tool import MemoryBankTool # Import the memory tool
from typing import Optional, Tuple
import re

# Ensure you have your GEMINI_API_KEY set as an environment variable
# 1. Load environment variables from the .env file in the current directory
load_dotenv() 

# 2. Initialize the Gemini Client. 
# It automatically reads the GEMINI_API_KEY from the environment now.
client = genai.Client()


def extract_phrase_for_teaching(corrector_output: str) -> Optional[Tuple[str, str]]:
    """
    Parses the Corrector Agent's output to extract the phrase to teach
    and the user's original (corrected) sentence context.

    Tries multiple heuristics to handle different LLM output styles:
    - Quoted phrase
    - A line following a 'Suggested Colloquial Phrase' header
    - Bolded phrase like '**passed out**' and parenthetical '(replaces ... )'
    """
    try:
        if not corrector_output:
            return None

        # Split output by separator if present
        parts = corrector_output.split('---')
        if len(parts) >= 2:
            corrected_text = parts[0].strip()
            suggestion_block = parts[1].strip()
        else:
            # Fallback: treat whole output as corrected_text
            corrected_text = corrector_output.strip()
            suggestion_block = ''

        # 1) Look for explicit 'Phrase to learn:' label
        label_match = re.search(r'Phrase to learn:\s*<<([^>]+)>>', suggestion_block, re.IGNORECASE)
        if label_match:
            return label_match.group(1).strip(), corrected_text
        label_match2 = re.search(r'Phrase to learn:\s*"?([^\n"]+)"?', suggestion_block, re.IGNORECASE)
        if label_match2:
            return label_match2.group(1).strip(), corrected_text

        # 2) Look for Definition label to extract phrase nearby
        def_match = re.search(r'Definition:\s*([^\n]+)', suggestion_block, re.IGNORECASE)
        if def_match:
            # if the phrase appears in the definition as "phrase" is ..., try to extract quoted or emphasized phrase earlier in block
            q = re.search(r'<<([^>]+)>>', suggestion_block)
            if q:
                return q.group(1).strip(), corrected_text

        # 1) Look for the last quoted phrase, assuming it's the suggestion
        phrase_match = re.search(r'["\']([^"\']+)["\']', suggestion_block)
        if phrase_match:
            suggested = phrase_match.group(1).strip()
            # normalize trailing 'is' or numbering
            suggested = re.sub(r"\b(?:is|is:)$", "", suggested, flags=re.IGNORECASE).strip()
            suggested = re.sub(r'^\d+\.\s*', '', suggested)
            return suggested, corrected_text

        # 2) Look for bolded phrase patterns like **passed out**
        bold_match = re.search(r'\*\*([^\*]+)\*\*', suggestion_block)
        if bold_match:
            suggested = bold_match.group(1).strip()
            suggested = re.sub(r"\b(?:is|is:)$", "", suggested, flags=re.IGNORECASE).strip()
            return suggested, corrected_text

        # 3a) Look for a plain phrase followed by a parenthetical '(replaces ...)'
        paren_plain = re.search(r'([A-Za-z\'\- ]{2,})\s*\(replaces[:\s]+[^)]+\)', suggestion_block, re.IGNORECASE)
        if paren_plain:
            suggested = paren_plain.group(1).strip()
            suggested = re.sub(r"\b(?:is|is:)$", "", suggested, flags=re.IGNORECASE).strip()
            suggested = re.sub(r'^\d+\.?\s*', '', suggested)
            return suggested, corrected_text

        # 3) Look for parenthetical 'replaces' pattern with emphasis markers: (replaces *original*) and capture preceding word(s)
        paren_match = re.search(r'\*\*?([^\*\(\n]+)\*\*?\s*\(replaces\s*\*([^\*)]+)\*\)', suggestion_block, re.IGNORECASE)
        if paren_match:
            return paren_match.group(1).strip(), corrected_text

        # 4) Look for a header label then the next non-empty line
        hdr_match = re.search(r'Suggested Colloquial Phrase[:\s]*\n?(.+)', suggestion_block, re.IGNORECASE)
        if hdr_match:
            # take the first line after header, strip Markdown markers
            line = hdr_match.group(1).splitlines()[0].strip()
            line = re.sub(r'[\*`_\[\]]', '', line)
            if line:
                return line, corrected_text

        # 5) As a last resort, try to pick the last short phrase-like token in the suggestion block
        tokens = re.findall(r"[A-Za-z' ]{2,}", suggestion_block)
        if tokens:
            candidate = tokens[-1].strip()
            if 1 < len(candidate.split()) <= 4:
                return candidate, corrected_text

        return None

    except Exception as e:
        print(f"Error extracting phrase: {e}")
        return None

def main():
    """
    Initializes agents and runs the sequential workflow.
    """
    print("--- Initializing Native Phrase Navigator System ---")
    
    # 1. Initialize Long-Term Memory Tool
    memory_bank = MemoryBankTool() 
    
    # 2. Initialize Agents
    corrector_agent = CorrectorAgent(client)
    # The Teacher Agent needs the memory tool passed to it
    teacher_agent = TeacherAgent(client, memory_bank) 
    
    print("\nSystem ready. Memory status:", memory_bank.get_memory_stats())

    # --- Start Sequential Workflow Demonstration ---
    
    user_input = "Yesterday I was very tired after my work, so I slept immediately."
    print(f"\n[USER]: {user_input}")
    
    # --- Step 1: Corrector Agent ---
    print("\n[SYSTEM]: Running Corrector Agent...")
    corrector_output = corrector_agent.run(user_input)
    print(f"\n[CORRECTOR AGENT]:\n{corrector_output}")
    
    # --- Step 2: Orchestration Logic (Extracting the suggestion) ---
    teaching_data = extract_phrase_for_teaching(corrector_output)
    
    if teaching_data:
        phrase_to_teach, context = teaching_data
        print(f"\n[SYSTEM]: Phrase extracted for teaching: '{phrase_to_teach}'")
        
        # --- Step 3: Teacher Agent (Teaches and Stores) ---
        print("\n[SYSTEM]: Running Teacher Agent (Teaching and Storing in Memory)...")
        teacher_output = teacher_agent.run(phrase_to_teach, context)
        print(f"\n[TEACHER AGENT]:\n{teacher_output}")

    else:
        print("\n[SYSTEM]: Could not extract a phrase to teach. Ending session.")
    
    # --- Final Check of Memory ---
    print("\n[SYSTEM]: Final Memory status:", memory_bank.get_memory_stats())

if __name__ == "__main__":
    main()