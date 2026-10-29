"""
Base view abstract class defining standard life-cycle for functional views.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import gradio as gr


class BaseView(ABC):
    """
    Abstract base view for all functional modules in AI WebUI.
    Guarantees consistent layout construction, event registration, and state restoration.
    """

    def __init__(self, name: str, icon: str = "", title: str = ""):
        self.name = name
        self.icon = icon
        self.title = title
        self.container: Optional[gr.Column] = None
        self.components: Dict[str, Any] = {}

    @abstractmethod
    def render(self, session_ctx: Any) -> gr.Column:
        """Constructs and returns the Gradio UI layout container for this view."""
        pass

    @abstractmethod
    def register_events(self, session_ctx: Any) -> None:
        """Binds internal event listeners and handlers for this view."""
        pass

    def get_restore_components(self) -> List[Any]:
        """Returns the list of Gradio components that participate in state restoration."""
        return []

    def restore_state(self, task: Optional[Any], device_id: str) -> List[Any]:
        """Returns the list of updates for components when session restores."""
        return [gr.update()] * len(self.get_restore_components())

    def poll_progress(self, task: Optional[Any], device_id: str) -> List[Any]:
        """Returns progress updates when active background task is polled."""
        return [gr.update()] * len(self.get_restore_components())
