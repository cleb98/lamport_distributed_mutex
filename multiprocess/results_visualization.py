import os
import json
import matplotlib.pyplot as plt

def load_results(results_dir):
    """
    Load results from JSON files in the specified directory.

    Args:
        results_dir (str): Path to the directory containing results JSON files.

    Returns:
        list: A list of tuples (number_of_processes, execution_time).
    """
    execution_times = []
    num_tot_mess = []
    num_processes = []


    # Read all JSON files from the results directory
    for file_name in os.listdir(results_dir):
        if file_name.endswith('.json'):
            file_path = os.path.join(results_dir, file_name)
            with open(file_path, 'r') as json_file:
                result = json.load(json_file)
                # Extract execution time and number of processes
                execution_times.append(result.get("execution_time", 0))
                num_processes.append(result.get("shared_counter", 0))
                num_tot_mess.append(result.get("total_messages", 0))
    
    # Return paired results
    return num_processes, execution_times, num_tot_mess

def plot_execution_time(num_processes, execution_times):
    """
    Plot the execution time against the number of processes, excluding zeros,
    and annotate each point with the corresponding number of processes.

    Args:
        num_processes (list): List of numbers of processes.
        execution_times (list): List of execution times.
    """
    # Filter out zero values
    filtered_results = [(n, t) for n, t in zip(num_processes, execution_times) if n > 0 and t > 0]
    if not filtered_results:
        print("No valid data to plot after excluding zeros.")
        return

    # Unpack the filtered results
    num_processes, execution_times = zip(*filtered_results)

    # Sort the results by the number of processes for better visualization
    sorted_results = sorted(zip(num_processes, execution_times))
    num_processes, execution_times = zip(*sorted_results)

    # Plot the execution time vs. number of processes
    plt.figure(figsize=(10, 6))
    plt.plot(num_processes, execution_times, marker='o', linestyle='-', color='b', label='Execution Time')

    # Annotate each point with the corresponding number of processes
    for n, t in zip(num_processes, execution_times):
        plt.annotate(f'{t:.2f}', (n, t), textcoords="offset points", xytext=(5, 5), ha='center', fontsize=9, color='black')

    plt.xlabel('Number of Processes')
    plt.ylabel('Execution Time (seconds)')
    plt.title('Execution Time vs. Number of Processes')
    plt.grid(True)
    plt.legend(['Execution Time'])
    plt.tight_layout()
    #save the plot
    plt.savefig('multiprocess/results/execution_time_vs_num_processes.png')
    # Show the plot
    plt.show()


def plot_total_mex(num_processes, total_messages):
    """
    Plot the execution time against the number of processes, excluding zeros,
    and annotate each point with the corresponding number of processes.

    Args:
        num_processes (list): List of numbers of processes.
        total_messages (list): List of total messages.
    """
    # Filter out zero values
    filtered_results = [(n, t) for n, t in zip(num_processes, total_messages) if n > 0 and t > 0]
    if not filtered_results:
        print("No valid data to plot after excluding zeros.")
        return

    # Unpack the filtered results
    num_processes, tot_mex = zip(*filtered_results)

    # Sort the results by the number of processes for better visualization
    sorted_results = sorted(zip(num_processes, tot_mex))
    num_processes, tot_mex = zip(*sorted_results)

    # Plot the execution time vs. number of processes
    plt.figure(figsize=(10, 6))
    plt.plot(num_processes, tot_mex, marker='o', linestyle='-', color='b', label='total_messages')

    # Annotate each point with the corresponding number of processes
    for n, t in zip(num_processes, tot_mex):
        plt.annotate(f'{t}', (n, t), textcoords="offset points", xytext=(5, 5), ha='center', fontsize=9, color='black')

    plt.xlabel('Number of Processes')
    plt.ylabel('Total messages')
    plt.title('Total messages sent by all processes vs. Number of Processes')
    plt.grid(True)
    plt.legend(['Number of messages'])
    plt.tight_layout()

    # Save the plot
    plt.savefig('multiprocess/results/total_messages_vs_num_processes.png')
    # Show the plot
    plt.show()

    

    



if __name__ == "__main__":
    # Path to the directory containing JSON result files
    results_dir = 'multiprocess/results'

    # Load the results
    num_processes, execution_times, num_tot_mex  = load_results(results_dir)

    # Plot the results
    plot_execution_time(num_processes, execution_times)
    plot_total_mex(num_processes, num_tot_mex)
