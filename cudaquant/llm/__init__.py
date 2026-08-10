"""LLM research agent integration — advisory only, never controls trading."""

from cudaquant.llm.agent import ExperimentProposal, LLMBudget, LLMResearchAgent
from cudaquant.llm.tool_budget import SearchBudget
from cudaquant.llm.tool_cache import SearchCache
from cudaquant.llm.tools import BraveSearchTool, FirecrawlTool, TavilySearchTool

__all__ = [
    "LLMBudget",
    "LLMResearchAgent",
    "ExperimentProposal",
    "SearchBudget",
    "SearchCache",
    "BraveSearchTool",
    "TavilySearchTool",
    "FirecrawlTool",
]
