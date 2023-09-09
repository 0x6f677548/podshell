from terminal import windowsterminal
from pod.docker import DockerConnector

import logging


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    connector = DockerConnector(
        configuration=windowsterminal.Configuration(),
        f_handle_event=lambda connector_event: print(
            connector_event.event_type, connector_event.event
        ),
        shell_command="/bin/bash"
    )
    connector.start()

    input("Press Enter to continue...")
    connector.stop()
