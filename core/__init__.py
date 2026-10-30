"""
Core architectural abstractions and supervisors.

IMPORTANT: this __init__ must stay import-light (no submodule re-exports).
`task_manager` imports `core.comfy_client`; eagerly importing `core.admin_manager`
here would import `task_manager` back mid-initialization and deadlock the package.
Consumers import submodules directly, e.g. `from core.admin_manager import AdminManager`.
"""
