"""
Web application assembly layer (Spec 2026-10-31 routing refactor, 方案A).

- shell.py   : shared page chrome (theme, head JS, sidebar/header/toolbar scaffold)
- pages_*.py : one Gradio Blocks per module page (/minimax, /upscaler, /strata)
- server.py  : FastAPI assembly — mounts, "/" last-page redirect, tab deep-link catch-all

`app.py` (project root) stays the stable entry point: it re-exports this
package's names so tests/e2e imports never changed during the refactor.
"""
