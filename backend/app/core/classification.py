def classify_status(status:str) -> str:
    if status.lower() == "non-compliant":
        return"High"
    return"None"
    