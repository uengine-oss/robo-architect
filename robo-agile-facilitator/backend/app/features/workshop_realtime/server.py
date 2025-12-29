"""Socket.IO server for the realtime workshop capability.

Important: importing this module must register all event handlers.
"""

import socketio

# Create Socket.IO server
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")

# Register handlers (side-effect import)
from . import canvas_handlers as _canvas_handlers  # noqa: F401
from . import video_signaling as _video_signaling  # noqa: F401


