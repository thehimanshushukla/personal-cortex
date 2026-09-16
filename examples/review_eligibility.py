import json
import sys


def eligibility(record):
    required = ("producer_session", "reviewer_session", "artifact_version")
    if not isinstance(record, dict) or any(
        not isinstance(record.get(key), str) or not record[key].strip()
        for key in required
    ):
        return "REFUSED", "Missing or invalid provenance"
    if record["producer_session"].strip() == record["reviewer_session"].strip():
        return "REFUSED", "Producer and reviewer session match"
    return "ELIGIBLE", "Identity screen passed; substantive review still required"


if __name__ == "__main__":
    try:
        verdict, reason = eligibility(json.load(sys.stdin))
    except (ValueError, OSError):
        verdict, reason = "REFUSED", "Unreadable review intake"
    print(json.dumps({"verdict": verdict, "reason": reason}))
    sys.exit(0 if verdict == "ELIGIBLE" else 2)
