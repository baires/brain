from brain.routines.models import RoutineAction, RoutineContext, RoutineResult
from brain.routines.registry import register_builtin


@register_builtin
class EchoAction(RoutineAction):
    name = "echo"

    def run(self, context: RoutineContext, params: dict) -> RoutineResult:
        message = params.get(
            "message", f"Routine {context.routine_name} triggered via {context.trigger.type}"
        )
        return RoutineResult(success=True, message=message)
