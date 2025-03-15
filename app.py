import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, filedialog
import sounddevice as sd
import numpy as np
import wave
import os
from datetime import datetime

# Filepath to the config file
config_file_path = 'config.txt'

# Default save directory (the current directory of the application)
default_save_directory = os.getcwd()

# Function to read the config file and load the save directory
def load_config():
    global save_directory
    save_directory = default_save_directory  # Set default directory at the beginning
    
    if os.path.exists(config_file_path):
        with open(config_file_path, 'r') as f:
            lines = f.readlines()
            for line in lines:
                if line.startswith('save_directory='):
                    save_directory = line.strip().split('=')[1]
                    break
    
    # Update the label to display the correct path
    save_directory_button.config(text=f"Save Directory: {save_directory}")

# Function to write the save directory to the config file
def save_config():
    with open(config_file_path, 'w') as f:
        f.write(f"save_directory={save_directory}\n")

# Function to retrieve valid input devices
def get_input_devices():
    devices = sd.query_devices()
    input_devices = []
    
    # Add only valid devices
    for device in devices:
        if device['max_input_channels'] > 0 and "Microsoft Sound Mapper - Input" not in device['name']:
            input_devices.append(device['name'])  # Add only valid devices
    return input_devices

# Global variables
listening = False
circular_buffer = None
stream = None
save_directory = None

# Function to log messages
def log_message(message):
    log_text.config(state=tk.NORMAL)  # Enable text box to insert text
    log_text.insert(tk.END, message + '\n')
    log_text.yview(tk.END)  # Scroll to the latest message
    log_text.config(state=tk.DISABLED)  # Disable text box after insertion

# Function to start listening
def start_listening():
    global listening, circular_buffer, stream
    # Check if a device is selected
    if not device_combobox.get():
        log_message("Error: Please select an input device.")
        return
    
    try:
        listening = True
        pastille_canvas.itemconfig(pastille, fill="red")  # Visual indicator (red dot)
        selected_device = device_combobox.get()
        device_index = next(i for i, d in enumerate(sd.query_devices()) if d['name'] == selected_device)
        sd.default.device = device_index
        sd.default.samplerate = 44100
        sd.default.channels = 1
        
        buffer_size = int(44100 * 300)  # 300 seconds
        circular_buffer = np.zeros(buffer_size, dtype=np.float32)
        
        def audio_callback(indata, frames, time, status):
            global circular_buffer
            if status:
                log_message(f"Status: {status}")
            # Add new data to the circular buffer
            circular_buffer[:-frames] = circular_buffer[frames:]
            circular_buffer[-frames:] = indata[:, 0]
        
        # Start the audio stream
        stream = sd.InputStream(callback=audio_callback)
        stream.start()
        log_message("Listening has started.")
    except Exception as e:
        log_message(f"Error starting listening: {e}")

# Function to stop listening
def stop_listening():
    global listening, stream
    if listening:
        listening = False
        pastille_canvas.itemconfig(pastille, fill="gray")  # Reset visual indicator (gray dot)
        if stream is not None:
            stream.stop()  # Stop the stream
            stream.close()  # Close the stream
        log_message("Listening has stopped.")
    else:
        log_message("No listening session is currently active.")

# Function to select the directory for saving captures
def select_save_directory():
    global save_directory
    directory = filedialog.askdirectory(title="Select Folder for Captures")
    if directory:  # Only update if the user selects a directory
        save_directory = directory
        save_directory_button.config(text=f"Save Directory: {save_directory}")
        log_message(f"Capture files will be saved to: {save_directory}")
        save_config()  # Save the new directory to the config file

def capture_audio():
    global listening, circular_buffer, stream, save_directory
    if not listening:
        log_message("Error: Listening has not started.")
        return

    # Pause listening while configuring the capture
    log_message("Pausing listening for capture configuration...")
    stop_listening()

    # Prompt for the filename
    filename = simpledialog.askstring("File Name", "Enter the file name:",
                                       initialvalue=f"capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    if not filename:  # Cancel pressed or empty input
        log_message("Capture canceled by the user.")
        start_listening()
        return

    # Ensure the extension
    if not filename.lower().endswith('.wav'):
        filename += '.wav'

    # Check save directory
    if not save_directory:
        save_directory = default_save_directory
        log_message(f"No directory selected. Using default directory: {save_directory}")

    # Generate the full file path
    file_path = os.path.join(save_directory, filename)

    # Check for overwrites
    if os.path.exists(file_path):
        overwrite = messagebox.askyesno("File exists", f"The file {filename} already exists. Do you want to overwrite it?")
        if not overwrite:
            log_message("Capture aborted: file not overwritten.")
            start_listening()
            return

    # Prompt for duration
    duration = simpledialog.askinteger("Capture Duration", "Capture duration (in seconds, 1-300):",
                                       minvalue=1, maxvalue=300)
    if not duration:  # Cancel pressed
        log_message("Capture canceled.")
        start_listening()
        return

    # Retrieve and save data
    try:
        sample_rate = 44100
        num_samples = duration * sample_rate
        captured_audio = circular_buffer[-num_samples:]

        with wave.open(file_path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes((captured_audio * 32767).astype(np.int16))
        log_message(f"Capture saved as {file_path}")
    except Exception as e:
        log_message(f"Error saving the recording: {e}")

    # Resume listening after capture dialog closes
    log_message("Resuming listening...")
    start_listening()


# Function to update the visual spectrum (simple amplitude-based display)
def update_spectrometer():
    global circular_buffer
    if listening and circular_buffer is not None:
        # Get the latest data from the circular buffer
        data = circular_buffer[-2048:]  # Take the last 2048 samples for better sensitivity
        
        # Calculate the amplitude (root mean square of the signal)
        amplitude = np.sqrt(np.mean(data**2))
        
        # Update the spectrometer bars based on the amplitude
        # Adjust the threshold for each bar based on the intensity
        for i in range(len(spectrometer_bars)):
            # More sensitive display
            if amplitude > (i + 1) * 0.005:  # Lower threshold for even greater sensitivity
                spectrometer_bars[i].config(height=10)  # Show bar (height 10)
            else:
                spectrometer_bars[i].config(height=1)  # Hide bar (height 1)
    
    # Call the function again after 50ms to update the spectrometer in real-time
    root.after(50, update_spectrometer)

# Setup the main window
root = tk.Tk()
root.title("Audio capture app")
root.geometry("350x500")

# Title label
label = tk.Label(root, text="Select an Audio Input Device", font=("Arial", 13))
label.pack(pady=10)

# Frame for input device selection
device_frame = tk.Frame(root)
device_frame.pack(pady=10)

# ComboBox for selecting the device
device_combobox = ttk.Combobox(device_frame, width=35)
device_combobox.grid(row=0, column=0, padx=10)

# Initialize the list of devices
input_devices = get_input_devices()
device_combobox['values'] = input_devices
if input_devices:
    device_combobox.current(0)

# Frame for listening control
control_frame = tk.Frame(root)
control_frame.pack(pady=20)

# Start Listening button
start_button = tk.Button(control_frame, text="Start Listening", command=start_listening)
start_button.grid(row=0, column=0, padx=10)

# Canvas for visual indicator (red dot)
pastille_canvas = tk.Canvas(control_frame, width=20, height=20)
pastille = pastille_canvas.create_oval(5, 5, 15, 15, fill="gray")
pastille_canvas.grid(row=0, column=1, padx=10)

# Stop Listening button
stop_button = tk.Button(control_frame, text="Stop Listening", command=stop_listening)
stop_button.grid(row=0, column=2, padx=10)

# Spectrometer container frame with fixed dimensions
spectrometer_container = tk.Frame(root, height=25, width=350,)
spectrometer_container.pack_propagate(False)  # Prevents resizing
spectrometer_container.pack(pady=20)

# Inner canvas for the spectrometer
spectrometer_canvas = tk.Canvas(spectrometer_container, height=25, width=350)
spectrometer_canvas.pack(fill=tk.BOTH, expand=True)

# Inner frame for spectrometer bars
spectrometer_frame = tk.Frame(spectrometer_canvas, height=25, width=350)
spectrometer_frame.pack_propagate(False)  # Prevent the frame from resizing to its children
spectrometer_canvas.create_window((0, 0), window=spectrometer_frame, anchor="nw")

# Define the size and layout for bars
spectrometer_bars = []
num_bars = 80
bar_width = 5
bar_spacing = 1
bar_height = 1  # Minimum height

for i in range(num_bars):
    bar = tk.Canvas(
        spectrometer_frame,
        width=bar_width,
        height=bar_height,
        bg="black",
        highlightthickness=0  # Remove border
    )
    bar.place(x=i * (bar_width + bar_spacing), y=0)  # Position bar
    spectrometer_bars.append(bar)

# Add capture button and save directory button
capture_button = tk.Button(root, text="Capture", command=capture_audio)
capture_button.pack(pady=0)

save_directory_button = tk.Button(root, text="Save Directory: ", command=select_save_directory)
save_directory_button.pack(pady=30)

# Log window for feedback
log_text = tk.Text(root, height=10, width=60, state=tk.DISABLED)
log_text.pack(pady=10)

# Initialize spectrometer update loop
update_spectrometer()

# Load the configuration file
load_config()

# Start the Tkinter main loop
root.mainloop()
