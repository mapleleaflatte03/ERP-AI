"""
ERPX AI Accounting - Policy Engine
==================================
PR-9: Guardrails for journal proposal validation.

Rule Types:
- threshold: Amount limits (auto-approve under X, reject over Y)
- vendor_allowlist: Allowed/denied vendor list
- balanced: Debits must equal credits
- tax_sanity: VAT rate validation (8-12%)
- entry_count: Journal entry count limits
"""

import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger("erpx.policy")


class RuleResult(str, Enum):
    """Result of a policy rule evaluation."""

    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    SKIP = "skip"  # Rule not applicable


class OverallResult(str, Enum):
    """Overall policy evaluation result."""

    APPROVED = "approved"  # All rules passed, can auto-approve
    REJECTED = "rejected"  # Critical rule failed, auto-reject
    REQUIRES_REVIEW = "requires_review"  # Some rules failed, needs human


@dataclass
class RuleEvaluation:
    """Single rule evaluation result."""

    rule_name: str
    rule_type: str
    result: RuleResult
    message: str
    action_on_fail: str = "require_review"

    def to_dict(self) -> dict:
        return {
            "rule": self.rule_name,
            "type": self.rule_type,
            "result": self.result.value,
            "message": self.message,
            "action": self.action_on_fail,
        }


@dataclass
class PolicyEvaluation:
    """Complete policy evaluation result."""

    job_id: str
    proposal_id: str | None
    overall_result: OverallResult
    rules_passed: int
    rules_failed: int
    rules_warned: int
    details: list[RuleEvaluation]
    auto_approved: bool = False

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "proposal_id": self.proposal_id,
            "overall_result": self.overall_result.value,
            "rules_passed": self.rules_passed,
            "rules_failed": self.rules_failed,
            "rules_warned": self.rules_warned,
            "auto_approved": self.auto_approved,
            "details": [d.to_dict() for d in self.details],
        }


# ===========================================================================
# Rule Evaluators
# ===========================================================================


def evaluate_threshold(
    proposal: dict,
    config: dict,
    rule_name: str,
) -> RuleEvaluation:
    """
    Evaluate amount threshold rule.

    Config:
        max_amount: Maximum amount for auto-approve
        currency: Expected currency (optional)
    """
    max_amount = config.get("max_amount", 10000000)  # 10M VND default
    total = float(proposal.get("total_amount", 0))

    if total <= max_amount:
        return RuleEvaluation(
            rule_name=rule_name,
            rule_type="threshold",
            result=RuleResult.PASS,
            message=f"Amount {total:,.0f} within threshold {max_amount:,.0f}",
        )
    else:
        return RuleEvaluation(
            rule_name=rule_name,
            rule_type="threshold",
            result=RuleResult.FAIL,
            message=f"Amount {total:,.0f} exceeds threshold {max_amount:,.0f}",
            action_on_fail="require_review",
        )


def evaluate_balanced(
    proposal: dict,
    config: dict,
    rule_name: str,
) -> RuleEvaluation:
    """
    Evaluate balanced journal rule.

    Config:
        tolerance: Allowed difference (default 0.01)
    """
    tolerance = config.get("tolerance", 0.01)
    entries = proposal.get("entries", [])

    if not entries:
        return RuleEvaluation(
            rule_name=rule_name,
            rule_type="balanced",
            result=RuleResult.FAIL,
            message="No journal entries found",
            action_on_fail="auto_reject",
        )

    total_debit = sum(float(e.get("debit", 0)) for e in entries)
    total_credit = sum(float(e.get("credit", 0)) for e in entries)

    diff = abs(total_debit - total_credit)

    if diff <= tolerance:
        return RuleEvaluation(
            rule_name=rule_name,
            rule_type="balanced",
            result=RuleResult.PASS,
            message=f"Journal balanced: Debit={total_debit:,.0f}, Credit={total_credit:,.0f}",
        )
    else:
        return RuleEvaluation(
            rule_name=rule_name,
            rule_type="balanced",
            result=RuleResult.FAIL,
            message=f"Journal unbalanced: Debit={total_debit:,.0f}, Credit={total_credit:,.0f}, Diff={diff:,.2f}",
            action_on_fail="auto_reject",
        )


def evaluate_entry_count(
    proposal: dict,
    config: dict,
    rule_name: str,
) -> RuleEvaluation:
    """
    Evaluate entry count rule.

    Config:
        min: Minimum entries (default 2)
        max: Maximum entries (default 20)
    """
    min_count = config.get("min", 2)
    max_count = config.get("max", 20)
    entries = proposal.get("entries", [])
    count = len(entries)

    if count < min_count:
        return RuleEvaluation(
            rule_name=rule_name,
            rule_type="entry_count",
            result=RuleResult.FAIL,
            message=f"Too few entries: {count} < {min_count}",
            action_on_fail="require_review",
        )
    elif count > max_count:
        return RuleEvaluation(
            rule_name=rule_name,
            rule_type="entry_count",
            result=RuleResult.FAIL,
            message=f"Too many entries: {count} > {max_count}",
            action_on_fail="require_review",
        )
    else:
        return RuleEvaluation(
            rule_name=rule_name,
            rule_type="entry_count",
            result=RuleResult.PASS,
            message=f"Entry count OK: {count} (range: {min_count}-{max_count})",
        )


def evaluate_tax_sanity(
    proposal: dict,
    config: dict,
    rule_name: str,
) -> RuleEvaluation:
    """
    Evaluate VAT rate sanity.

    Config:
        min_rate: Minimum expected rate (default 0.08)
        max_rate: Maximum expected rate (default 0.12)
    """
    min_rate = config.get("min_rate", 0.08)
    max_rate = config.get("max_rate", 0.12)

    total = float(proposal.get("total_amount", 0))
    vat = float(proposal.get("vat_amount", 0))

    if total == 0:
        return RuleEvaluation(
            rule_name=rule_name,
            rule_type="tax_sanity",
            result=RuleResult.SKIP,
            message="No total amount to validate tax",
        )

    if vat == 0:
        return RuleEvaluation(
            rule_name=rule_name,
            rule_type="tax_sanity",
            result=RuleResult.WARN,
            message="VAT amount is zero",
            action_on_fail="warn_only",
        )

    # Calculate effective rate: VAT / (Total - VAT)
    base = total - vat
    if base <= 0:
        return RuleEvaluation(
            rule_name=rule_name,
            rule_type="tax_sanity",
            result=RuleResult.WARN,
            message="Invalid VAT calculation (base <= 0)",
            action_on_fail="warn_only",
        )

    rate = vat / base

    if min_rate <= rate <= max_rate:
        return RuleEvaluation(
            rule_name=rule_name,
            rule_type="tax_sanity",
            result=RuleResult.PASS,
            message=f"VAT rate {rate * 100:.1f}% within range ({min_rate * 100:.0f}%-{max_rate * 100:.0f}%)",
        )
    else:
        return RuleEvaluation(
            rule_name=rule_name,
            rule_type="tax_sanity",
            result=RuleResult.WARN,
            message=f"VAT rate {rate * 100:.1f}% outside expected range ({min_rate * 100:.0f}%-{max_rate * 100:.0f}%)",
            action_on_fail="warn_only",
        )


def evaluate_vendor_allowlist(
    proposal: dict,
    config: dict,
    rule_name: str,
) -> RuleEvaluation:
    """
    Evaluate vendor allowlist/denylist.

    Config:
        vendors: List of vendor patterns
        mode: "allow" (only these) or "deny" (block these)
    """
    vendors = config.get("vendors", [])
    mode = config.get("mode", "allow")
    proposal_vendor = (proposal.get("vendor") or "").lower().strip()

    if not vendors:
        return RuleEvaluation(
            rule_name=rule_name,
            rule_type="vendor_allowlist",
            result=RuleResult.SKIP,
            message="No vendor list configured",
        )

    if not proposal_vendor:
        return RuleEvaluation(
            rule_name=rule_name,
            rule_type="vendor_allowlist",
            result=RuleResult.WARN,
            message="No vendor name in proposal",
            action_on_fail="warn_only",
        )

    # Check if vendor matches any pattern
    matched = False
    for pattern in vendors:
        pattern_lower = pattern.lower().strip()
        if pattern_lower in proposal_vendor or proposal_vendor in pattern_lower:
            matched = True
            break
        # Try regex
        try:
            if re.search(pattern_lower, proposal_vendor):
                matched = True
                break
        except re.error:
            pass

    if mode == "allow":
        if matched:
            return RuleEvaluation(
                rule_name=rule_name,
                rule_type="vendor_allowlist",
                result=RuleResult.PASS,
                message=f"Vendor '{proposal_vendor}' is in allowlist",
            )
        else:
            return RuleEvaluation(
                rule_name=rule_name,
                rule_type="vendor_allowlist",
                result=RuleResult.FAIL,
                message=f"Vendor '{proposal_vendor}' not in allowlist",
                action_on_fail="require_review",
            )
    else:  # deny mode
        if matched:
            return RuleEvaluation(
                rule_name=rule_name,
                rule_type="vendor_allowlist",
                result=RuleResult.FAIL,
                message=f"Vendor '{proposal_vendor}' is in denylist",
                action_on_fail="auto_reject",
            )
        else:
            return RuleEvaluation(
                rule_name=rule_name,
                rule_type="vendor_allowlist",
                result=RuleResult.PASS,
                message=f"Vendor '{proposal_vendor}' not in denylist",
            )


# ===========================================================================
# Main Policy Engine
# ===========================================================================

# Mapping of rule types to evaluators
RULE_EVALUATORS = {
    "threshold": evaluate_threshold,
    "balanced": evaluate_balanced,
    "entry_count": evaluate_entry_count,
    "tax_sanity": evaluate_tax_sanity,
    "vendor_allowlist": evaluate_vendor_allowlist,
}


async def get_active_rules(conn, tenant_id: str | None = None) -> list[dict]:
    """
    Get active policy rules for a tenant.

    Returns system rules (tenant_id=NULL) + tenant-specific rules.
    """
    query = """
        SELECT id, name, rule_type, priority, config, action_on_fail
        FROM policy_rules
        WHERE is_active = TRUE
        AND (tenant_id IS NULL OR tenant_id = $1)
        ORDER BY priority ASC, created_at ASC
    """
    tenant_uuid = uuid.UUID(tenant_id) if tenant_id and len(str(tenant_id)) > 10 else None
    rows = await conn.fetch(query, tenant_uuid)

    return [
        {
            "id": str(row["id"]),
            "name": row["name"],
            "rule_type": row["rule_type"],
            "priority": row["priority"],
            "config": row["config"] if isinstance(row["config"], dict) else json.loads(row["config"] or "{}"),
            "action_on_fail": row["action_on_fail"],
        }
        for row in rows
    ]


async def evaluate_proposal(
    conn,
    proposal: dict,
    job_id: str,
    proposal_id: str | None = None,
    tenant_id: str | None = None,
    request_id: str | None = None,
) -> PolicyEvaluation:
    """
    Evaluate a proposal against all active policy rules.

    Returns:
        PolicyEvaluation with overall result and per-rule details
    """
    rules = await get_active_rules(conn, tenant_id)
    evaluations: list[RuleEvaluation] = []

    passed = 0
    failed = 0
    warned = 0
    has_auto_reject = False

    for rule in rules:
        rule_type = rule["rule_type"]
        evaluator = RULE_EVALUATORS.get(rule_type)

        if not evaluator:
            logger.warning(f"[{request_id}] Unknown rule type: {rule_type}")
            continue

        try:
            result = evaluator(proposal, rule["config"], rule["name"])
            result.action_on_fail = rule["action_on_fail"]
            evaluations.append(result)

            if result.result == RuleResult.PASS:
                passed += 1
            elif result.result == RuleResult.FAIL:
                failed += 1
                if result.action_on_fail == "auto_reject":
                    has_auto_reject = True
            elif result.result == RuleResult.WARN:
                warned += 1

        except Exception as e:
            logger.error(f"[{request_id}] Rule evaluation error ({rule['name']}): {e}")
            evaluations.append(
                RuleEvaluation(
                    rule_name=rule["name"],
                    rule_type=rule_type,
                    result=RuleResult.WARN,
                    message=f"Evaluation error: {str(e)}",
                    action_on_fail="warn_only",
                )
            )
            warned += 1

    # Determine overall result
    if has_auto_reject:
        overall = OverallResult.REJECTED
        auto_approved = False
    elif failed > 0:
        overall = OverallResult.REQUIRES_REVIEW
        auto_approved = False
    else:
        overall = OverallResult.APPROVED
        # Auto-approve only if all threshold checks passed
        auto_approved = any(e.rule_type == "threshold" and e.result == RuleResult.PASS for e in evaluations)

    evaluation = PolicyEvaluation(
        job_id=job_id,
        proposal_id=proposal_id,
        overall_result=overall,
        rules_passed=passed,
        rules_failed=failed,
        rules_warned=warned,
        details=evaluations,
        auto_approved=auto_approved,
    )

    # Persist evaluation to DB
    await save_policy_evaluation(conn, evaluation, tenant_id, request_id)

    logger.info(
        f"[{request_id}] Policy evaluation for {job_id}: {overall.value} (pass={passed}, fail={failed}, warn={warned})"
    )

    return evaluation


async def save_policy_evaluation(
    conn,
    evaluation: PolicyEvaluation,
    tenant_id: str | None = None,
    request_id: str | None = None,
):
    """Save policy evaluation to database."""
    try:
        await conn.execute(
            """
            INSERT INTO policy_evaluations
            (job_id, proposal_id, tenant_id, overall_result, rules_passed, 
             rules_failed, rules_warned, details, auto_approved, request_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::text)
            """,
            evaluation.job_id,
            uuid.UUID(evaluation.proposal_id) if evaluation.proposal_id else None,
            uuid.UUID(tenant_id) if tenant_id and len(str(tenant_id)) > 10 else None,
            evaluation.overall_result.value,
            evaluation.rules_passed,
            evaluation.rules_failed,
            evaluation.rules_warned,
            json.dumps([d.to_dict() for d in evaluation.details]),
            evaluation.auto_approved,
            request_id,
        )
    except Exception as e:
        logger.error(f"[{request_id}] Failed to save policy evaluation: {e}")


async def get_policy_evaluation(
    conn,
    job_id: str,
) -> dict | None:
    """Get latest policy evaluation for a job."""
    row = await conn.fetchrow(
        """
        SELECT * FROM policy_evaluations
        WHERE job_id = $1
        ORDER BY evaluated_at DESC
        LIMIT 1
        """,
        job_id,
    )

    if not row:
        return None

    return {
        "id": str(row["id"]),
        "job_id": row["job_id"],
        "proposal_id": str(row["proposal_id"]) if row["proposal_id"] else None,
        "evaluated_at": row["evaluated_at"].isoformat() if row["evaluated_at"] else None,
        "overall_result": row["overall_result"],
        "rules_passed": row["rules_passed"],
        "rules_failed": row["rules_failed"],
        "rules_warned": row["rules_warned"],
        "details": row["details"] if isinstance(row["details"], list) else json.loads(row["details"] or "[]"),
        "auto_approved": row["auto_approved"],
        "request_id": row["request_id"],
    }
