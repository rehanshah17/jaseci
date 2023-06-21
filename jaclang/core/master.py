"""Master class for Jaseci."""
from jaclang.core.element import Element


class Master(Element):
    """Master class for Jaseci."""

    def __init__(self, *args: list, **kwargs: dict) -> None:
        """Initialize master."""
        super().__init__(*args, **kwargs)
