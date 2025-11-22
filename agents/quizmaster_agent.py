# Compatibility shim: quizmaster_agent -> QuizAgent
# The real implementation now lives in agents/quiz_agent.py
from agents.quiz_agent import QuizAgent as QuizMasterAgent

# Expose the class at module level for backward compatibility
__all__ = ["QuizMasterAgent"]
