import json
import re
from pathlib import Path

MEMORY_FILE = Path(__file__).resolve().parent.parent / 'memory_bank.json'

LABEL_PATTERNS = [
    r'Suggested colloquial phrase[:\s]*<<([^>]+)>>',
    r'Suggested colloquial phrase[:\s]*"?([^\n<"]+)"?',
    r'Phrase to learn[:\s]*<<([^>]+)>>',
    r'Phrase to learn[:\s]*"?([^\n<"]+)"?',
    r'LESSON[:\s]*<?strong>?>?\s*([^<\n]+)',
]

DEF_PATTERNS = [
    r'Definition[:\-\s]*([^\n\.]+)',
    r'Meaning[:\-\s]*([^\n\.]+)',
    r'is usually defined as (.*?)\.',
]

STRONG_HTML = re.compile(r'<strong>([^<]+)</strong>', re.IGNORECASE)


def extract_canonical(lesson_text: str, lesson_html: str, stored_phrase: str):
    # prefer explicit labeled patterns in plain text
    for pat in LABEL_PATTERNS:
        m = re.search(pat, lesson_text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    # check lesson_html labels
    mhtml = re.search(r'Suggested colloquial phrase[:\s]*<strong>([^<]+)</strong>', lesson_html, re.IGNORECASE)
    if mhtml:
        return mhtml.group(1).strip()
    # fallback: first <<...>> in lesson_text
    m2 = re.search(r'<<([^>]+)>>', lesson_text)
    if m2:
        return m2.group(1).strip()
    # fallback: first <strong> in lesson_html
    m3 = STRONG_HTML.search(lesson_html or '')
    if m3:
        return m3.group(1).strip()
    # last resort: stored phrase
    return stored_phrase


def extract_meaning(lesson_text: str, lesson_html: str, stored_meaning: str):
    for pat in DEF_PATTERNS:
        m = re.search(pat, lesson_text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        m2 = re.search(pat, lesson_html, re.IGNORECASE)
        if m2:
            return m2.group(1).strip()
    return stored_meaning


def clean_context(text: str) -> str:
    if not text:
        return text
    # remove ** and numbered prefixes, and trim
    text = re.sub(r'\*\*', '', text)
    text = re.sub(r'^\d+\.\s*', '', text)
    return text.strip()


def normalize():
    if not MEMORY_FILE.exists():
        print('Memory file not found:', MEMORY_FILE)
        return
    data = json.loads(MEMORY_FILE.read_text(encoding='utf-8'))
    changed = False
    for entry in data:
        lesson_text = entry.get('lesson_text','') or ''
        lesson_html = entry.get('lesson_html','') or ''
        stored_phrase = entry.get('phrase','')
        stored_meaning = entry.get('meaning','')

        canon = extract_canonical(lesson_text, lesson_html, stored_phrase)
        if canon and canon != stored_phrase:
            entry['phrase'] = canon
            changed = True

        meaning = extract_meaning(lesson_text, lesson_html, stored_meaning)
        if meaning and meaning != stored_meaning:
            entry['meaning'] = meaning
            changed = True

        # remove source_context if it's the raw original (detect patterns like '**1. Corrected Text**' or '1. The corrected')
        sc = entry.get('source_context')
        if sc:
            # if it contains '**' or 'Corrected' or starts with numbering, remove it
            if '**' in sc or 'Corrected' in sc:
                entry.pop('source_context', None)
                changed = True
            else:
                entry['source_context'] = clean_context(sc)

        # clean corrected_context
        cc = entry.get('corrected_context')
        if cc:
            entry['corrected_context'] = clean_context(cc)

    if changed:
        MEMORY_FILE.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding='utf-8')
        print('Memory normalized and saved.')
    else:
        print('No changes needed.')


if __name__ == '__main__':
    normalize()
