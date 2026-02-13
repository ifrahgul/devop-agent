import re
from datetime import datetime

ERROR_PATTERNS = {
    "Exception Occurred": [r"Exception", r"ERROR", r"CRITICAL"],
    "Timeout Error": [r"timeout", r"timed out", r"connection lost"],
    "Disk Full": [r"disk full", r"No space left on device"],
    "Permission Denied": [r"Permission denied", r"Access is denied"],
    "Unknown system error": [r".*"]  # fallback pattern
}

def determine_confidence(pattern_matched):
    if pattern_matched in ["Exception Occurred", "Timeout Error", "Disk Full", "Permission Denied"]:
        return "High"
    elif pattern_matched == "Unknown system error":
        return "Low"
    else:
        return "Medium"

def analyze_errors(log_lines, use_ai=True):
    """
    Analyze logs and return summary and detailed lists.
    summary = {total_errors, unknown_errors, confidence_counts}
    detailed = list of dicts with keys: log_line, confidence, probable_cause, timestamp
    """
    detailed = []

    for line in log_lines:
        line_lower = line.lower()
        matched = False
        probable_cause = "Unknown system error"


        for cause, patterns in ERROR_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, line, re.IGNORECASE):
                    probable_cause = cause
                    matched = True
                    break
            if matched:
                break

        confidence = determine_confidence(probable_cause)
        timestamp_match = re.search(r"\b(\d{8,14})\b", line)
        timestamp = None
        if timestamp_match:
            ts_str = timestamp_match.group(1)
            try:
                if len(ts_str) == 8:
                    timestamp = datetime.strptime(ts_str, "%Y%m%d")
                elif len(ts_str) == 14:
                    timestamp = datetime.strptime(ts_str, "%Y%m%d%H%M%S")
            except:
                timestamp = None

        detailed.append({
            "log_line": line,
            "confidence": confidence,
            "probable_cause": probable_cause,
            "timestamp": timestamp
        })


    total_errors = len(detailed)
    unknown_errors = len([d for d in detailed if d['probable_cause']=="Unknown system error"])
    confidence_counts = {
        "High": len([d for d in detailed if d['confidence']=="High"]),
        "Medium": len([d for d in detailed if d['confidence']=="Medium"]),
        "Low": len([d for d in detailed if d['confidence']=="Low"])
    }

    summary = {
        "total_errors": total_errors,
        "unknown_errors": unknown_errors,
        "confidence_counts": confidence_counts
    }

    return summary, detailed

def ai_suggest_error(log_line, probable_cause=None, confidence=None, timestamp=None):
    """
    Returns an AI-like suggestion for a log line.
    Works for all confidence levels.
    """
    if not log_line:
        return "No log line provided."

    suggestion = ""
    if confidence == "High":
        suggestion = f"Immediate attention recommended: {probable_cause}."
    elif confidence == "Medium":
        suggestion = f"Investigate potential issues: {probable_cause}."
    else:
        suggestion = f"Possible fix or check context: {probable_cause}."

    if timestamp:
        suggestion += f" Occurred on {timestamp.strftime('%Y-%m-%d')}."

    return suggestion
