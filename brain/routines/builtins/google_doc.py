from brain.routines.models import (
    RoutineAction,
    RoutineContext,
    RoutineResult,
    append_query_results,
)
from brain.routines.registry import register_builtin


@register_builtin
class GoogleDocAction(RoutineAction):
    name = "google_doc"

    def run(self, context: RoutineContext, params: dict) -> RoutineResult:
        doc_id = params.get("doc_id")
        if not doc_id:
            return RoutineResult(success=False, message="Missing 'doc_id' parameter")

        content = params.get("content", "")

        content, error = append_query_results(context, params, content, default_n_results=10)
        if error:
            return error

        if not content:
            content = f"Routine '{context.routine_name}' update."

        credentials_path = params.get("credentials_path")

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
        except ImportError:
            return RoutineResult(
                success=False,
                message="Google API client libraries are required. Install with: uv pip install google-auth google-auth-oauthlib google-api-python-client",
            )

        try:
            creds = None
            if credentials_path:
                creds = service_account.Credentials.from_service_account_file(
                    credentials_path,
                    scopes=["https://www.googleapis.com/auth/documents"],
                )
            if creds is None:
                return RoutineResult(
                    success=False,
                    message="Google Doc authentication failed. Provide 'credentials_path'.",
                )

            service = build("docs", "v1", credentials=creds)
            requests_body = [
                {
                    "insertText": {
                        "location": {"index": 1},
                        "text": content + "\n",
                    }
                }
            ]
            service.documents().batchUpdate(
                documentId=doc_id, body={"requests": requests_body}
            ).execute()
            return RoutineResult(success=True, message=f"Appended to Google Doc {doc_id}")
        except Exception as exc:
            return RoutineResult(success=False, message=str(exc))
