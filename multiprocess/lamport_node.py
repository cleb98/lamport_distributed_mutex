import socket
import time
import random
import threading
from queue import PriorityQueue

from connection_pool import ConnectionPool

class LamportNode:
    """
    Implements Lamport’s Mutual Exclusion with single-request concurrency
    and a 'SHUTDOWN' message for coordinated shutdown.
    """

    def __init__(
            self, 
            my_id,
            total_nodes, 
            port,
            cs_history,
            message_count, 
            shared_counter,
            visualization_data
        ):
        
        """
        Initialize the LamportNode.

        Args:
            my_id (int): The ID of the current node.
            total_nodes (int): Total number of nodes in the system.
            port (int): Port number for the node's server.
            cs_history (manager.list): Shared list to store critical section history.
            message_count (manager.Dict): Shared dictionary to store message counts for each process.
            shared_counter (manager.Value): Shared counter to track the number of messages sent.
        """
        self.my_id = my_id
        self.total_nodes = total_nodes
        self.port = port
        self.cs_history = cs_history
        self.message_count = message_count
        self.shared_counter = shared_counter
        self.visualiztion_data = visualization_data

        self.lamport_clock = 0 #to ensure that no node starts with the same clock value (even if eventually the priority queue can manage this)
        self.request_queue = PriorityQueue()
        self.replies_received = 0

        self.running = True
        self.in_critical_section = False

        self.local_lock = threading.Lock()
        self.connection_pool = ConnectionPool(my_id, total_nodes)

        # set of nodes from which we've received SHUTDOWN
        self.shutdown_set = set()

    def log(self, msg: str):
        """
        Logs a message with the node ID and current Lamport clock. ( [Node {id} | Clock {clock}] {msg} )

        Args:
            msg (str): Message to log.
        """
        print(f"[Node {self.my_id} | Clock {self.lamport_clock}] {msg}")

    def increment_clock(self):
        """
        Increment the Lamport clock.
        """
        with self.local_lock:
            self.lamport_clock += 1

    def update_clock(self, other_clock):
        """
        Update the Lamport clock to be the maximum of the current clock
        and the received clock, plus one.

        Args:
            other_clock (int): The received Lamport clock value.
        """
        with self.local_lock:
            self.lamport_clock = max(self.lamport_clock, other_clock) + 1

    def request_cs(self):
        """
        Request access to the critical section.

        Steps:
        1. Increment the Lamport clock.
        2. Add the current request to the queue.
        3. Broadcast a REQUEST message to all other nodes.
        4. Wait for REPLY messages from all other nodes.
        5. Ensure the node's request is at the head of the queue.
        6. Enter the critical section.
        """
        self.increment_clock()
        current_req = (self.lamport_clock, self.my_id) #store the (clock, id) tuple, to track if the first request in the queue is the current node's request
        self.request_queue.put(current_req)

        self.replies_received = 0
        req_msg = f"REQUEST {self.lamport_clock} {self.my_id}\n"
        # self.increment_clock()
        self.broadcast_message(req_msg)
        self.log(f"Sent REQUEST ({current_req})). Waiting for REPLY...")

        while True:
            time.sleep(0.05)
            with self.local_lock:
                if self.replies_received >= (self.total_nodes - 1):
                    break
                self.log(f"REPLY count: {self.replies_received}/{self.total_nodes - 1}")
                self.log(f"Queue: {list(self.request_queue.queue)}")

        self.log("All REPLY received. Checking if my request is at the head...")
        while True:
            head_req = self.request_queue.queue[0]
            if head_req == current_req:
                break
            time.sleep(0.05)

        self.in_critical_section = True
        self.log(">>> ENTER CRITICAL SECTION <<<")
        start_time = time.time()
        #wait a random time to simulate the critical section execution
        time.sleep(random.uniform(0.5, 1.0))

        #incremeant global shared counter
        with self.local_lock:
            self.shared_counter.value += 1

        end_time = time.time()
        self.visualiztion_data.append((self.my_id, start_time, end_time))
        #the process in the critical section should record its entry and increment the shared counter 
        self.cs_history.append((self.my_id, self.lamport_clock))

    def release_cs(self):
        """
        Release access to the critical section.

        Steps:
        1. Check if the node is currently in the critical section.
           - If not, log a warning and return.
        2. Set the `in_critical_section` flag to False.
        3. Log the exit from the critical section.
        4. Remove the node's request from the queue.
           - Ensure the top item in the queue matches the node's request.
           - If not, log an error and return.
        5. Increment the Lamport clock.
        6. Broadcast a RELEASE message to all other nodes.
        """
        if not self.in_critical_section:
            self.log("release_cs() called but not in CS!")
            return

        self.in_critical_section = False
        self.log("<<< EXIT CRITICAL SECTION >>>")

        # single-get approach
        if not self.request_queue.empty():
            head_req = self.request_queue.get()
            if head_req[1] != self.my_id:
                self.log(f"ERROR: top item {head_req} != me {self.my_id}")
                self.request_queue.put(head_req)

        self.increment_clock()
        rel_msg = f"RELEASE {self.lamport_clock} {self.my_id}\n"
        self.broadcast_message(rel_msg)

    def broadcast_shutdown(self):
        """
        Broadcast a SHUTDOWN message to all peers.

        Steps:
        1. Increment the Lamport clock.
        2. Create a SHUTDOWN message.
        3. Broadcast the SHUTDOWN message to all peers.
        4. Log the shutdown broadcast.
        """
        self.increment_clock()
        shut_msg = f"SHUTDOWN {self.lamport_clock} {self.my_id}\n"
        # Broadcast SHUTDOWN to all peers
        for pid in range(self.total_nodes):
            if pid != self.my_id:
                self.connection_pool.send_message(pid, shut_msg)
                # self.send_message(pid, shut_msg) #cosi conta gli shut_msg come messaggi inviati per gli esperimenti, non lo voglio
        self.log("Broadcasted SHUTDOWN to all peers.")

    def broadcast_message(self, message: str):
        """
        Broadcast a message to all other nodes.

        Args:
            message (str): The message to broadcast.

        Steps:
        1. Iterate over all nodes except the current node.
        2. Send the message to each node using the connection pool service.
        """
        for pid in range(self.total_nodes):
            if pid != self.my_id:
                # self.connection_pool.send_message(pid, message)
                self.send_message(pid, message)

    def send_message(self, to_id: int, message: str):
        """
        Send a message to the specified node.
        1. Increment the message count for the sender.
        2. Send the message using the connection pool service.

        Args:
            to_id (int): The ID of the target node.
            message (str): The message to send.
        """
        #count the message sent (just for the experiment section)
        with self.local_lock:
            # if message != "SHUTDOWN": # now shotdown is not added to self.message_count,
            # because self.broadcast_shutdown() is not using this method
            old_count = self.message_count.get(self.my_id, 0)
            self.message_count[self.my_id] = old_count + 1

        #send the message via the connection pool
        self.connection_pool.send_message(to_id, message)

    def run_server(self):
        """
        Start the server to listen for incoming messages.

        Steps:
        1. Create a server socket and bind to the specified port.
        2. Set the socket to listen for connections.
        3. Accept incoming connections and spawn a thread to handle each client.
        4. Handle exceptions and log errors.
        5. Shut down the server when `running` is set to False.
        """
        self.log(f"Starting server on port {self.port}")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(("localhost", self.port))
            server_socket.listen(self.total_nodes - 1)

            while self.running:
                try:
                    server_socket.settimeout(1.0)
                    conn, addr = server_socket.accept()
                    t = threading.Thread(target=self.handle_client, args=(conn,), daemon=True)
                    t.start()
                except socket.timeout:
                    pass
                except Exception as e:
                    self.log(f"run_server exception: {e}")
                    break
        self.log("Server shutting down...")

    def handle_client(self, conn: socket.socket):
        """
        Handle communication with a connected client.

        Args:
            conn (socket.socket): The socket connection to the client.

        Steps:
        1. Read data from the client socket.
        2. Buffer the data until a full message is received.
        3. Handle each complete message.
        4. Close the connection on errors or when the client disconnects.
        """
        buffer = ""
        while self.running:
            try:
                data = conn.recv(1024)
                if not data:
                    break
                buffer += data.decode('utf-8')
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if line:
                        self.handle_message(line)
            except Exception as e:
                self.log(f"handle_client error: {e}")
                break
        conn.close()

    def handle_message(self, line: str):
        """
        Process a received message.

        Args:
            line (str): The received message.

        Steps:
        1. Parse the message and extract its type, clock, and sender.
        2. Update the Lamport clock based on the received clock.
        3. Handle the message based on its type (REQUEST, REPLY, RELEASE, SHUTDOWN).
           - For REQUEST: Add the sender's request to the queue and send a REPLY.
           - For REPLY: Increment the count of replies received.
           - For RELEASE: Remove the sender's request from the queue.
           - For SHUTDOWN: Add the sender to the shutdown set and stop if all peers are done.
        4. Log errors for unknown message types.
        """
        parts = line.split()
        if len(parts) < 3:
            self.log(f"Malformed message: {line}")
            return

        msg_type = parts[0]
        msg_clock = int(parts[1])
        msg_sender = int(parts[2])

        self.update_clock(msg_clock)
        self.log(f"Received {msg_type} from {msg_sender} (clock={msg_clock}).")

        if msg_type == "REQUEST":
            self.request_queue.put((msg_clock, msg_sender))
            self.log(f"Inserted request from {msg_sender}. Queue: {list(self.request_queue.queue)}")
            # auto-REPLY
            self.increment_clock()
            self.send_message(msg_sender, f"REPLY {self.lamport_clock} {self.my_id}\n")

        elif msg_type == "REPLY":
            with self.local_lock:
                self.replies_received += 1
            self.log(f"REPLY count: {self.replies_received}/{self.total_nodes - 1}")

        elif msg_type == "RELEASE":
            if not self.request_queue.empty():
                head_req = self.request_queue.get()
                if head_req[1] != msg_sender:
                    self.log(f"ERROR: top item {head_req} != {msg_sender} releasing.")
                    #rimetti l'elemento in cima alla coda
                    self.request_queue.put(head_req) 
                else:
                    self.log(f"Removed top item {head_req} after RELEASE from {msg_sender}")
                    self.log(f"Updated Queue: {list(self.request_queue.queue)}")
            else:
                self.log("ERROR: queue empty but got RELEASE?")

        elif msg_type == "SHUTDOWN":
            # Node `msg_sender` is done
            self.log(f"Node {msg_sender} is shutting down.")
            with self.local_lock:
                self.shutdown_set.add(msg_sender)

            # If we've now received SHUTDOWN from all other nodes, we can stop.
            if len(self.shutdown_set) == self.total_nodes - 1:
                self.log("Received SHUTDOWN from all peers. Stopping now.")
                self.stop()

        else:
            self.log(f"Unknown message type: {msg_type}")

    def stop(self):
        """
        Stop the node's server and close all connections.
        """
        self.running = False
        self.connection_pool.close_all()
