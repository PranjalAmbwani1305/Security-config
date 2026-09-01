def calculate_compliance(results) -> float:
    assessed = [
        result
        for result in results
        if result.status.lower() in {
            "compliant",
            "non-compliant",
            "compensating control",
        }
    ]

    if not assessed:
        return 0.0

    compliant = sum(
        1
        for result in assessed
        if result.status.lower() in {
            "compliant",
            "compensating control",
        }
    )

    return (compliant / len(assessed)) * 100