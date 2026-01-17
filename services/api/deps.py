from app.sgr import SGRController

_controller: SGRController | None = None

def get_controller() -> SGRController:
    global _controller
    if _controller is None:
        _controller = SGRController()
    return _controller
