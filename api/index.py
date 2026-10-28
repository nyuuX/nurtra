"""Vercel serverless entrypoint.

Vercel's @vercel/python builder looks for a top-level `app`, `application`,
or `handler` binding in this file, so the ASGI app is wrapped here directly
instead of re-exported from another module.
"""

from mangum import Mangum

from backend.app.app import app

handler = Mangum(app, lifespan="off")
