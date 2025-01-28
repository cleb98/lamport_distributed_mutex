# main.py
import multiprocessing
import time
import random
import threading
import json
import matplotlib.pyplot as plt

from lamport_node import LamportNode

def visualize_results(data, cs_history, total_processes):
    # type: (list[tuple[int, float, float]], list[tuple[int, int]], int) -> None
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
    ax.set_title("Gantt Chart of Critical Section Execution")
    ax.grid(True)

    # Latency Analysis
    ax = axes[1]
    bars = ax.bar(processes, avg_latency_values, alpha=0.7, color='tab:blue')
    for bar, value in zip(bars, avg_latency_values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2, f'{value:.1f}',
                ha='center', va='bottom', fontsize=10, color='black')
    #spazio tra i plot
    plt.subplots_adjust(hspace=2)
    ax.set_title("Average Latency to Access Critical Section")
    ax.set_xlabel("Process ID")
    ax.set_ylabel("Average Latency (Lamport Clock Ticks)")
    ax.set_xticks(processes)
    ax.grid(axis="y", linestyle="--", alpha=0.7)

    plt.tight_layout()
    plt.savefig(f"results{total_processes}.png")
    plt.show()
    plt.close()

def node_main(
        my_id, 
        total_nodes,
        cs_history,
        message_count,
        shared_counter, 
        visualization_data, 
        iterations=1
    ):
    
    """
    Main function executed by each LamportNode process.

    Args:
        my_id (int): Unique ID of the node.
        total_nodes (int): Total number of nodes in the system.

    Steps:
    1. Initialize the LamportNode with its ID, total nodes, and port.
    2. Start the server in a separate thread to handle incoming connections.
    3. Allow time for all nodes to start their servers.
    4. Request access to the critical section.
    5. Simulate critical section execution.
    6. Release the critical section.
    7. Broadcast a SHUTDOWN message to notify peers of completion.
    8. Wait until the node receives SHUTDOWN messages from all peers.
    9. Stop the node and log completion.
    """
    # Step 1: Initialize LamportNode
    node_port = 5000 + my_id
    node = LamportNode(
                my_id, 
                total_nodes, 
                node_port,
                cs_history,
                message_count,
                shared_counter, 
                visualization_data
            )

    # Step 2: Start the server in a thread
    server_thread = threading.Thread(target=node.run_server, daemon=True)
    server_thread.start()

    # Step 3: Wait for all nodes to start
    time.sleep(1)

    for i in range(iterations):
        #random sleep time before entering the CS
        time.sleep(random.uniform(1, 1.5))
        # Step 4: Request access to the critical section
        node.request_cs()
        print(f"[Process {my_id}] INSIDE CRITICAL SECTION")

        # Step 5: Simulate critical section execution 
        # it is done inside request_cs to keep trak of how many time the CS is executed
        # if you prefer to simulate the CS execution here, you can uncomment the following lines and comment in the request_cs method
        # time.sleep(random.uniform(0.5, 1.0)) 

        # Step 6: Release the critical section
        node.release_cs()

        #some random sleep time after releasing the CS
        print(f"[Process {my_id}] FINISHED CRITICAL SECTION")
        time.sleep(random.uniform(1, 1.5)) #simulate latency after CS


    # Step 7: Broadcast SHUTDOWN
    node.broadcast_shutdown()

    # Step 8: Wait until node stops (all peers are done)
    while node.running:
        time.sleep(0.2)

    # Step 9: Log completion
    print(f"[Process {my_id}] Node fully stopped (all peers done).")


def main():
    """
    Main function to start the LamportNode processes.

    Steps:
    1. Set the multiprocessing start method to 'spawn' for cross-platform compatibility.
    2. Define the total number of nodes in the system.
    3. Create a multiprocessing.Process for each node.
    4. Start all processes.
    5. Wait for all processes to complete using join().
    6. Log completion after all processes finish.
    """
    # Step 1: Set the multiprocessing start method
    multiprocessing.set_start_method('spawn', force=True)

    # Step 2: 
    # Define total number of nodes 
    total_nodes = int(input("Enter the number of processes: "))

    #create manager backend shared data
    manager = multiprocessing.Manager()

    cs_history = manager.list() # store (process_id, lamport_clock) for each CS entry
    message_count = manager.dict() # store message count for each process
    shared_counter = manager.Value('i', 0) # shared counter for CS execution
    visualization_data = manager.list()  # Track (process_id, start_time, end_time)

    #message_count initialization
    for i in range(total_nodes):
        message_count[i] = 0

    processes = []
    iteration = int(input("Enter the number of CS access for each process: "))

    # Step 3: Create a process for each node
    for pid in range(total_nodes):
        p = multiprocessing.Process(target=node_main, args=(pid, total_nodes, cs_history, message_count, shared_counter, visualization_data, iteration))
        processes.append(p)

    start_time = time.time() # start time of the simulation
    # Step 4: Start all processes
    for p in processes:
        p.start()

    # Step 5: Wait for all processes to complete
    for p in processes:
        p.join()

    end_time = time.time() # end time of the simulation
    execution_time = end_time - start_time


    # Step 6: Log completion and data visualization-storing
    print("All processes finished. No connection reset errors should occur.")

    #convert manager types to standard python types 
    cs_history_list = list(cs_history)
    message_count_dict = dict(message_count)
    total_msgs = sum(message_count_dict.values())
    final_counter = shared_counter.value

    print("\n--- Final Results ---")
    print("cs_history:", cs_history_list)
    print("shared_counter:", final_counter)
    print("message_count:", message_count_dict)
    print("Total messages sent:", total_msgs)
    print("Execution time:", f"{execution_time:.4f}s")

    # Build the final JSON
    results = {
        "cs_history": cs_history_list,
        "shared_counter": final_counter,
        "message_count": message_count_dict,
        "total_messages": total_msgs,
        "execution_time": execution_time
    }

    with open(f"results{final_counter}.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"Results saved to results{final_counter}.json")

    # print("Visualization Data:")
    # print(visualization_data)

    print("Visualizing Results:")
    visualize_results(visualization_data, cs_history, total_nodes)


 

if __name__ == "__main__":
    main()
