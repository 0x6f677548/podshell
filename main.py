import logging
import os
from terminal import windowsterminal
from pod.docker import DockerConnector
from pod.ssh import SSHConnector
from pod.connection import ConnectorEvent, ConnectorEventTypes

logger = logging.getLogger(__name__)


def handle_event(connector_event: ConnectorEvent):
    print(connector_event.event_type, connector_event.event)

    logger.info(
        f"Event: {connector_event.event_type}, {connector_event.event}, {connector_event.terminal_profile}"
    )

    if (
        connector_event.event_type == ConnectorEventTypes.STARTING
        or connector_event.event_type == ConnectorEventTypes.STOPPING
        or connector_event.event_type == ConnectorEventTypes.WARNING
    ):
        # remove profiles from the configuration
        terminal_configuration.remove_group(connector_event.connector_friendly_name)
    elif connector_event.event_type == ConnectorEventTypes.ADD_PROFILE:
        # add profile to the configuration
        terminal_configuration.add_profile(
            connector_event.terminal_profile, connector_event.connector_friendly_name
        )
    elif connector_event.event_type == ConnectorEventTypes.REMOVE_PROFILE:
        # remove profile from the configuration
        terminal_configuration.remove_profile(connector_event.terminal_profile.name)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    terminal_configuration = windowsterminal.Configuration()
    
    docker_connector = DockerConnector(
        connector_event_handler=handle_event,
        shell_command="/bin/bash",
    )
    docker_connector.start()

    ssh_connector = SSHConnector(
        connector_event_handler=handle_event,
        ssh_config_file=os.path.expanduser(os.path.join("~", ".ssh", "config"))
    )

    ssh_connector.start()
    input("Press Enter to continue...")
    docker_connector.stop()
    ssh_connector.stop()
