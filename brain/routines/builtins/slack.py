import json

import requests

from brain.routines.models import (
    RoutineAction,
    RoutineContext,
    RoutineResult,
    append_query_results,
)
from brain.routines.registry import register_builtin


@register_builtin
class SlackAction(RoutineAction):
    name = "slack"

    def run(self, context: RoutineContext, params: dict) -> RoutineResult:
        webhook_url = params.get("webhook_url")
        if not webhook_url:
            return RoutineResult(success=False, message="Missing 'webhook_url' parameter")

        message = params.get("message", f"Routine *{context.routine_name}* triggered.")

        message, error = append_query_results(context, params, message)
        if error:
            return error

        payload = {"text": message}

        try:
            response = requests.post(
                webhook_url,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            response.raise_for_status()
            return RoutineResult(
                success=True, message=f"Slack notification sent: {response.status_code}"
            )
        except requests.RequestException as exc:
            return RoutineResult(success=False, message=str(exc))
