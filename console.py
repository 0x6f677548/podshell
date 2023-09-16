from orchestration import Orchestrator
from events import Event


class App:
    """Represents a console App"""
    def __init__(self) -> None:
        """Creates a new instance of the App class."""
        self._orchestrator = Orchestrator(self._handle_orchestrator_event)

    def _handle_orchestrator_event(self, event: Event):
        # write events to the console using colors:
        #  - green for healthy events
        #  - yellow for warning events
        #  - normal color for other events
        event_text = f"{event.event_type}: {event.source_name} - {event.message}"
        if event.event_type == "HEALTHY":
            print(f"\033[92m{event_text}\033[0m")
        elif event.event_type == "WARNING":
            print(f"\033[93m{event_text}\033[0m")
        else:
            print(f"{event_text}")

    def run(self):
        """Runs the application."""
        print("Press Enter to exit...")
        self._orchestrator.start()
        input()
        self._orchestrator.stop()


if __name__ == "__main__":
    App().run()
