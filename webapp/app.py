import sys, os
# Ensure the project root is on sys.path so top-level imports work when running from the webapp/ folder
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, render_template, request, jsonify
from google import genai
from tools.memory_bank_tool import MemoryBankTool
from agents.corrector_agent import CorrectorAgent
from agents.teacher_agent import TeacherAgent
from agents.review_agent import ReviewAgent
import os

app = Flask(__name__, static_folder='static', template_folder='templates')

# Initialize dependencies (simple, single-instance)
client = genai.Client()
memory_bank = MemoryBankTool()
corrector = CorrectorAgent(client)
teacher = TeacherAgent(client, memory_bank)
reviewmaster = ReviewAgent(memory_bank)

@app.route('/')
def index():
    return render_template('index.html', memory_count=len(memory_bank.memory))

@app.route('/submit', methods=['POST'])
def submit():
    data = request.json or {}
    sentence = data.get('sentence', '').strip()
    if not sentence:
        return jsonify({'error': 'No sentence provided'}), 400

    # Run corrector and attempt to teach
    corrector_output = corrector.run(sentence)
    teaching = None
    lesson_html = None
    lesson_text_out = None

    from main import extract_phrase_for_teaching
    teaching_data = extract_phrase_for_teaching(corrector_output)

    # Fallback: try to extract a candidate phrase directly from the corrector output
    def _fallback_phrase_from_text(text: str):
        import re
        if not text:
            return None
        m = re.search(r'<<([^>]+)>>', text)
        if m and m.group(1).strip():
            return m.group(1).strip()
        m2 = re.search(r'(?:Phrase to learn|Suggested colloquial phrase)\s*[:\-]?\s*(?:<<([^>]+)>>|"?([^\n"]+)"?)', text, re.IGNORECASE)
        if m2:
            return (m2.group(1) or m2.group(2) or '').strip() or None
        # as a last quick heuristic, look for quoted words
        m3 = re.search(r'"([^"]{2,40})"', text)
        if m3:
            return m3.group(1).strip()
        return None

    phrase = None
    context = None

    if teaching_data:
        phrase, context = teaching_data
    else:
        # attempt fallback phrase detection from corrector output
        phrase = _fallback_phrase_from_text(corrector_output)
        # prefer corrected context if available from corrector, else use original sentence
        context = corrector_output or sentence

    try:
        # Call teacher even if phrase is None/empty — teacher will attempt to determine canonical phrase
        teacher_output = teacher.run(phrase or '', context or sentence)
        # Teacher.run may return (lesson_text, lesson_html) or a single string
        lesson_text_out = None
        lesson_html_out = None
        if isinstance(teacher_output, (list, tuple)):
            # expected (lesson_text, lesson_html)
            lesson_text_out = teacher_output[0] if len(teacher_output) > 0 else None
            lesson_html_out = teacher_output[1] if len(teacher_output) > 1 else None
        else:
            lesson_text_out = teacher_output

        # Helper: extract canonical phrase from lesson_text or lesson_html
        def _extract_canonical(lt: str, lh: str):
            import re
            if lt:
                m = re.search(r'(?:Phrase to learn|Suggested colloquial phrase)\s*[:\-]?\s*(?:<<([^>]+)>>|"?([^\n"]+)"?)', lt, re.IGNORECASE)
                if m:
                    return (m.group(1) or m.group(2) or '').strip() or None
                m2 = re.search(r'<<([^>]+)>>', lt)
                if m2 and m2.group(1).strip():
                    return m2.group(1).strip()
            if lh:
                # try to find <strong> that follows 'Phrase to learn' or first strong
                # remove tags and search labels
                plain = re.sub(r'<[^>]+>', '', lh)
                m3 = re.search(r'(?:Phrase to learn|Suggested colloquial phrase)\s*[:\-]?\s*([^\n]+)', plain, re.IGNORECASE)
                if m3:
                    return m3.group(1).strip()
                m4 = re.search(r'<strong>([^<]+)</strong>', lh, re.IGNORECASE)
                if m4 and m4.group(1).strip():
                    return m4.group(1).strip()
            return None

        canonical = _extract_canonical(lesson_text_out or '', lesson_html_out or '')

        # Try to locate the stored memory entry: prefer canonical, fallback to phrase, corrected_context, or most recent
        stored = None
        if canonical:
            stored = next((e for e in memory_bank.memory if e.get('phrase') and e.get('phrase').lower() == canonical.lower()), None)
        if not stored and phrase:
            stored = next((e for e in memory_bank.memory if e.get('phrase') and e.get('phrase').lower() == phrase.lower()), None)
        if not stored and context:
            stored = next((e for e in memory_bank.memory if e.get('corrected_context') and e.get('corrected_context').strip() == (context or '').strip()), None)
        if not stored and memory_bank.memory:
            try:
                stored = max(memory_bank.memory, key=lambda x: x.get('date_added',''))
            except Exception:
                stored = memory_bank.memory[-1]

        # Determine final_phrase to return in 'teaching' (prefer canonical if present)
        final_phrase_out = canonical or (stored.get('phrase') if stored else None) or phrase or ''

        if stored:
            # prefer lesson_html returned from teacher if present, else stored
            lesson_html = lesson_html_out or stored.get('lesson_html')
            teaching = {'phrase': final_phrase_out, 'lesson': lesson_text_out, 'lesson_html': lesson_html}
        else:
            teaching = {'phrase': final_phrase_out, 'lesson': lesson_text_out, 'lesson_html': lesson_html_out}

    except Exception as e:
        return jsonify({'error': f'Teacher failed: {e}'}), 500

    # Sanitize corrector output: remove ** markers and convert suggested emphasis to <strong>
    corrector_html = None
    try:
        co = corrector_output or ''
        co_plain = co.replace('**', '')
        co_html = co_plain.replace('\n', '<br>')
        co_html = co_html.replace('*', '')
        corrector_html = co_html
    except Exception:
        corrector_html = None

    # Return top-level lesson_text and lesson_html for frontend compatibility
    return jsonify({
        'corrector_output': corrector_output,
        'corrector_output_html': corrector_html,
        'teaching': teaching,
        'lesson_text': lesson_text_out,
        'lesson_html': lesson_html or lesson_html_out
    })

@app.route('/memory')
def memory():
    return jsonify({'memory': memory_bank.memory})

@app.route('/quiz')
def quiz():
    # Use ReviewMasterAgent to generate a quiz question (single-choice)
    q = reviewmaster.generate_quiz()
    return jsonify({'quiz': [q] if isinstance(q, dict) else q})

@app.route('/evaluate', methods=['POST'])
def evaluate():
    # Lightweight evaluation: token-overlap against stored meaning
    data = request.json or {}
    phrase = data.get('phrase')
    answer = data.get('answer', '')
    if not phrase:
        return jsonify({'error': 'No phrase provided'}), 400
    # find meaning
    meaning = None
    for item in memory_bank.memory:
        if item.get('phrase','').lower() == (phrase or '').lower():
            meaning = item.get('meaning') or item.get('definition') or ''
            break
    if not meaning:
        return jsonify({'correct': False, 'score': 0.0, 'feedback': 'Phrase not found in memory.'})
    import re
    ua = re.sub(r"[^\w\s]", "", (answer or "").lower())
    meaning_clean = re.sub(r"[^\w\s]", "", meaning.lower())
    ua_words = set(ua.split())
    meaning_words = set(meaning_clean.split())
    if not meaning_words:
        return jsonify({'correct': False, 'score': 0.0, 'feedback': 'No stored meaning to compare against.'})
    common = ua_words & meaning_words
    score = len(common) / max(1, len(meaning_words))
    correct = score >= 0.4 or (meaning_clean and meaning_clean in ua)
    feedback = 'Good answer!' if correct else f"Not quite. Expected meaning (approx): {meaning}"
    return jsonify({'correct': correct, 'score': score, 'feedback': feedback})

@app.route('/review')
def review_page():
    return render_template('review.html')

@app.route('/review_search')
def review_search():
    q = request.args.get('q','')
    results = reviewmaster.search(q)
    return jsonify(results)

@app.route('/review_list')
def review_list():
    # return parsed list for UI
    parsed = reviewmaster.list_phrases()
    return jsonify(parsed)

@app.route('/review_quiz')
def review_quiz():
    question = reviewmaster.generate_quiz()
    return jsonify(question)

@app.route('/quizpage')
def quiz_page():
    return render_template('quiz.html')

@app.route('/quiz_mc')
def quiz_mc():
    # return a single multiple-choice question
    q = reviewmaster.generate_quiz()
    return jsonify(q)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
