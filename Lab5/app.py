import serial
import time
import csv
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from datetime import datetime

SERIAL_PORT = '/dev/cu.usbmodem14101' 
BAUD_RATE = 9600
LOG_FILE = 'threshold_exceeded_log.csv'

# Setup Serial Connection
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2) # Allow Arduino to reset
except Exception as e:
    print(f"Error: {e}")
    exit()

# Setup Data plotting
x_data, y_data = [], []
fig, ax = plt.subplots()
line, = ax.plot([], [], lw=2, color='blue')
ax.set_ylim(0, 1024)
ax.set_xlim(0, 100)
ax.set_title("Live Sound Level Visualization")
ax.set_ylabel("Analog Value")
ax.set_xlabel("Time")

# Initialize CSV Log
with open(LOG_FILE, mode='w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(["Timestamp", "Sound Level"])

def update_plot(frame):
    if ser.in_waiting > 0:
        try:
            line_data = ser.readline().decode('utf-8').strip()
            if ',' in line_data:
                sound_val_str, threshold_str = line_data.split(',')
                sound_val = int(sound_val_str)
                is_triggered = int(threshold_str)

                # Append data for visualization
                x_data.append(len(x_data))
                y_data.append(sound_val)
                
                # Keep list sizes manageable
                if len(x_data) > 100:
                    x_data.pop(0)
                    y_data.pop(0)
                    ax.set_xlim(x_data[0], x_data[-1])

                line.set_data(x_data, y_data)

                # Visual indicator: change line color to red if high
                line.set_color('red' if sound_val > 600 else 'blue')

                # Log ONLY if threshold was exceeded (Triggered by ISR)
                if is_triggered == 1:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                    with open(LOG_FILE, mode='a', newline='') as file:
                        writer = csv.writer(file)
                        writer.writerow([timestamp, sound_val])
                    print(f"Logged Threshold Event: {timestamp} | Level: {sound_val}")

        except ValueError:
            pass # Ignore corrupted serial lines
            
    return line,

ani = animation.FuncAnimation(fig, update_plot, interval=50, blit=False)
plt.show()
