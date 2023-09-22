from enum import StrEnum


class EventType(StrEnum):
    """The type of the event."""

    ADD_PROFILE = "ADD_PROFILE"
    REMOVE_PROFILE = "REMOVE_PROFILE"
    WARNING = "WARNING"
    STARTING = "STARTING"
    STOPPING = "STOPPING"
    HEALTHY = "HEALTHY"


class Event:
    """Event that is sent to event handler."""

    def __init__(
        self,
        source_name: str,
        event_type: EventType,
        event_message: str,
        event_data=None,
    ):
        """Creates a new instance of the Event class."""
        self.event_type = event_type
        self.message = event_message
        self.source_name = source_name
        self.data = event_data
