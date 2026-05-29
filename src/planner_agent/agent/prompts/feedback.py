"""Feedback parsing prompt (used by Haiku)."""

FEEDBACK_PARSE_PROMPT = """\
Parse this email reply into structured task feedback. The email is a reply to a daily \
planner briefing that assigned specific numbered tasks.

Extract for each mentioned task:
- task_id: the task number from the briefing (1, 2, 3, etc.)
- status: "done", "skipped", "in_progress", or "deferred"
- actual_hours: hours spent (if mentioned), as a decimal number
- notes: any context about why it was done/skipped
- learnings: any insights, patterns, or knowledge gained

Also extract:
- general_notes: any overall comments not tied to a specific task
- total_hours_reported: total hours the user reports working (if mentioned), as a decimal number. \
Convert minutes to decimals: "10 hrs 20 mins" = 10.33, "2 hours 30 minutes" = 2.5, "90 mins" = 1.5

IMPORTANT: Always look for time/hours/duration mentions. Common formats:
- "Spent 4 hours" → 4.0
- "10 Hrs and 20 Mins" → 10.33
- "took me about 3h" → 3.0
- "2.5 hours on task 1" → actual_hours: 2.5 for task 1
- "6 hours total" → total_hours_reported: 6.0

The user writes in natural language. Examples:
"Done 1 and 2. Skipped 3." → tasks 1,2 done; task 3 skipped
"Finished everything except the blog post" → all tasks done except the writing task
"Spent 4 hours total, got through the first two labs" → tasks 1,2 done; total_hours_reported: 4.0
"All tasks done. 10 Hrs and 20 Mins to finish" → all tasks done; total_hours_reported: 10.33

Return a JSON object:
{
  "task_updates": [
    {"task_id": 1, "status": "done", "actual_hours": null, "notes": "", "learnings": ""},
    {"task_id": 2, "status": "done", "actual_hours": null, "notes": "", "learnings": ""},
    {"task_id": 3, "status": "skipped", "actual_hours": null, "notes": "reason", "learnings": ""}
  ],
  "general_notes": "",
  "total_hours_reported": 10.33
}
"""
