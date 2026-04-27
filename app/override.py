import hashlib
import json
from datetime import datetime, timezone

def log_override(old_value, new_value, user):

    event = {
        "old_value": old_value,
        "new_value": new_value,
        "user": user,
        "timestamp": str(datetime.now(timezone.utc))
    }

    event_str = json.dumps(event, sort_keys=True)

    hash_value = hashlib.sha256(event_str.encode()).hexdigest()

    return {
        "event": event,
        "hash": hash_value
    }


if __name__ == "__main__":
    result = log_override("US0378331005", "US0378331006", "ashish")
    print(result)