
import re

def _cancel_regex():
    cancels = {"en": "Cancel", "ar": "إلغاء"} # Simulated
    escaped = [re.escape(t) for t in cancels.values() if t]
    return r"^(" + "|".join(escaped) + r")" if escaped else r"^Cancel$"

print(_cancel_regex())
print("No syntax error")
