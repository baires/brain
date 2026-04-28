import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from brain.routines.models import (
    RoutineAction,
    RoutineContext,
    RoutineResult,
    append_query_results,
)
from brain.routines.registry import register_builtin


@register_builtin
class EmailAction(RoutineAction):
    name = "email"

    def run(self, context: RoutineContext, params: dict) -> RoutineResult:
        to = params.get("to")
        if not to:
            return RoutineResult(success=False, message="Missing 'to' parameter")

        subject = params.get("subject", f"Brain routine: {context.routine_name}")
        body = params.get("body", f"Routine '{context.routine_name}' was triggered.")

        body, error = append_query_results(context, params, body)
        if error:
            return error

        smtp_host = params.get("smtp_host", "localhost")
        smtp_port = params.get("smtp_port", 25)
        smtp_user = params.get("smtp_user")
        smtp_password = params.get("smtp_password")
        from_addr = params.get("from", smtp_user or "brain@localhost")

        msg = MIMEMultipart()
        msg["From"] = from_addr
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                if params.get("smtp_tls", False):
                    server.starttls()
                if smtp_user and smtp_password:
                    server.login(smtp_user, smtp_password)
                server.send_message(msg)
            return RoutineResult(success=True, message=f"Email sent to {to}")
        except Exception as exc:
            return RoutineResult(success=False, message=str(exc))
