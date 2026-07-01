"""Stock group-message recognition and risk review system."""

from .engine import StockRecognitionEngine
from .evidence_playbook import build_evidence_requirements
from .exit_suggestion import build_suggested_exit_plan
from .holdings import Holding, SellSignal, create_holding, create_holding_from_simulation, load_holdings, monitor_holding
from .models import EvidenceRequirement, GroupMessage, MarketEvidence, OpportunityReview, RiskConfig, SuggestedExitPlan, TrainingPlan, TrainingTier
from .opportunity import build_opportunity_review
from .reporting import build_markdown_report
from .short_term import build_short_term_plan
from .simulation import SimulationPosition, SimulationUpdate, load_simulations, open_simulation_from_result, summarize_simulations, update_simulation
from .technical import review_technical
from .training import build_training_plan

__all__ = [
    "GroupMessage",
    "EvidenceRequirement",
    "MarketEvidence",
    "OpportunityReview",
    "RiskConfig",
    "SuggestedExitPlan",
    "TrainingPlan",
    "TrainingTier",
    "SimulationPosition",
    "SimulationUpdate",
    "Holding",
    "SellSignal",
    "StockRecognitionEngine",
    "create_holding",
    "create_holding_from_simulation",
    "build_evidence_requirements",
    "build_opportunity_review",
    "build_suggested_exit_plan",
    "build_short_term_plan",
    "build_training_plan",
    "load_simulations",
    "load_holdings",
    "open_simulation_from_result",
    "summarize_simulations",
    "update_simulation",
    "monitor_holding",
    "build_markdown_report",
    "review_technical",
]
