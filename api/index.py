"""Vercel serverless entrypoint.

Vercel's @vercel/python builder imports this module and looks for a module
level `handler` (or `app`) callable. `backend.app.app.handler` is the
Mangum-wrapped ASGI application, which accepts the Lambda-style event that
Vercel passes in.
"""

from backend.app.app import handler  # noqa: F401
