"""Walker class for Jaseci."""
from jaclang.core.object import Object


class Walker(Object):
    """Walker class for Jaseci."""

    def __init__(self, *args: list, **kwargs: dict) -> None:
        """Initialize walker."""
        super().__init__(*args, **kwargs)
