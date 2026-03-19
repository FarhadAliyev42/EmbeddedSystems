import serial
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from datetime import datetime
import csv
import sys
import math

# --- Configuration ---
SERIAL_PORT = '/dev/cu.usbmodem1101' 
BAUD_RATE = 115200; 
LOG_FILE = "exceeded_thresholds_log.csv"

# Set this to wherever you want the visual red line to appear!
THRESHOLD_DB = 80.0  

# --- Connect to Arduino ---
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
except Exception as e:
    print(f"Error connecting to {SERIAL_PORT}: {e}")
    sys.exit()

# --- Setup Visualization ---
x_data, y_data = [], []
fig, ax = plt.subplots()
line, = ax.plot(x_data, y_data, color='blue', linewidth=2)

ax.set_title("Real-Time Sound Level (Decibels)")
ax.set_ylabel("Level (dB)")
ax.set_xlabel("Time (Samples)")

# Initialize CSV log file with headers
with open(LOG_FILE, "a", newline='') as file:
    writer = csv.writer(file)
    file.seek(0, 2)
    if file.tell() == 0:
        writer.writerow(["Timestamp", "Sound Level (dB)"])

def update_graph(frame):
    try:
        line_data = None
        
        while ser.in_waiting > 0:
            line_data = ser.readline().decode('utf-8').strip()
            
        if line_data and ";" in line_data:
            sound_str, interrupt_str = line_data.split(",")
            raw_value = int(sound_str)
            interrupt_flag = int(interrupt_str)

            if raw_value > 0:
                db_level = (20 * math.log10(raw_value)) * 1.5
            else:
                db_level = 30.0

            x_data.append(frame)
            y_data.append(db_level)

            if len(x_data) > 100:
                x_data.pop(0)
                y_data.pop(0)

            line.set_data(x_data, y_data)
            
            ax.set_xlim(min(x_data), max(x_data) + 1)
            current_max_y = max(y_data)
            ax.set_ylim(0, max(120, current_max_y + 10))

            if interrupt_flag == 1:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(LOG_FILE, "a", newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow([timestamp, f"{db_level:.2f} dB"])
            else:
                line.set_color('blue')

    except Exception as e:
        pass
    return line,

ani = animation.FuncAnimation(fig, update_graph, frames=range(100000), interval=50, blit=False)

plt.show()

ser.close()
