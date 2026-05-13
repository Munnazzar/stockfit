LOW = "LOW"
MODERATE = "MODERATE"
HIGH = "HIGH"

GREEN = "GREEN"
YELLOW = "YELLOW"
RED = "RED"

#Assumed by us
REQUIRED_RETURN_THRESHOLD = {
    LOW:      (1 + 0.12) ** (1/12) - 1,  # ≈ 0.00949 (~0.95%/month)
    MODERATE: (1 + 0.20) ** (1/12) - 1,  # ≈ 0.01531 (~1.53%/month)
    HIGH:     (1 + 0.30) ** (1/12) - 1,  # ≈ 0.02233 (~2.23%/month)
}


#From CFA INSTITUTE (We might adjust to our timeline)
TIME_HORIZON_THRESHOLD = {
    LOW: 0.5,
    HIGH: 1
}

#From CFA INSTITUTE
BEHAVIORAL_RISK_TIER_THRESHOLD = {
    LOW: 13,
    MODERATE: 22,
    HIGH: 30
}


# key: (Need, Ability, Behavioral)
RISK_DECISION_TABLE = {
    (HIGH, HIGH, HIGH): {
        "signal": GREEN,
        "portfolio": HIGH,
        "message": "All factors align. You may proceed with a high volatility portfolio."
    },

    (MODERATE, HIGH, HIGH): {
        "signal": GREEN,
        "portfolio": HIGH,
        "message": "Your moderate risk need can be safely ignored. You may proceed with a high volatility portfolio."
    },

    (LOW, HIGH, HIGH): {
        "signal": GREEN,
        "portfolio": HIGH,
        "message": "Your low risk need can be safely ignored. You may proceed with a high volatility portfolio."
    },

    (MODERATE, MODERATE, MODERATE): {
        "signal": GREEN,
        "portfolio": MODERATE,
        "message": "All factors align. You may proceed with a moderate volatility portfolio."
    },

    (MODERATE, HIGH, MODERATE): {
        "signal": GREEN,
        "portfolio": MODERATE,
        "message": "Your high risk-taking ability can be safely ignored. You may proceed with a moderate volatility portfolio."
    },

    (LOW, MODERATE, MODERATE): {
        "signal": GREEN,
        "portfolio": MODERATE,
        "message": "Your low risk need can be safely ignored. You may proceed with a moderate volatility portfolio."
    },

    (LOW, HIGH, MODERATE): {
        "signal": GREEN,
        "portfolio": MODERATE,
        "message": "Both your low risk need and high risk-taking ability can be safely ignored in favor of your moderate loss tolerance. You may proceed with a moderate volatility portfolio."
    },

    (LOW, LOW, LOW): {
        "signal": GREEN,
        "portfolio": LOW,
        "message": "All factors align. You may proceed with a low volatility portfolio."
    },

    (LOW, HIGH, LOW): {
        "signal": GREEN,
        "portfolio": LOW,
        "message": "Your high risk-taking ability can be safely ignored. You may proceed with a low volatility portfolio."
    },

    (LOW, MODERATE, LOW): {
        "signal": GREEN,
        "portfolio": LOW,
        "message": "Your moderate risk-taking ability can be safely ignored. You may proceed with a low volatility portfolio."
    },

    (MODERATE, MODERATE, HIGH): {
        "signal": YELLOW,
        "portfolio": MODERATE,
        "message": "Caution: Your loss tolerance exceeds your risk-taking ability. You may expect or desire more volatility than is prudent. Some education may be required before proceeding with a moderate volatility portfolio."
    },

    (LOW, MODERATE, HIGH): {
        "signal": YELLOW,
        "portfolio": MODERATE,
        "message": "Caution: Your loss tolerance exceeds your risk-taking ability. You may expect or desire more volatility than is prudent. Your low risk need can be safely ignored. Some education may be required before proceeding with a moderate volatility portfolio."
    },

    (LOW, LOW, HIGH): {
        "signal": YELLOW,
        "portfolio": LOW,
        "message": "Caution: Your loss tolerance exceeds your risk-taking ability. You may expect or desire more volatility than is prudent. Some education may be required before proceeding with a low volatility portfolio."
    },

    (LOW, LOW, MODERATE): {
        "signal": YELLOW,
        "portfolio": LOW,
        "message": "Caution: Your loss tolerance exceeds your risk-taking ability. You may expect or desire more volatility than is prudent. Some education may be required before proceeding with a low volatility portfolio."
    },

    (HIGH, HIGH, MODERATE): {
        "signal": YELLOW,
        "portfolio": None,
        "message": "Caution: Your loss tolerance is lower than your risk need and risk-taking ability. You may need guidance to feel comfortable increasing your volatility exposure to meet your goals. Do not assume you are willing to increase volatility. Reevaluating your goal to align with your behavioral loss tolerance may be necessary."
    },

    (HIGH, HIGH, LOW): {
        "signal": YELLOW,
        "portfolio": None,
        "message": "Caution: Your loss tolerance is lower than your risk need and risk-taking ability. You may need guidance to feel comfortable increasing your volatility exposure to meet your goals. Do not assume you are willing to increase volatility. Reevaluating your goal to align with your behavioral loss tolerance may be necessary."
    },

    (MODERATE, HIGH, LOW): {
        "signal": YELLOW,
        "portfolio": None,
        "message": "Caution: Your loss tolerance is lower than your risk need and risk-taking ability. You may need guidance to feel comfortable increasing your volatility exposure to meet your goals. Do not assume you are willing to increase volatility. Reevaluating your goal to align with your behavioral loss tolerance may be necessary."
    },

    (MODERATE, MODERATE, LOW): {
        "signal": YELLOW,
        "portfolio": None,
        "message": "Caution: Your loss tolerance is lower than your risk need and risk-taking ability. You may need guidance to feel comfortable increasing your volatility exposure to meet your goals. Do not assume you are willing to increase volatility. Reevaluating your goal to align with your behavioral loss tolerance may be necessary."
    },

    (HIGH, MODERATE, HIGH): {
        "signal": RED,
        "portfolio": None,
        "message": "Your risk need exceeds your risk-taking ability. Even though your need and loss tolerance point to a high volatility portfolio, your moderate ability means you can withstand only a moderate volatility strategy. Please reestablish your expectations and reevaluate your goals."
    },

    (HIGH, MODERATE, MODERATE): {
        "signal": RED,
        "portfolio": None,
        "message": "Your risk need exceeds your risk-taking ability. You have only a moderate ability and can withstand only a moderate volatility strategy. Please reestablish your expectations and reevaluate your goals."
    },

    (HIGH, MODERATE, LOW): {
        "signal": RED,
        "portfolio": None,
        "message": "Your risk need exceeds your risk-taking ability. You have only a moderate ability and can withstand only a moderate volatility strategy. You may need guidance to feel comfortable increasing your volatility exposure; reevaluating your goal to align with your behavioral loss tolerance may be necessary instead."
    },

    (HIGH, LOW, HIGH): {
        "signal": RED,
        "portfolio": None,
        "message": "Your risk need exceeds your risk-taking ability. You have a low ability and can withstand only a low volatility strategy. You may need guidance to feel comfortable increasing your volatility exposure; reevaluating your goal to align with your behavioral loss tolerance may be necessary instead."
    },

    (HIGH, LOW, MODERATE): {
        "signal": RED,
        "portfolio": None,
        "message": "Your risk need exceeds your risk-taking ability. You have a low ability and can withstand only a low volatility strategy. You may need guidance to feel comfortable increasing your volatility exposure; reevaluating your goal to align with your behavioral loss tolerance may be necessary instead."
    },

    (HIGH, LOW, LOW): {
        "signal": RED,
        "portfolio": None,
        "message": "Your risk need exceeds your risk-taking ability. You have a low ability and can withstand only a low volatility strategy. Please reestablish your expectations and reevaluate your goals."
    },

    (MODERATE, LOW, HIGH): {
        "signal": RED,
        "portfolio": None,
        "message": "Your risk need exceeds your risk-taking ability, and your loss tolerance also exceeds your risk-taking ability. You may expect or desire more volatility than is prudent. You have a low ability and can withstand only a low volatility strategy. Additional education is warranted."
    },

    (MODERATE, LOW, MODERATE): {
        "signal": RED,
        "portfolio": None,
        "message": "Your risk need exceeds your risk-taking ability, and your loss tolerance also exceeds your risk-taking ability. You may expect or desire more volatility than is prudent. You have a low ability and can withstand only a low volatility strategy. Additional education is warranted."
    },

    (MODERATE, LOW, LOW): {
        "signal": RED,
        "portfolio": None,
        "message": "Your risk need exceeds your risk-taking ability. You have a low ability and can withstand only a low volatility strategy. Please reestablish your expectations and reevaluate your goals."
    },
}