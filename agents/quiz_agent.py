from agents.review_agent import ReviewAgent

class QuizAgent:
    """Thin wrapper QuizAgent that delegates quiz generation to ReviewAgent.

    Keeps the API aligned with AGENTS_README: QuizAgent.generate_quiz(num_choices)
    """
    def __init__(self, memory_bank):
        self._review = ReviewAgent(memory_bank)

    def generate_quiz(self, num_choices: int = 4):
        return self._review.generate_quiz(num_choices)

    def list_phrases(self):
        return self._review.list_phrases()

    def search(self, q: str):
        return self._review.search(q)
