"""
ERPX Policy Engine Module
=========================
PR-9: Policy guardrails for journal proposals.
"""

from .engine import (
    OverallResult,
    PolicyEvaluation,
    RuleEvaluation,
    RuleResult,
    evaluate_proposal,
    get_active_rules,
    get_policy_evaluation,
    save_policy_evaluation,
)

__all__ = [
    "RuleResult",
    "OverallResult",
    "RuleEvaluation",
    "PolicyEvaluation",
    "evaluate_proposal",
    "get_active_rules",
    "get_policy_evaluation",
    "save_policy_evaluation",
]
