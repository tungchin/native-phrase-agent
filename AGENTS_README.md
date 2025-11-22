Project: Native English Phrase Tutor

Purpose
- Help non-native speakers learn common, colloquial English phrases by providing corrections, concise lessons, and a review/quiz system.

Agent responsibilities (clarified)
- CorrectorAgent
  - Purpose: receive user's sentence and return a corrected version plus a short "What to improve" note (grammar, word choice, phrasing). It should NOT suggest or pick the target phrase to learn.
  - Output: corrected_context (plain text) and a brief "What to improve" explanation.

- TeacherAgent
  - Purpose: consume the corrected_context produced by CorrectorAgent, choose a single canonical phrase or idiom to teach (the teacher decides the best phrase given the corrected sentence and the user's intent), and produce a compact labeled lesson containing:
    - Phrase to learn: (single phrase; mark with <<...>> in plain text)
    - Definition: one clear sentence
    - Examples: exactly two short example sentences using the phrase
    - Notes: short guidance on common usage/context
  - Side effects: save the canonical phrase, definition, examples, corrected_context, plain lesson_text and lesson_html into MemoryBankTool.

- ReviewAgent (previously ReviewMasterAgent)
  - Purpose: load and normalize MemoryBank entries and expose list/search utilities for the UI; present canonical phrase, definition, examples and date added.
  - Does NOT perform teaching; it is a read/search/format layer for the UI and quiz generator.

- QuizAgent (previously QuizMasterAgent)
  - Purpose: generate multiple-choice or short quiz prompts from MemoryBank content (pick a target phrase, produce distractor choices from other stored meanings), and provide an evaluation endpoint for answers.
  - The frontend receives one question at a time and shows feedback; the quiz agent uses a lightweight heuristic to score free-text answers or compares choice selections for MCQs.

Architecture (high level)
- UI (Flask webapp)
  - /submit -> sends user sentence
  - /review_list, /review_search -> review pages
  - /quiz_mc -> request one multiple-choice question
  - /evaluate -> send answer for scoring

- Pipeline (run per submission)
  1. CorrectorAgent: corrects sentence, returns corrected_context + "what to improve" notes.
  2. TeacherAgent: reads corrected_context, selects one phrase to teach, builds labeled lesson (Definition, 2 Examples, Notes), saves canonical phrase + lesson to MemoryBank.
  3. MemoryBankTool: persistent storage (JSON) of canonical phrase entries.
  4. ReviewAgent: reads MemoryBank and formats items for the UI (list/search).
  5. QuizAgent: builds and serves quiz questions from MemoryBank.

Demo
- Start Flask app: python3 webapp/app.py (runs on port 5001)
- Home: submit a sentence -> Corrector returns corrected text and "what to improve"; Teacher generates a single-phrase lesson and saves it.
- Review: browse canonical phrases with definition, two examples and date added.
- Quiz: click "Quiz me" to get a single multiple-choice question; submit and receive feedback. If wrong, UI shows the correct answer.

Implementation notes
- Teacher output is prompt-engineered to emit labeled plain-text sections. The app sanitizes and converts <<...>> markers to <strong> for rendering in HTML.
- MemoryBankTool stores entries as objects with keys: phrase, meaning/definition, examples, corrected_context, lesson_text, lesson_html, date_added.
- ReviewAgent focuses on deterministic parsing and normalization so review and quiz use consistent canonical phrases.
- QuizAgent creates MCQs by selecting a target phrase and sampling distractor meanings from other memory entries.

Key concepts mapping
- Multi-agent system: sequential agents implementing the teaching pipeline (Corrector -> Teacher -> Review -> Quiz).
- Agent powered by an LLM: CorrectorAgent and TeacherAgent use an LLM for natural-language correction and lesson generation.
- Tools / Custom tools: MemoryBankTool is a custom tool used by TeacherAgent to persist lessons.
- Sessions & Memory: MemoryBankTool is the project's long-term memory (JSON file). Session-level state is handled by the webapp when needed.
- Context engineering: teacher prompts enforce labeled outputs (What to improve, Phrase to learn, Definition, Examples, Notes) to make parsing reliable.
- Observability: simple logging and saved timestamps (date_added) in MemoryBank entries aid tracing and review ordering.

Where to look in repo
- agents/: CorrectorAgent, TeacherAgent, ReviewAgent, QuizAgent implementations
- tools/: MemoryBankTool and normalization utilities
- webapp/: Flask UI, templates, and static assets

Contact
- Project owner: tungchin
