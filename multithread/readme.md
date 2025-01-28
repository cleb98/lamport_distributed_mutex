# **Lamport Mutex Algorithm in a Distributed Environment**

This project implements the **Lamport Mutex** algorithm in a distributed environment using **TCP sockets** to simulate inter-process communication. It demonstrates how multiple processes can coordinate to enter a **Critical Section (CS)** without violating safety properties (e.g., mutual exclusion) and ensuring liveness (no deadlock or starvation).

---

## **Project Structure**

The project consists of a single Python script that integrates all functionality for simplicity.

 <!-- This non-modular implementation is ideal for quick prototyping and learning. -->

### **Key Components:**

1. **Global Shared Data**:

   - Variables like `critical_section_access`, `cs_history`, `shared_counter`, and `message_count` track the state of the system and shared resources.
   - These are managed with `threading.Lock` to ensure thread safety.

2. **`LamportMutex` Class**:

   - Implements Lamport's Mutual Exclusion algorithm.
   - Manages logical clocks, priority queues for requests, and communication via TCP sockets.
   - Handles the entire lifecycle of a process, including requests, replies, releases, and recovery checks.

3. **`ConnectionPool` Class**:

   - **Purpose**: Efficiently manages persistent TCP connections between processes.
   - **How It Works**:
     - Maintains a dictionary of open socket connections to other processes, indexed by process ID.
     - Reuses existing connections for all communication, reducing overhead from repeatedly opening and closing sockets.
     - If a connection is broken or closed, it automatically re-establishes the connection when needed.
   - **Benefits**:
     - Reduces communication latency by avoiding connection setup for every message.
     - Simplifies debugging by ensuring stable and consistent connections between processes.
     - Improves scalability for systems with frequent message exchanges.

4. **`simulate_process()` Function**:

   - Simulates an individual process using the `LamportMutex` class.
   - Spawns server and recovery threads to handle communication and deadlock recovery.
   - Requests and releases the critical section (CS).

5. **Main Function**:

   - Coordinates the simulation by initializing shared data, spawning processes (threads), and collecting results.

---

## **What Does the System Do?**

1. **Simulates a Distributed Environment**:

   - Each "process" is a Python thread that runs a `LamportMutex` instance.
   - Processes communicate via TCP sockets bound to unique ports (e.g., `5000 + process_id`).

2. **Implements Lamport’s Distributed Mutual Exclusion**:

   - Processes use `REQUEST`, `REPLY`, and `RELEASE` messages to coordinate access to the CS.
   - Logical clocks and a priority queue ensure FIFO ordering of requests.

3. **Handles Deadlocks and Timeouts**:

   - A recovery thread periodically checks for stalled progress and re-broadcasts `REQUEST` messages if necessary.

4. **Simulates Shared Resource Access**:

   - The `shared_counter` is incremented within the CS to demonstrate mutual exclusion in action.

---

## **Algorithm Details**

### **Core Principles:**

- **Logical Clocks**:

  - Each process maintains a Lamport logical clock, incremented on events and synchronized via message passing.

- **Message Exchange:**

  - Processes exchange `REQUEST`, `REPLY`, and `RELEASE` messages to coordinate CS access.

- **Critical Section Entry:**

  - A process enters the CS only if it:
    1. Is at the head of its local priority queue.
    2. Has received `REPLY` messages from all other processes.

- **Critical Section Exit:**

  - After completing its work, the process sends a `RELEASE` message to inform peers.

### **Overheads & Limitations:**

1. **Message Complexity**:

   - $3(N - 1)$ messages per CS entry (1 `REQUEST`, 1 `REPLY`, 1 `RELEASE` for each peer).

2. **Synchronization Delays**:

   - Processes must wait for replies from all peers, which can be delayed by network or processing.

3. **Connection Management**:

   - Persistent connections are used to reduce overhead from repeatedly opening/closing sockets.

4. **Deadlock Recovery**:

   - Recovery threads periodically rebroadcast `REQUEST` messages if progress stalls.

---

## **How the System Works**

1. **Initialization:**

   - Global data structures (`cs_history`, `message_count`, etc.) are initialized.
   - Threads representing processes are spawned.

2. **Process Lifecycle:**

   - Each process:
     1. Starts a server to listen for incoming messages.
     2. Begins a recovery thread to handle timeouts and deadlocks.
     3. Requests the CS, performs work, and releases the CS.

3. **Communication:**

   - Processes exchange messages over persistent TCP connections managed by the `ConnectionPool` class.
   - Each message (`REQUEST`, `REPLY`, `RELEASE`) follows Lamport’s protocol.

4. **Shutdown:**

   - Processes clean up resources by stopping their server and recovery threads.
   - Persistent connections are closed.

---

## **Advantages of Persistent Connections**

1. **Reduced Overhead:**

   - Connections are reused, avoiding repeated socket creation/destruction.

2. **Improved Performance:**

   - Faster message delivery due to maintained connections.

3. **Simplified Debugging:**

   - Easier to trace communication issues with long-lived connections.

---

## **Results & Observations**

- **Critical Section History (`cs_history`)**:

  - Logs which processes accessed the CS and their logical clock values.

- **Global Shared Counter (`shared_counter`)**:

  - Final value verifies mutual exclusion (exactly one increment per CS entry).

- **Message Count:**

  - Tracks how many messages each process sent, highlighting the algorithm’s overhead.

- **Execution Time:**

  - Measures the total time for all processes to complete their CS requests.
#bash output
```bash
--- Final Results ---
Critical Section History (cs_history): [(0, 12), (8, 34), (4, 44), (6, 51), (5, 57), (3, 65), (2, 74), (9, 83), (7, 85), (1, 89)]
Global shared counter (shared_counter): 10
Message Count: {0: 18, 1: 18, 2: 18, 3: 18, 4: 18, 5: 18, 6: 18, 7: 18, 8: 18, 9: 18}
Total messages sent: 180
All processes respected Safety, Liveness, and Fairness.

Total execution time: 16.9793 seconds
Gantt Chart Visualization:
Visualizes the timeline of CS access for each process.
(p = 10 processes)
```
![alt text](image.png)

---

## **Conclusion**

- **What the System Demonstrates:**

  - A functional implementation of Lamport’s Mutual Exclusion algorithm with practical features like deadlock recovery and persistent connections.

- **Strengths:**

  - Simplicity and correctness.
  - Real-time simulation of distributed systems.
  - Demonstrates critical section access under mutual exclusion guarantees.

- **Weaknesses:**

  - Message overhead scales poorly with the number of processes.
  - Requires full connectivity between all processes.

---

## **Future Enhancements**

1. **Fault Tolerance:**

   - Handle process/node failures gracefully.

2. **Optimization:**

   - Use more efficient algorithms like Ricart-Agrawala or Maekawa’s algorithm for reduced message complexity.

3. **Dynamic Scaling:**

   - Support dynamic addition/removal of processes during runtime.

4. **Visualization:**

   - Provide graphical outputs (e.g., Gantt charts) for better understanding of CS access patterns.

---

