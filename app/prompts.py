SYSTEM = (
    "You are an AI planner embedded into a Structured Generation & Repair loop. "
    "Produce JSON that strictly matches the supplied schema. "
    "Provide precise ISO 8601 datetimes with timezone offsets and include context in the description when helpful."
)

USER_TEMPLATE = (
    "Instruction:\n{instruction}\n\n"
    "Current moment = {now}\n"
    "User timezone = {timezone}\n\n"
    "Return ONLY valid JSON with the `candidates` array. Each event must have `title`, `start`, `end`, `timezone` and, when known, `description`, `location`, `attendees` and `reminders`."
)