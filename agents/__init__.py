"""agents package exports

Provides canonical class exports for easy imports such as:
  from agents import CorrectorAgent, TeacherAgent, ReviewAgent, QuizAgent

Also re-exports legacy names for compatibility: ReviewMasterAgent, QuizMasterAgent
"""

from .corrector_agent import CorrectorAgent
from .teacher_agent import TeacherAgent
from .review_agent import ReviewAgent
from .quiz_agent import QuizAgent

# Backwards-compatible aliases
ReviewMasterAgent = ReviewAgent
QuizMasterAgent = QuizAgent

__all__ = [
    "CorrectorAgent",
    "TeacherAgent",
    "ReviewAgent",
    "QuizAgent",
    "ReviewMasterAgent",
    "QuizMasterAgent",
]
