from .constants import LOW, MODERATE, HIGH, REQURED_RETURN_THRESHOLD, TIME_HORIZON_THRESHOLD, BEHAVIORAL_RISK_TIER_THRESHOLD

def solve_required_return(current_portfolio_value: float, annual_net_cash_flow: float, investment_time_horizon_years: int, target_future_value: float, tol: float = 1e-6, max_iter: int = 1000) -> float:

    A = current_portfolio_value
    S = annual_net_cash_flow
    T = investment_time_horizon_years
    G = target_future_value

    def future_value(r):
        if abs(r) < 1e-10:
            return A + S * T
        return A * (1 + r) ** T + S * (((1 + r) ** T - 1) / r)

    low, high = -0.99, 1.0

    for _ in range(max_iter):
        mid = (low + high) / 2
        fv = future_value(mid)

        if abs(fv - G) < tol:
            return mid

        if fv < G:
            low = mid
        else:
            high = mid

        if abs(high - low) < tol:
            break

    return (low + high) / 2

def get_user_risk_need_tier(target_future_value: float, current_portfolio_value: float, investment_time_horizon_years: int, annual_net_cash_flow: float):

    r = solve_required_return(
        current_portfolio_value,
        annual_net_cash_flow,
        investment_time_horizon_years,
        target_future_value
    )

    if r <= REQURED_RETURN_THRESHOLD[LOW]:
        tier = LOW
    elif r <= REQURED_RETURN_THRESHOLD[MODERATE]:
        tier = MODERATE
    else:
        tier = HIGH

    return {
        "tier": tier,
        "required_rate_of_return": round(r, 4)
    }


def get_user_risk_capacity_tier(tolerance_time_horizon_years: int, expects_high_withdrawal_rate: bool, has_stable_external_income: bool):

    if (
        tolerance_time_horizon_years <= TIME_HORIZON_THRESHOLD[LOW] or
        (expects_high_withdrawal_rate and not has_stable_external_income)
    ):
        tier = LOW

    elif (
        tolerance_time_horizon_years >= TIME_HORIZON_THRESHOLD[HIGH] and
        not expects_high_withdrawal_rate and
        has_stable_external_income
    ):
        tier = HIGH

    else:
        tier = MODERATE

    return {
        "tier": tier
    }
    
def get_user_behavioral_risk_tier(willingness_to_take_risk: int, safety_vs_return_preference: int, financial_knowledge_level: int, investment_experience_level: int, market_risk_perception: int, reaction_to_losses_score: int):

    scores = [
        willingness_to_take_risk,
        safety_vs_return_preference,
        financial_knowledge_level,
        investment_experience_level,
        market_risk_perception,
        reaction_to_losses_score
    ]

    for score in scores:
        if score < 1 or score > 5:
            raise ValueError("Scores must be between 1 and 5")

    total_score = sum(scores)

    if 6 <= total_score <= BEHAVIORAL_RISK_TIER_THRESHOLD[LOW]:
        tier = LOW
    elif total_score <= BEHAVIORAL_RISK_TIER_THRESHOLD[MODERATE]:
        tier = MODERATE
    else:
        tier = HIGH

    return {
        "tier": tier,
        "total_score": total_score
    }