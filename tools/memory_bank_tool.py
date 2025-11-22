import json
import os
import random
from typing import List, Dict, Optional

# Define the path where the memory will be stored
MEMORY_FILE_PATH = "memory_bank.json"

class MemoryBankTool:
    """
    Manages the long-term memory for the Native Phrase Navigator Agent.
    It stores and retrieves colloquial phrases taught to the user.
    """

    def __init__(self):
        """
        Initializes the MemoryBankTool and loads existing phrases from the file.
        """
        self.memory: List[Dict] = self._load_memory()
        print(f"MemoryBank initialized. Loaded {len(self.memory)} phrases.")

    def _load_memory(self) -> List[Dict]:
        """Loads memory data from the JSON file."""
        if os.path.exists(MEMORY_FILE_PATH):
            try:
                with open(MEMORY_FILE_PATH, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (IOError, json.JSONDecodeError) as e:
                print(f"Error loading memory file: {e}. Starting with empty memory.")
                return []
        return []

    def _save_memory(self):
        """Saves the current memory data to the JSON file."""
        try:
            with open(MEMORY_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.memory, f, indent=4)
        except IOError as e:
            print(f"Error saving memory file: {e}")

    # --- Tool Functions for the Agents to Use ---

    def _extract_canonical_from_lesson(self, lesson_text: Optional[str], lesson_html: Optional[str]) -> Optional[str]:
        """Try to extract an explicit canonical phrase from lesson_text or lesson_html.
        Checks labeled lines (Phrase to learn / Suggested colloquial phrase), <<...>> markers, or <strong> tags.
        """
        import re
        text = (lesson_text or '')
        html = (lesson_html or '')
        if text:
            m = re.search(r'(?:Phrase to learn|Suggested colloquial phrase)\s*[:\-]?\s*(?:<<([^>]+)>>|"?([^\n"]+)"?)', text, re.IGNORECASE)
            if m:
                return (m.group(1) or m.group(2) or '').strip() or None
            m2 = re.search(r'<<([^>]+)>>', text)
            if m2 and m2.group(1).strip():
                return m2.group(1).strip()
        if html:
            # strip tags and retry label search
            plain = re.sub(r'<[^>]+>', '', html)
            m = re.search(r'(?:Phrase to learn|Suggested colloquial phrase)\s*[:\-]?\s*(?:<<([^>]+)>>|"?([^\n"]+)"?)', plain, re.IGNORECASE)
            if m:
                return (m.group(1) or m.group(2) or '').strip() or None
            m3 = re.search(r'<strong>([^<]+)</strong>', html, re.IGNORECASE)
            if m3 and m3.group(1).strip():
                return m3.group(1).strip()
        return None

    def add_phrase(self, phrase: str, meaning: str, source_context: str = None, corrected_context: str = None, lesson_text: str = None, lesson_html: str = None) -> str:
        """
        Adds a new colloquial phrase and its details to the memory bank.
        This function is called by the Teacher Agent.

        Args:
            phrase: The colloquial phrase (e.g., "starving").
            meaning: The standard definition (e.g., "extremely hungry").
            source_context: (optional) The original user sentence (will not be saved if None).
            corrected_context: (optional) The corrected version of the user's sentence (plain text).
            lesson_text: (optional) Full lesson text in plain text.
            lesson_html: (optional) Lesson text that may include safe <strong> tags for emphasis.
        
        Returns:
            A confirmation message that the phrase was added or updated.
        """
        # Determine canonical phrase from lesson_text or lesson_html when available
        canonical = None
        try:
            canonical = self._extract_canonical_from_lesson(lesson_text, lesson_html)
        except Exception:
            canonical = None

        final_phrase = (canonical or phrase or '').strip()
        if not final_phrase:
            return "No valid phrase provided to add."

        # Normalize for comparison
        def _norm(s: str) -> str:
            return (s or '').lower().strip()

        final_norm = _norm(final_phrase)

        # If an existing entry matches the canonical phrase, update it instead of adding duplicate
        for idx, item in enumerate(self.memory):
            if _norm(item.get('phrase')) == final_norm:
                # Merge/update fields
                if meaning:
                    item['meaning'] = meaning
                if corrected_context:
                    item['corrected_context'] = corrected_context
                if lesson_text:
                    item['lesson_text'] = lesson_text
                if lesson_html:
                    item['lesson_html'] = lesson_html
                # update date
                item['date_added'] = self._get_timestamp()
                self.memory[idx] = item
                self._save_memory()
                return f"Updated existing entry for '{final_phrase}' in the memory bank."

        # If no exact match found, append new entry
        new_entry = {
            "phrase": final_phrase,
            "meaning": meaning,
            "date_added": self._get_timestamp()
        }

        if source_context:
            new_entry["source_context"] = source_context

        if corrected_context:
            new_entry["corrected_context"] = corrected_context
        if lesson_text:
            new_entry["lesson_text"] = lesson_text
        if lesson_html:
            new_entry["lesson_html"] = lesson_html

        self.memory.append(new_entry)
        self._save_memory()
        return f"Successfully added '{final_phrase}' to the memory bank for future testing."

    def get_random_phrase(self, count: int = 1) -> List[Dict]:
        """
        Retrieves a specified number of random phrases from the memory bank.
        This function is called by the Quiz Master Agent.

        Args:
            count: The number of phrases to retrieve. Defaults to 1.
        
        Returns:
            A list of phrase dictionaries, or an empty list if memory is insufficient.
        """
        if len(self.memory) < count:
            return [{"error": f"Not enough phrases (needed {count}, found {len(self.memory)}). Continue teaching the user first."}]

        # Use random.sample for efficient selection without replacement
        selected_phrases = random.sample(self.memory, count)
        
        # We clean the output slightly for the Quiz Master to prevent it from seeing the 'date_added' if not needed
        output = []
        for phrase in selected_phrases:
            output.append({
                "phrase": phrase["phrase"],
                "meaning": phrase["meaning"],
                # Do not return the source_context in the quiz retrieval
            })
            
        return output

    def get_memory_stats(self) -> str:
        """
        Provides a summary of the current memory bank.
        """
        return f"Memory Bank currently holds {len(self.memory)} unique phrases."

    def _get_timestamp(self) -> str:
        """Utility function to get the current time."""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Example usage (for testing purposes, not part of the agent flow)
if __name__ == "__main__":
    # Create an instance of the tool
    mb = MemoryBankTool()
    
    # Check stats
    print(mb.get_memory_stats())

    # Add a new phrase
    add_result = mb.add_phrase("spill the beans", "to reveal a secret", "I hope you don't spill the beans about the party.")
    print(add_result)
    
    # Add another phrase
    mb.add_phrase("hang in there", "don't give up", "You just have to hang in there until the project is over.")
    
    # Get a random phrase for a quiz
    random_phrase = mb.get_random_phrase(1)
    print(f"\nQuiz Request:")
    print(random_phrase)
    
    # Check final stats
    print(f"\nFinal Stats: {mb.get_memory_stats()}")