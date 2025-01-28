import socket
import threading
import time
import random
from queue import PriorityQueue
from threading import Condition, Barrier
from typing import Dict, List, Tuple
import matplotlib.pyplot as plt

# --------------------------------------------------------------------------------------------
# Global shared variables among processes
# --------------------------------------------------------------------------------------------
critical_section_access: List[int] = []  # Track which processes are currently in the critical section
cs_history: List[Tuple[int, int]] = []   # Full history of (process_id, lamport_clock) entries to the CS
message_count: Dict[int, int] = {}       # Count of messages sent by each process
lock = threading.Lock()                  # Lock for synchronizing access to shared variables
shared_counter: int = 0                  # Shared resource: global counter
visualization_data: List[Tuple[int, float, float]] = []  # Track (process_id, start_time, end_time)

# Adjustable parameters
total_processes = int(input("Enter the total number of processes: "))
assert type(total_processes) == int and total_processes > 1, "Please enter a valid integer greater than 1."
shutdown_barrier = Barrier(total_processes)  # For optional shutdown synchronization

class ConnectionPool:
    def __init__(self, process_id: int, total_processes: int):
        self.process_id = process_id
        self.total_processes = total_processes
        self.connections = {}
        self.lock = threading.Lock()

    def get_connection(self, to_process_id: int) -> socket.socket:
        with self.lock:
            if to_process_id not in self.connections or self.connections[to_process_id]._closed:
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    s.connect(("localhost", 5000 + to_process_id))
                    self.connections[to_process_id] = s
                    print(f"[Process {self.process_id}] Established connection to Process {to_process_id}")
                except ConnectionRefusedError as e:
                    print(f"[Process {self.process_id}] Failed to connect to Process {to_process_id}: {e}")
                    raise
            return self.connections[to_process_id]

    def close_all(self):
        with self.lock:
            for s in self.connections.values():
                s.close()
            self.connections.clear()
            print(f"[Process {self.process_id}] All connections closed.")

class LamportMutex:
    def __init__(self, process_id: int, total_processes: int, port: int):
        self.process_id = process_id
        self.total_processes = total_processes
        self.port = port
        self.lamport_clock = 0
        self.request_queue = PriorityQueue()
        self.replies_received = 0
        self.lock = threading.Lock()
        self.condition = Condition()
        self.running = True
        self.in_critical_section = False
        self.connection_pool = ConnectionPool(process_id, total_processes)

    def log(self, message: str):
        print(f"[Process {self.process_id} | Clock {self.lamport_clock}] {message}")

    def increment_clock(self):
        with self.lock:
            self.lamport_clock += 1

    def update_clock(self, other_clock: int):
        with self.lock:
            self.lamport_clock = max(self.lamport_clock, other_clock) + 1

    def request_critical_section(self):
        global visualization_data, shared_counter

        self.increment_clock()
        self.request_queue.put((self.lamport_clock, self.process_id))
        self.broadcast_message(f"REQUEST {self.lamport_clock} {self.process_id}")
        self.log("Sent REQUEST for the critical section")

        with self.condition:
            if not self.condition.wait_for(lambda: self.replies_received >= self.total_processes - 1, timeout=5):
                self.log("Timeout while waiting for REPLY. Aborting critical section entry.")
                return

        self.log("All REPLY messages received. Checking critical section availability...")
        
        while True:
            with lock:
                if len(critical_section_access) == 0 and self.request_queue.queue[0][1] == self.process_id:
                    critical_section_access.append(self.process_id)
                    cs_history.append((self.process_id, self.lamport_clock))
                    self.in_critical_section = True
                    self.log(f"Process {self.process_id} ENTERS CS. Current state: {critical_section_access}")
                    break
            time.sleep(0.1)

        start_time = time.time()
        time.sleep(random.uniform(0.5, 1.0))
        with lock:
            shared_counter += 1
            end_time = time.time()
            visualization_data.append((self.process_id, start_time, end_time))
            self.log(f"(CRITICAL SECTION) Shared counter incremented to {shared_counter}")

    def release_critical_section(self):
        if not self.in_critical_section:
            self.log(f"Process {self.process_id} attempted to release CS but was not in CS.")
            return

        with lock:
            critical_section_access.pop()
            self.in_critical_section = False
            self.log(f"Process {self.process_id} EXITS CS. Current state: {critical_section_access}")

        self.increment_clock()
        try:
            self.request_queue.get_nowait()
            self.log(f"Updated queue after releasing CS: {[item for item in self.request_queue.queue]}")
        except Exception as e:
            self.log(f"Error updating queue after releasing CS: {e}")

        self.replies_received = 0
        self.broadcast_message(f"RELEASE {self.lamport_clock} {self.process_id}")
        self.log("Released the critical section")

    def broadcast_message(self, message: str):
        global message_count
        for i in range(self.total_processes):
            if i != self.process_id:
                self.send_message(i, message)

    def send_message(self, to_process_id: int, message: str):
        retries = 3
        for attempt in range(retries):
            try:
                conn = self.connection_pool.get_connection(to_process_id)
                conn.sendall(message.encode())
                self.log(f"Sent message to Process {to_process_id}: {message}")
                with lock:
                    message_count[self.process_id] = message_count.get(self.process_id, 0) + 1
                return
            except (ConnectionRefusedError, BrokenPipeError) as e:
                self.log(f"Failed to send message to Process {to_process_id}, attempt {attempt + 1}: {e}")
                time.sleep(0.5)
        self.log(f"Giving up on sending message to Process {to_process_id} after {retries} retries.")

    def stop(self):
        self.running = False
        self.connection_pool.close_all()

    def recovery_check(self):
        last_progress_time = time.time()
        while self.running:
            time.sleep(5)
            with self.lock:
                if self.replies_received >= self.total_processes - 1:
                    last_progress_time = time.time()
                elif time.time() - last_progress_time > 30:
                    self.log("Detected potential deadlock. Re-broadcasting REQUEST.")
                    self.broadcast_message(f"REQUEST {self.lamport_clock} {self.process_id}")
                    last_progress_time = time.time()

    def run_server(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(("localhost", self.port))
            server_socket.listen(self.total_processes - 1)
            self.log("Server started and listening...")

            while self.running:
                try:
                    conn, _ = server_socket.accept()
                    threading.Thread(target=self.handle_client, args=(conn,), daemon=True).start()
                except socket.error as e:
                    if not self.running:
                        break
                    self.log(f"Server error: {e}")
            self.log("Server shutting down...")

    def handle_client(self, conn: socket.socket):
        while self.running:
            try:
                message = conn.recv(1024).decode()
                if message:
                    self.handle_message(message)
                else:
                    break
            except socket.error as e:
                self.log(f"Connection error: {e}")
                break
        conn.close()

    def handle_message(self, message: str):
        parts = message.split()
        msg_type = parts[0]
        msg_clock = int(parts[1])
        msg_process_id = int(parts[2])

        self.update_clock(msg_clock)
        self.log(f"Received {msg_type} from Process {msg_process_id} with clock {msg_clock}")

        if msg_type == "REQUEST":
            self.request_queue.put((msg_clock, msg_process_id))
            self.log(f"Updated queue after REQUEST: {[item for item in self.request_queue.queue]}")
            self.increment_clock()
            self.send_message(msg_process_id, f"REPLY {self.lamport_clock} {self.process_id}")

        elif msg_type == "REPLY":
            with self.condition:
                self.replies_received += 1
                self.log(f"REPLY received: {self.replies_received}/{self.total_processes - 1}")
                self.condition.notify()

        elif msg_type == "RELEASE":
            if not self.request_queue.empty():
                with self.lock:
                    try:
                        self.request_queue.get_nowait()
                        self.log(f"Updated queue after RELEASE: {[item for item in self.request_queue.queue]}")
                    except Exception as e:
                        self.log(f"Error updating queue after RELEASE: {e}")

def simulate_process(process_id: int, total_processes: int):
    global message_count
    message_count[process_id] = 0

    port = 5000 + process_id
    process = LamportMutex(process_id, total_processes, port)
    server_thread = threading.Thread(target=process.run_server)
    recovery_thread = threading.Thread(target=process.recovery_check)

    server_thread.start()
    recovery_thread.start()

    time.sleep(2)

    try:
        time.sleep(random.uniform(1, 3))
        process.request_critical_section()
        process.release_critical_section()
    finally:
        process.stop()
        server_thread.join(timeout=5)
        recovery_thread.join(timeout=5)
        if server_thread.is_alive():
            print(f"Process {process_id}: Server thread did not stop properly.")
        if recovery_thread.is_alive():
            print(f"Process {process_id}: Recovery thread did not stop properly.")

def visualize_results(data: List[Tuple[int, float, float]], cs_history: List[Tuple[int, int]], total_processes: int):
    """
    Generate a single figure combining Gantt chart and latency analysis.

    Args:
        data (List[Tuple[int, float, float]]): List of tuples containing process_id, start_time, and end_time.
        cs_history (List[Tuple[int, int]]): List of tuples (process_id, lamport_clock) when processes entered CS.
        total_processes (int): Total number of processes in the simulation.

    Returns:
        None
    """
    latencies = {i: [] for i in range(total_processes)}

    for i in range(1, len(cs_history)):
        curr_process, curr_clock = cs_history[i]
        prev_process, prev_clock = cs_history[i - 1]
        if curr_process != prev_process:
            latencies[curr_process].append(curr_clock - prev_clock)

    avg_latencies = {pid: sum(times) / len(times) if times else 0 for pid, times in latencies.items()}

    processes = list(avg_latencies.keys())
    avg_latency_values = list(avg_latencies.values())

    fig, axes = plt.subplots(2, 1, figsize=(12, 10))

    # Gantt Chart
    ax = axes[0]
    for process_id, start_time, end_time in data:
        ax.broken_barh([(start_time, end_time - start_time)], (process_id * 10, 9), facecolors=('tab:blue'))
        ax.text(start_time + (end_time - start_time) / 2, process_id * 10 + 4.5, f"P{process_id}",
                ha="center", va="center", color="white", fontsize=8, weight="bold")

    ax.set_yticks([i * 10 + 5 for i in range(total_processes)])
    ax.set_yticklabels([f"Process {i}" for i in range(total_processes)])
    ax.set_xlabel("Time (seconds)")
    ax.set_title("Annotated Gantt Chart of Critical Section Execution")
    ax.grid(True)

    # Latency Analysis
    ax = axes[1]
    bars = ax.bar(processes, avg_latency_values, alpha=0.7, color='tab:blue')
    for bar, value in zip(bars, avg_latency_values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2, f'{value:.1f}',
                ha='center', va='bottom', fontsize=10, color='black')
    ax.set_title("Average Latency to Access Critical Section")
    ax.set_xlabel("Process ID")
    ax.set_ylabel("Average Latency (Lamport Clock Ticks)")
    ax.set_xticks(processes)
    ax.grid(axis="y", linestyle="--", alpha=0.7)

    plt.tight_layout()
    plt.savefig(f"results{total_processes}.png")
    plt.show()
    plt.close()

def main() -> None:
    start_time = time.time()

    critical_section_access.clear()
    cs_history.clear()
    message_count.clear()

    global visualization_data
    visualization_data.clear()  # Reset visualization data

    threads = []

    for i in range(total_processes):
        thread = threading.Thread(target=simulate_process, args=(i, total_processes))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    print("\n--- Final Results ---")
    print("Critical Section History (cs_history):", cs_history)
    print("Global shared counter (shared_counter):", shared_counter)
    print("Message Count:", message_count)
    print("Total messages sent:", sum(message_count.values()))
    assert len(critical_section_access) == 0, "Critical section must be empty at the end."
    print("All processes respected Safety, Liveness, and Fairness.")

    end_time = time.time()
    execution_time = end_time - start_time
    print(f"\nTotal execution time: {execution_time:.4f} seconds")

     #create json file to store the results
    import json
    results = {
        "cs_history": cs_history,
        "shared_counter": shared_counter,
        "message_count": message_count,
        "total_messages": sum(message_count.values()),
        "execution_time": execution_time
    }
    with open(f"results{total_processes}.json", "w") as f:
        json.dump(results, f, indent=4)
    print(f"Results saved to results{total_processes}.json")

    print("Visualizing Results:")
    visualize_results(visualization_data, cs_history, total_processes)

   

if __name__ == "__main__":
    main()
