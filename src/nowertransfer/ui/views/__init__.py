"""One module per screen."""

from .home import HomeView
from .receive import ReceiveView
from .send import SendView
from .settings import SettingsView

__all__ = ["HomeView", "ReceiveView", "SendView", "SettingsView"]
