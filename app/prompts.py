SYSTEM = (
    "You are a scheduling assistant using strict JSON output that must validate "
    "against a provided Pydantic schema. Use the timezone unless specified."
)

USER_TEMPLATE = (
    "Instruction:\n{instruction}\n\n"
    "Now = {now}\nTimezone = {timezone}\n"
    "Return ONLY valid JSON for a list of events."
)