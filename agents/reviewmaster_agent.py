# Compatibility shim: ReviewMasterAgent -> ReviewAgent
# The real implementation lives in agents/review_agent.py
from agents.review_agent import ReviewAgent as ReviewMasterAgent

# Expose the class at module level for backward compatibility
__all__ = ["ReviewMasterAgent"]
