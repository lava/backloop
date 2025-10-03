import socket
from typing import Tuple


def get_random_port() -> Tuple[socket.socket, int]:
    """Get a random available port and return the socket and port number.

    Returns the socket to avoid timing issues where the port might be taken
    between checking and using it. The caller should close the socket when done.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("", 0))
    sock.listen(1)
    port = sock.getsockname()[1]
    return sock, port
