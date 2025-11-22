from tools.memory_bank_tool import MemoryBankTool
import random
import re

class ReviewAgent:
    """Collects taught phrases and provides search and quiz utilities.

    - list_phrases(): returns all entries (parsed)
    - search(query): simple fuzzy search over phrase, meaning, contexts
    - generate_quiz(num_choices: int = 4): returns a single-choice question with one correct phrase and distractors
    """
    def __init__(self, memory_bank: MemoryBankTool):
        self.memory_bank = memory_bank

    def _canonical_from_labels(self, text: str):
        # Look for explicit labeled phrase lines
        if not text:
            return None
        m = re.search(r'(?:Phrase to learn|Suggested colloquial phrase)\s*[:\-]?\s*(?:<<([^>]+)>>|"?([^\n"]+)"?)', text, re.IGNORECASE)
        if m:
            return (m.group(1) or m.group(2) or '').strip() or None
        return None

    def _extract_canonical_phrase(self, item: dict) -> str:
        lesson_text = (item.get('lesson_text') or '')
        lesson_html = (item.get('lesson_html') or '')
        # 1) labeled phrase in plain text
        lab = self._canonical_from_labels(lesson_text)
        if lab:
            return lab
        # 2) first <<...>> marker in plain text
        m = re.search(r'<<([^>]+)>>', lesson_text)
        if m and m.group(1).strip():
            return m.group(1).strip()
        # 3) first <strong> in html
        m2 = re.search(r'<strong>([^<]+)</strong>', lesson_html, re.IGNORECASE)
        if m2 and m2.group(1).strip():
            return m2.group(1).strip()
        # 4) try labels in html converted to text
        # strip tags and retry
        plain_html = re.sub(r'<[^>]+>', '', lesson_html or '')
        lab2 = self._canonical_from_labels(plain_html)
        if lab2:
            return lab2
        # 5) fallback to stored phrase
        return item.get('phrase') or None

    def _extract_definition(self, lesson_text: str, item: dict) -> str:
        if not lesson_text:
            # try fallback to stored meaning
            return item.get('meaning') or ''
        # Prefer explicit Definition: label in lesson_text
        m = re.search(r'Definition\s*[:\-]?\s*(.+)', lesson_text, re.IGNORECASE)
        if m:
            # stop at double newline or next labeled section
            val = m.group(1).strip()
            val = re.split(r'\n\n|\n[A-Z][a-z]+\s*[:\-]', val)[0].strip()
            return val
        # look for Definition in HTML if present
        m2 = re.search(r'Definition\s*[:\-]?\s*([^<]+)', lesson_text, re.IGNORECASE)
        if m2:
            return m2.group(1).strip()
        # fallback to stored meaning
        if item.get('meaning'):
            return item.get('meaning')
        # last resort: attempt to take the first sentence after the canonical phrase
        phrase = item.get('phrase') or ''
        if phrase:
            # find phrase in lesson_text and take following sentence
            idx = lesson_text.lower().find(phrase.lower())
            if idx != -1:
                after = lesson_text[idx:]
                sents = re.split(r'(?<=[\.\?\!])\s+', after)
                if len(sents) > 1:
                    return sents[1].strip().strip('"')
        return ''

    def _extract_examples(self, lesson_text: str, canonical: str, item: dict) -> list:
        examples = []
        if lesson_text:
            m = re.search(r'Examples?\s*[:\-]?\s*(.*?)(?:\n\n|\nLesson:|\nUsage|$)', lesson_text, re.IGNORECASE | re.DOTALL)
            if m:
                block = m.group(1).strip()
                # split by lines and numbered bullets
                parts = re.split(r'\n+', block)
                for p in parts:
                    s = p.strip()
                    if not s:
                        continue
                    s = re.sub(r'^[\-\*\d\.)\s]+', '', s).strip()
                    # replace <<...>> with content or canonical
                    s = re.sub(r'<<([^>]*)>>', lambda mo: (mo.group(1).strip() or (canonical or '')).strip(), s)
                    # remove any empty angle pairs
                    s = s.replace('<>', '').replace('  ', ' ').strip()
                    if len(s) > 5:
                        examples.append(s)
                    if len(examples) >= 2:
                        break
        # fallback: use any explicit 'Usage' lines
        if len(examples) < 2 and lesson_text:
            usages = re.findall(r'Usage\s*\d*\s*[:\-]?\s*(.+)', lesson_text, re.IGNORECASE)
            for u in usages:
                s = u.strip()
                s = re.sub(r'<<([^>]*)>>', lambda mo: (mo.group(1).strip() or (canonical or '')).strip(), s)
                if s and s not in examples:
                    examples.append(s)
                if len(examples) >= 2:
                    break
        # fallback: use examples stored in item (legacy)
        if len(examples) < 2 and isinstance(item.get('examples'), list):
            for ex in item.get('examples'):
                s = (ex or '').strip()
                if s and s not in examples:
                    examples.append(s)
                if len(examples) >= 2:
                    break
        # fallback: use corrected_context split into short sentences
        if len(examples) < 2 and item.get('corrected_context'):
            ctx = item.get('corrected_context')
            sents = re.split(r'(?<=[\.\?\!])\s+', ctx)
            for sent in sents:
                s = sent.strip()
                if not s:
                    continue
                s = re.sub(r'<<([^>]*)>>', lambda mo: (mo.group(1).strip() or (canonical or '')).strip(), s)
                s = s.replace('<>', '').strip()
                if len(s) > 5 and s not in examples:
                    examples.append(s)
                if len(examples) >= 2:
                    break
        # fallback: sentences in lesson_text containing canonical phrase
        if len(examples) < 2 and canonical and lesson_text:
            for sent in re.findall(r'[^\n\.]+\.', lesson_text):
                if re.search(re.escape(canonical), sent, re.IGNORECASE) or '<<' in sent:
                    s = sent.strip()
                    s = re.sub(r'<<([^>]*)>>', lambda mo: (mo.group(1).strip() or (canonical or '')).strip(), s)
                    s = s.replace('<>', '').strip()
                    if s and s not in examples:
                        examples.append(s)
                    if len(examples) >= 2:
                        break
        # final cleanup
        cleaned = []
        for s in examples:
            s2 = s.replace('<>', '').strip()
            s2 = re.sub(r'\s{2,}', ' ', s2)
            if s2:
                cleaned.append(s2)
            if len(cleaned) >= 2:
                break
        return cleaned[:2]

    def _parse_lesson(self, item: dict) -> dict:
        lesson_text = (item.get('lesson_text') or '')
        canonical = self._extract_canonical_phrase(item) or item.get('phrase') or ''
        definition = self._extract_definition(lesson_text, item) or item.get('meaning') or ''
        examples = self._extract_examples(lesson_text, canonical, item)
        # ensure examples contain canonical phrase where possible and clean angle markers
        cleaned_examples = []
        for ex in examples:
            ex_clean = re.sub(r'<<([^>]*)>>', lambda mo: (mo.group(1).strip() or canonical).strip(), ex)
            ex_clean = ex_clean.replace('<>', canonical or '').strip()
            cleaned_examples.append(ex_clean)
        # If still missing examples, try to fabricate short examples using canonical
        if len(cleaned_examples) < 2 and canonical:
            base = canonical
            if base:
                if len(cleaned_examples) == 0:
                    cleaned_examples.append(f"I used '{base}' in a sentence.")
                if len(cleaned_examples) == 1:
                    cleaned_examples.append(f"Can you say: '{base}' naturally?")
        # ensure phrase is not None
        phrase_out = canonical or item.get('phrase') or ''
        return {
            'phrase': phrase_out,
            'definition': definition,
            'examples': cleaned_examples
        }

    def list_phrases(self):
        return [self._parse_lesson(item) for item in self.memory_bank.memory]

    def search(self, query: str):
        q = (query or '').lower().strip()
        parsed = self.list_phrases()
        if not q:
            return parsed
        results = []
        for item in parsed:
            hay = ' '.join([str(item.get(k, '')).lower() for k in ['phrase','definition']])
            if q in hay:
                results.append(item)
        return results

    def generate_quiz(self, num_choices: int = 4):
        entries = self.memory_bank.memory
        if len(entries) < 1:
            return {'error': 'No phrases available for quiz.'}

        correct = random.choice(entries)
        # ensure we have a phrase and meaning for the correct
        correct_phrase = correct.get('phrase') or self._extract_canonical_phrase(correct) or ''
        correct_meaning = correct.get('meaning') or ''

        distractors = [e for e in entries if (e.get('phrase') or '').lower() != (correct_phrase or '').lower()]
        random.shuffle(distractors)
        distractors = distractors[:max(0, num_choices-1)]

        choices = [d.get('meaning','') or d.get('definition','') or '' for d in distractors]
        choices.append(correct_meaning)
        random.shuffle(choices)

        try:
            correct_index = choices.index(correct_meaning) if correct_meaning in choices else -1
        except Exception:
            correct_index = -1

        question = {
            'question': f"What is the best meaning of the phrase: '{correct_phrase}'?",
            'phrase': correct_phrase,
            'choices': choices,
            'correct_index': correct_index
        }
        return question
