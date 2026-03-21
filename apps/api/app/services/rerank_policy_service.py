from typing import Literal

AutoApplyPolicy = Literal["auto_apply", "pending_review", "reject"]

AUTO_APPLY_THRESHOLD = 0.80
PENDING_REVIEW_THRESHOLD = 0.60


def decide_policy(confidence: float) -> AutoApplyPolicy:
    if confidence >= AUTO_APPLY_THRESHOLD:
        return "auto_apply"
    if confidence >= PENDING_REVIEW_THRESHOLD:
        return "pending_review"
    return "reject"
