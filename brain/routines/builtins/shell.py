import os
import subprocess

from brain.routines.models import RoutineAction, RoutineContext, RoutineResult
from brain.routines.registry import register_builtin


@register_builtin
class ShellAction(RoutineAction):
    name = "shell"

    def run(self, context: RoutineContext, params: dict) -> RoutineResult:
        command = params.get("command")
        if not command:
            return RoutineResult(success=False, message="Missing 'command' parameter")

        env = os.environ.copy()
        env["BRAIN_ROUTINE_NAME"] = context.routine_name
        env["BRAIN_TRIGGER_TYPE"] = context.trigger.type
        env["BRAIN_TRIGGER_VALUE"] = context.trigger.value or ""
        for key, value in params.get("env", {}).items():
            env[key] = str(value)

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=params.get("timeout", 60),
                env=env,
            )
            if result.returncode == 0:
                return RoutineResult(
                    success=True,
                    message=result.stdout.strip(),
                    data={"stdout": result.stdout, "stderr": result.stderr},
                )
            return RoutineResult(
                success=False,
                message=f"Exit code {result.returncode}: {result.stderr.strip()}",
                data={"stdout": result.stdout, "stderr": result.stderr},
            )
        except subprocess.TimeoutExpired:
            return RoutineResult(
                success=False, message=f"Command timed out after {params.get('timeout', 60)}s"
            )
        except Exception as exc:
            return RoutineResult(success=False, message=str(exc))
