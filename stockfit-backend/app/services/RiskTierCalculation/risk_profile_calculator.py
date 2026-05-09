from .utils import get_user_risk_need_tier, get_user_risk_capacity_tier, get_user_behavioral_risk_tier
from .constants import RISK_DECISION_TABLE

def evaluate_user_risk_profile(
    # Risk Need
    target_future_value: float,
    current_portfolio_value: float,
    investment_time_horizon_years: int,
    annual_net_cash_flow: float,  # +ve = saving, -ve = withdrawal

    # Risk Tolerance
    tolerance_time_horizon_years: int,
    expects_high_withdrawal_rate: bool,  # True if >5% withdrawal expected
    has_stable_external_income: bool,

    # Behavioral Loss Tolerance
    willingness_to_take_risk: int,
    safety_vs_return_preference: int,
    financial_knowledge_level: int,
    investment_experience_level: int,
    market_risk_perception: int,
    reaction_to_losses_score: int
) -> dict:
    """
    Evaluates investor risk profile based on:
    - Risk Need (financial requirement)
    - Risk Capacity (ability to take risk)
    - Behavioral Risk Tolerance (psychological factors)

    Returns a dictionary with overall risk score/tier if possible,
    otherwise return an appropriate message.
    """

    risk_need = get_user_risk_need_tier(
        target_future_value,
        current_portfolio_value,
        investment_time_horizon_years,
        annual_net_cash_flow
    )

    risk_capacity = get_user_risk_capacity_tier(
        tolerance_time_horizon_years,
        expects_high_withdrawal_rate,
        has_stable_external_income
    )

    behavioral = get_user_behavioral_risk_tier(
        willingness_to_take_risk,
        safety_vs_return_preference,
        financial_knowledge_level,
        investment_experience_level,
        market_risk_perception,
        reaction_to_losses_score
    )

    portfolio_recommendation = RISK_DECISION_TABLE.get((risk_need["tier"], risk_capacity["tier"], behavioral["tier"]))
    
    return {
        "portfolio_tier": portfolio_recommendation["portfolio"],
        "signal": portfolio_recommendation["signal"],
        "message": portfolio_recommendation["message"],
        "risk_need_tier": risk_need["tier"],
        "risk_capacity_tier": risk_capacity["tier"],
        "behavioral_risk_tier": behavioral["tier"],
        "required_rate_of_return": risk_need["required_rate_of_return"],
    }