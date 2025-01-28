import socket
import multiprocessing

class ConnectionPool:
    """
    Manages persistent TCP connections to other nodes storing them in a dictionary.

    Each node connects to (localhost, 5000 + to_id).
    """

    def __init__(self, my_id, total_nodes):
        """
        Initialize the ConnectionPool.

        Args:
            my_id (int): The ID of the current node.
            total_nodes (int): Total number of nodes in the system.
        """
        self.my_id = my_id
        self.total_nodes = total_nodes
        self.connections = {}
        self.lock = multiprocessing.Lock()

    def get_connection(self, to_id):
        """
        Retrieve or establish a TCP connection to the specified node.

        Args:
            to_id (int): The ID of the target node to connect to.

        Returns:
            socket.socket: A socket connection to the target node.

        Steps:
        1. Acquire the lock to ensure thread-safe access to the connections.
        2. Check if a connection to the target node already exists.
           - If yes, return the existing connection.
           - If no, create a new socket and connect to (localhost, 5000 + to_id).
        3. Store the new connection in the connections dictionary.
        4. Return the connection.
        """
        with self.lock:
            if to_id not in self.connections:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                target_port = 5000 + to_id
                print(f"[ConnPool] Node {self.my_id} connecting to Node {to_id} on port {target_port}")
                s.connect(("localhost", target_port))
                self.connections[to_id] = s
            return self.connections[to_id]

    def send_message(self, to_id, message: str):
        """
        Send a message to using the connection to the target node.

        Args:
            to_id (int): The ID of the target node.
            message (str): The message to send.

        Steps:
        1. Retrieve the connection to the target node using `get_connection`.
        2. Send the message using the connection.
        3. Handle `ConnectionResetError` and log an error if the target node is unavailable.
        """
        conn = self.get_connection(to_id)
        try:
            conn.sendall(message.encode('utf-8'))
        except ConnectionResetError as e:
            print(f"[ConnPool] Node {self.my_id} -> Node {to_id}: ConnectionResetError {e}. Probably that node stopped.")

    def close_all(self):
        """
        Close all open connections.

        Steps:
        1. Acquire the lock to ensure thread-safe access to the connections.
        2. Iterate through all stored connections:
           - Attempt to close each connection.
           - Ignore any exceptions during closure.
        3. Clear the connections dictionary.
        """
        with self.lock:
            for s in self.connections.values():
                try:
                    s.close()
                except Exception as e:
                    print(f"[ConnPool] Error closing connection: {e}")
            self.connections.clear()
