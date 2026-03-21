from .main_chatbot import FraudDetectionChatbot
from .enhanced_query_analyzer import EnhancedQueryAnalyzer, QueryPreprocessor
from .data_executor import DataExecutor
from .conversation_memory_manager import ConversationMemoryManager
from .answer_construction import (
    RuleBasedAnswerConstructor,
    FollowUpSuggester,
    ReasoningTracer
)
from .fallback import LowConfidenceFallback

# NLP components
from .text_processor import TextPreprocessor
from .spell_checker import SpellChecker
from .kerword_extractor import KeyWordExtractor, NERModule
from .query_analysis import (
    IntentDomainDetector,
    MultiQuestionDetector,
    MathematicalQueryHandler
)

# Vector components (optional)
try:
    from .vector_retriever import VectorRetriever
    VECTOR_AVAILABLE = True
except ImportError:
    VECTOR_AVAILABLE = False

# Domain vocabulary
from .domain_vocabulary import (
    COLUMN_ALIASES,
    ALL_COLUMNS,
    NUMERIC_COLUMNS,
    CATEGORICAL_COLUMNS,
    VALID_FILTER_VALUES,
    INTENT_KEYWORDS
)


__version__ = "1.0.0"

__all__ = [
    # Main chatbot
    "FraudDetectionChatbot",
    
    # Query processing
    "EnhancedQueryAnalyzer",
    "QueryPreprocessor",
    "DataExecutor",
    
    # Memory & answers
    "ConversationMemoryManager",
    "RuleBasedAnswerConstructor",
    "FollowUpSuggester",
    "ReasoningTracer",
    "LowConfidenceFallback",
    
    # NLP components
    "TextPreprocessor",
    "SpellChecker",
    "KeyWordExtractor",
    "NERModule",
    "IntentDomainDetector",
    "MultiQuestionDetector",
    "MathematicalQueryHandler",
    
    # Vector (if available)
    "VectorRetriever",
    "VECTOR_AVAILABLE",
    
    # Constants
    "COLUMN_ALIASES",
    "ALL_COLUMNS",
    "NUMERIC_COLUMNS",
    "CATEGORICAL_COLUMNS",
]
