"""Node class for Jaseci."""
from jaclang.core.object import object


class Node(object):
    """Node class for Jaseci."""

    def __init__(self, *args: list, **kwargs: dict) -> None:
        """Initialize node."""
        super().__init__(*args, **kwargs)
