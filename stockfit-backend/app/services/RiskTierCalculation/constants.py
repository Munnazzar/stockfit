LOW = "LOW"
MODERATE = "MODERATE"
HIGH = "HIGH"

GREEN = "GREEN"
YELLOW = "YELLOW"
RED = "RED"

#Assumed by us
REQURED_RETURN_THRESHOLD = {
    LOW: 0.12,
    MODERATE: 0.20,
    HIGH: 0.30
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
        "message": "All factors align. Proceed with high volatility portfolio."
    },

    (MODERATE, HIGH, HIGH): {
        "signal": GREEN,
        "portfolio": HIGH,
        "message": "Moderate need can be ignored. Proceed with high volatility portfolio."
    },

    (LOW, HIGH, HIGH): {
        "signal": GREEN,
        "portfolio": HIGH,
        "message": "Low need can be ignored. Proceed with high volatility portfolio."
    },

    (MODERATE, MODERATE, MODERATE): {
        "signal": GREEN,
        "portfolio": MODERATE,
        "message": "All factors align. Proceed with moderate volatility portfolio."
    },

    (MODERATE, HIGH, MODERATE): {
        "signal": GREEN,
        "portfolio": MODERATE,
        "message": "High ability can be ignored. Proceed with moderate volatility portfolio."
    },

    (LOW, MODERATE, MODERATE): {
        "signal": GREEN,
        "portfolio": MODERATE,
        "message": "Low need can be ignored. Proceed with moderate volatility portfolio."
    },
   #dasdsa
    (LOW, HIGH, MODERATE): {
        "signal": GREEN,
        "portfolio": MODERATE,
        "message": "Proceed: Moderate volatility portfolio. Both low need and high ability can be safely ignored in favor of moderate tolerance"
    },

    (LOW, LOW, LOW): {
        "signal": GREEN,
        "portfolio": LOW,
        "message": "All factors align. Proceed with low volatility portfolio."
    },

    (LOW, HIGH, LOW): {
        "signal": GREEN,
        "portfolio": LOW,
        "message": "Ability ignored. Proceed with low volatility portfolio."
    },

    (LOW, MODERATE, LOW): {
        "signal": GREEN,
        "portfolio": LOW,
        "message": "Moderate ability ignored. Proceed with low volatility portfolio."
    },

    (MODERATE, MODERATE, HIGH): {
        "signal": YELLOW,
        "portfolio": MODERATE,
        "message": "Behavior exceeds ability. Investor education required."
    },

    (LOW, MODERATE, HIGH): {
        "signal": YELLOW,
        "portfolio": MODERATE,
        "message": "Behavior exceeds ability. Low need ignored."
    },

    (LOW, LOW, HIGH): {
        "signal": YELLOW,
        "portfolio": LOW,
        "message": "Behavior exceeds ability. Caution advised."
    },

    (LOW, LOW, MODERATE): {
        "signal": YELLOW,
        "portfolio": LOW,
        "message": "Behavior exceeds ability. Caution advised."
    },

    (HIGH, HIGH, MODERATE): {
        "signal": YELLOW,
        "portfolio": None,
        "message": "Investor unwilling to take required risk. Discussion needed."
    },
#dasdsads
    (HIGH, HIGH, LOW): {
        "signal": YELLOW,
        "portfolio": None,
        "message": "Investor tolerance too low. May need goal adjustment."
    },
    
    (MODERATE, HIGH, LOW): {
        "signal": YELLOW,
        "portfolio": None,
        "message": "Investor tolerance too low. May need goal adjustment."
    },
    
    (MODERATE, MODERATE, LOW): {
        "signal": YELLOW,
        "portfolio": None,
        "message": "Investor tolerance too low. May need goal adjustment."
    },

    (HIGH, MODERATE, HIGH): {
        "signal": RED,
        "portfolio": None,
        "message": "Risk need exceeds capacity. Reevaluate goals."
    },

    (HIGH, MODERATE, MODERATE): {
        "signal": RED,
        "portfolio": None,
        "message": "Risk need exceeds capacity. Reevaluate goals."
    },

    (HIGH, MODERATE, LOW): {
        "signal": RED,
        "portfolio": None,
        "message": "Risk need exceeds capacity. Behavioral mismatch."
    },
#dasdsad
    (HIGH, LOW, HIGH): {
        "signal": RED,
        "portfolio": None,
        "message": "Severe mismatch. Low capacity cannot support goal."
    },

    (HIGH, LOW, MODERATE): {
        "signal": RED,
        "portfolio": None,
        "message": "Severe mismatch. Reevaluate goals."
    },

    (HIGH, LOW, LOW): {
        "signal": RED,
        "portfolio": None,
        "message": "Completely infeasible risk profile."
    },

    (MODERATE, LOW, HIGH): {
        "signal": RED,
        "portfolio": None,
        "message": "Need exceeds capacity + behavior mismatch."
    },

    (MODERATE, LOW, MODERATE): {
        "signal": RED,
        "portfolio": None,
        "message": "Need exceeds capacity."
    },

    (MODERATE, LOW, LOW): {
        "signal": RED,
        "portfolio": None,
        "message": "Infeasible given low capacity."
    },
}