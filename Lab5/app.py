import sys
import serial
import time
import serial.tools.list_ports
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame
from PyQt6.QtCore import QTimer, Qt

class Lab4FinalGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.is_running = False
        self.initUI()
        self.setup_serial()

    def setup_serial(self):
        ports = list(serial.tools.list_ports.comports())
        target = next((p.device for p in ports if "usb" in p.device.lower()), None)
        try:
            self.ser = serial.Serial(target, 9600, timeout=0.1)
        except:
            self.ser = None

    def initUI(self):
        self.setWindowTitle('Lab 4: 4-Way Joystick System')
        layout = QVBoxLayout()

        self.toggle_btn = QPushButton('START SYSTEM', self)
        self.toggle_btn.clicked.connect(self.toggle)
        layout.addWidget(self.toggle_btn)

        # 2D Visualization Box 
        self.viz_frame = QFrame()
        self.viz_frame.setFixedSize(200, 300)
        self.viz_frame.setStyleSheet("background-color: black; border: 2px solid gray;")
        self.pointer = QLabel("+", self.viz_frame)
        self.pointer.setStyleSheet("color: lime; font-weight: bold; font-size: 20px;")
        self.pointer.move(90, 90)
        layout.addWidget(self.viz_frame, alignment=Qt.AlignmentFlag.AlignCenter)

        # Virtual LED Indicators
        self.led_layout = QHBoxLayout()
        self.led_indicators = {
            'L': QLabel('LEFT'), 'R': QLabel('RIGHT'), 
            'U': QLabel('UP'), 'D': QLabel('DOWN')
        }
        for label in self.led_indicators.values():
            label.setStyleSheet("background-color: #333; color: white; padding: 5px;")
            self.led_layout.addWidget(label)
        layout.addLayout(self.led_layout)

        self.data_label = QLabel('X: 2.50V | Y: 2.50V | Button: RLSD')
        layout.addWidget(self.data_label)

        self.setLayout(layout)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_gui)
        self.timer.start(30)

    def toggle(self):
        self.is_running = not self.is_running
        self.toggle_btn.setText("STOP" if self.is_running else "START")

    def update_gui(self):
        if not self.is_running or not self.ser: return
        if self.ser.in_waiting > 0:
            try:
                line = self.ser.readline().decode('utf-8').strip()
                d = dict(item.split(":") for item in line.split(","))
                
                # Update Text
                self.data_label.setText(f"X: {d['X']}V | Y: {d['Y']}V | Button: {d['B']}")


                px = 180 - int((float(d['X']) / 5.0) * 180)
                
                py = 180 - int((float(d['Y']) / 5.0) * 180)
    
                self.pointer.move(px, py)

                self.set_led_style('L', d['L'])
                self.set_led_style('R', d['R'])
                self.set_led_style('U', d['U'])
                self.set_led_style('D', d['D'])
            except: pass

    def set_led_style(self, key, state):
        color = "red" if state == "1" else "#333"
        self.led_indicators[key].setStyleSheet(f"background-color: {color}; color: white; padding: 5px;")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = Lab4FinalGUI()
    ex.show()
    sys.exit(app.exec())
