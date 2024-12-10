import tkinter as tk
from tkinter import ttk, simpledialog
import sounddevice as sd
import numpy as np
import wave
from datetime import datetime

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
        pastille_label.config(bg="red")  # Visual indicator
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
        pastille_label.config(bg="gray")  # Reset visual indicator
        if stream is not None:
            stream.stop()  # Stop the stream
            stream.close()  # Close the stream
        log_message("Listening has stopped.")
    else:
        log_message("No listening session is currently active.")

# Function to capture audio and save it to a file
def capture_audio():
    global listening, circular_buffer, stream
    if not listening:
        log_message("Error: Listening has not started.")
        return
    
    # Pause listening while configuring the capture
    log_message("Pausing listening for capture configuration...")
    stop_listening()
    
    # Ask user for file name and capture duration
    filename = simpledialog.askstring("File Name", "Enter the file name (e.g., capture_YYYYMMDD_HHMMSS.wav):",
                                      initialvalue=f"capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav")
    if not filename:
        return

    duration = simpledialog.askinteger("Capture Duration", "Capture duration (in seconds, 1-300):",
                                       minvalue=1, maxvalue=300)
    if not duration:
        return

    # Retrieve necessary data from the buffer
    sample_rate = 44100
    num_samples = duration * sample_rate
    captured_audio = circular_buffer[-num_samples:]

    # Save to WAV file
    try:
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(1)  # Mono
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            wf.writeframes((captured_audio * 32767).astype(np.int16))  # Convert to int16
        log_message(f"Capture saved as {filename}")
    except Exception as e:
        log_message(f"Error saving the recording: {e}")

    # Resume listening after the capture dialog is closed
    log_message("Resuming listening...")
    start_listening()

# Setup the main window
root = tk.Tk()
root.title("Select an Input Device")
root.geometry("500x400")

# Title label
label = tk.Label(root, text="Select an Audio Input Device")
label.pack(pady=10)

# ComboBox for selecting the device
device_combobox = ttk.Combobox(root, width=50)
device_combobox.pack(pady=10)

# Initialize the list of devices
input_devices = get_input_devices()
device_combobox['values'] = input_devices
if input_devices:
    device_combobox.current(0)

# Button to start listening
start_button = tk.Button(root, text="Start Listening", command=start_listening)
start_button.pack(pady=10)

# Button to stop listening
stop_button = tk.Button(root, text="Stop Listening", command=stop_listening)
stop_button.pack(pady=10)

# Button to capture audio
capture_button = tk.Button(root, text="Capture", command=capture_audio)
capture_button.pack(pady=10)

# Visual indicator for active listening
pastille_label = tk.Label(root, text="", bg="gray", width=10, height=2)
pastille_label.pack(pady=10)

# Log text area to display messages
log_text = tk.Text(root, width=60, height=10, wrap=tk.WORD, state=tk.DISABLED)
log_text.pack(padx=10, pady=10)

# Start the graphical interface
root.mainloop()
