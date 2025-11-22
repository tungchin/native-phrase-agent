from google import genai
from google.genai import types
import re
from tools.memory_bank_tool import MemoryBankTool # Import the tool class

class TeacherAgent:
    """
    Agent responsible for providing a detailed lesson on a suggested phrase 
    and storing the phrase in the long-term memory via the MemoryBankTool.
    """
    def __init__(self, client: genai.Client, memory_bank: MemoryBankTool):
        self.client = client
        self.memory_bank = memory_bank  # Store the memory bank instance
        # Request plain-text output only. The model MUST include explicit labeled lines
        # to make extraction reliable. Use <<phrase>> markers to indicate emphasis.
        # Required labeled sections (exact text):
        # - What to improve:
        # - Phrase to learn:
        # - Definition:
        # - Examples: (provide exactly two short example sentences)
        # - Notes: (optional brief guidance)
        # IMPORTANT: Output MUST be plain text (no Markdown, no asterisks). Do NOT include the user's original raw sentence.
        self.system_instruction = (
            "You are a friendly, encouraging Native English Tutor. "
            "Given a Phrase and Context, output a concise, plain-text teaching note using these exact labeled sections: \n"
            "What to improve: (list grammar, structure, slang/phrases issues)\n"
            "Phrase to learn: (single phrase or idiom; mark it with <<...>> for emphasis)\n"
            "Definition: (one clear sentence definition of the phrase)\n"
            "Examples: (provide exactly two corrected example sentences demonstrating the phrase)\n"
            "Notes: (optional brief usage tips)\n"
            "Output must be plain text only. Use <<...>> to mark emphasis instead of Markdown. Do NOT output the user's original raw sentence or additional unrelated content."
        )

    def _sanitize_lesson_text(self, text: str) -> str:
        """Remove unwanted Markdown/HTML and normalize emphasis markers."""
        if not text:
            return text
        # Remove code fences and inline code markers
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        text = re.sub(r'`([^`]*)`', r"\1", text)
        # Remove stray asterisks or underscores used as emphasis
        text = re.sub(r'\*\*?', '', text)
        text = re.sub(r'__', '', text)
        # Collapse multiple blank lines
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _to_html(self, text: str) -> str:
        """Convert <<emphasis>> markers into <strong> for safe HTML rendering, and escape other content minimally."""
        if not text:
            return text
        # Escape basic HTML characters
        esc = (text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))
        # Then convert the escaped <<...>> markers back to <strong>
        html = re.sub(r'&lt;&lt;([^&]*)&gt;&gt;', r'<strong>\1</strong>', esc)
        # Also support raw <<...>> without escaping in case
        html = re.sub(r'<<([^>]+)>>', r'<strong>\1</strong>', html)
        # Replace newlines with <br> for simple HTML formatting
        html = html.replace('\n', '<br>')
        return html

    def _canonical_from_labels(self, text: str):
        if not text:
            return None
        m = re.search(r'(?:Phrase to learn|Suggested colloquial phrase)\s*[:\-]?\s*(?:<<([^>]+)>>|"?([^\n"]+)"?)', text, re.IGNORECASE)
        if m:
            return (m.group(1) or m.group(2) or '').strip() or None
        return None

    def _extract_definition_and_examples(self, lesson_text: str, canonical: str):
        # definition
        definition = None
        if lesson_text:
            m = re.search(r'Definition\s*[:\-]?\s*(.+?)(?:\n\n|\n[A-Z][a-z]+\s*[:\-]|$)', lesson_text, re.IGNORECASE | re.DOTALL)
            if m:
                definition = m.group(1).strip()
        # examples: try Examples: block
        examples = []
        if lesson_text:
            m2 = re.search(r'Examples?\s*[:\-]?\s*(.*?)(?:\n\n|\nNotes:|$)', lesson_text, re.IGNORECASE | re.DOTALL)
            if m2:
                block = m2.group(1).strip()
                parts = [p.strip() for p in re.split(r'\n+', block) if p.strip()]
                for p in parts:
                    # remove bullet/number prefixes
                    s = re.sub(r'^[\-\*\d\.)\s]+', '', p).strip()
                    s = re.sub(r'<<([^>]*)>>', lambda mo: (mo.group(1).strip() or canonical or '').strip(), s)
                    s = s.replace('<>', '').strip()
                    if len(s) > 5:
                        examples.append(s)
                    if len(examples) >= 2:
                        break
        # fallback: sentences containing canonical
        if len(examples) < 2 and lesson_text and canonical:
            for sent in re.findall(r'[^\n\.]+\.', lesson_text):
                if re.search(re.escape(canonical), sent, re.IGNORECASE) or '<<' in sent:
                    s = sent.strip()
                    s = re.sub(r'<<([^>]*)>>', lambda mo: (mo.group(1).strip() or canonical).strip(), s)
                    s = s.replace('<>', '').strip()
                    if s and s not in examples:
                        examples.append(s)
                    if len(examples) >= 2:
                        break
        # final fallback: synthesize examples
        while len(examples) < 2 and canonical:
            if len(examples) == 0:
                examples.append(f"I often say, '{canonical}', when I want to emphasize that idea.")
            else:
                examples.append(f"You can use '{canonical}' in everyday conversation to express this meaning.")
        return definition or "No clear definition found.", examples[:2]

    def run(self, phrase: str, source_context: str) -> str:
        """
        Generates the lesson and stores the phrase in memory.

        Args:
            phrase: The new colloquial phrase to teach (e.g., "starving").
            source_context: The corrected sentence context (plain text) provided by the Corrector.

        Returns:
            The generated lesson text and a confirmation of storage.
        """
        prompt = f"Phrase: {phrase} | Context: {source_context}"
        lesson_text = ""

        try:
            # 1. Generate the Lesson Content using the LLM
            response = self.client.models.generate_content(
                model='gemini-2.5-flash-preview-09-2025',
                contents=[prompt],
                config=types.GenerateContentConfig(
                    system_instruction=self.system_instruction
                )
            )
            lesson_text = response.text
            lesson_text = self._sanitize_lesson_text(lesson_text)
            # try to determine canonical phrase (prefer labeled)
            canonical = self._canonical_from_labels(lesson_text) or self._canonical_from_labels(self._to_html(lesson_text))
            if not canonical:
                m = re.search(r'<<([^>]+)>>', lesson_text)
                if m and m.group(1).strip():
                    canonical = m.group(1).strip()
            if not canonical:
                m2 = re.search(r'<strong>([^<]+)</strong>', self._to_html(lesson_text), re.IGNORECASE)
                if m2 and m2.group(1).strip():
                    canonical = m2.group(1).strip()
            # fallback
            canonical = canonical or (phrase or '').strip()

            # extract definition and two examples (or synthesize)
            definition, examples = self._extract_definition_and_examples(lesson_text, canonical)

            # Build a standardized lesson_text that contains exactly one canonical phrase and two examples
            std_lines = []
            # What to improve: try to keep existing short note if present
            m_w = re.search(r'What to improve\s*[:\-]?\s*(.*?)(?:\n\n|\nPhrase to learn:|\nDefinition:|$)', lesson_text, re.IGNORECASE | re.DOTALL)
            what_to_improve = (m_w.group(1).strip() if m_w else '').strip()
            if not what_to_improve:
                what_to_improve = '(none)'
            std_lines.append(f"What to improve: {what_to_improve}")
            std_lines.append(f"Phrase to learn: <<{canonical}>>")
            std_lines.append(f"Definition: {definition}")
            std_lines.append("Examples:")
            for ex in examples:
                std_lines.append(ex)
            # optional Notes if present in original
            m_notes = re.search(r'Notes\s*[:\-]?\s*(.+)', lesson_text, re.IGNORECASE | re.DOTALL)
            if m_notes:
                notes = m_notes.group(1).strip()
                std_lines.append(f"Notes: {notes}")

            lesson_text_std = "\n".join(std_lines)
            lesson_html = self._to_html(lesson_text_std)

            # Store canonical phrase only once and normalized
            memory_status = self.memory_bank.add_phrase(
                phrase=canonical,
                meaning=definition,
                source_context=None,
                corrected_context=source_context,
                lesson_text=lesson_text_std,
                lesson_html=lesson_html,
            )

            # Return plain lesson text and HTML separately
            return lesson_text_std, lesson_html

        except Exception as e:
            # on error, return error string and None for html
            return f"Error in Teacher Agent: {e}", None