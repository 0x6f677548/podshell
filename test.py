from pod.docker import DockerConnector
import logging
from pod.connection import ConnectorEvent, ConnectorEventTypes


def handle_event(connector_event: ConnectorEvent):
    logging.info(
            f"({connector_event.event_type}) {connector_event.event}"
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    connector = DockerConnector(handle_event)
    connector.start()

    input("Press enter to stop the connector")
    connector.stop()

    input("Press enter to exit")
