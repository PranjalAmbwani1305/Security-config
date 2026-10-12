def calculate_risk(likelihood:int,impact:int) -> dict:
    score = likelihood * impact
    if score <= 4:
        level = "Low"
    elif score <= 9:
        level = "Medium"
    elif score <= 16:
        level = "High"
    else:
        level = "Critical"
    return {
        "risk_score": score,
        "risk_level":level,
    }