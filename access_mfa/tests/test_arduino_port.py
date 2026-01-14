import os
import time
import serial

PORT = os.getenv("ARDUINO_PORT", "COM5")
BAUD = int(os.getenv("ARDUINO_BAUD", "9600"))

ser = serial.Serial(PORT, BAUD, timeout=1)
time.sleep(2)

print("OK: puerto abierto", PORT)

ser.write(bytes([1,1,1,1,1]))
ser.flush()
time.sleep(1)

ser.write(bytes([0,0,0,0,0]))
ser.flush()

ser.close()
print("OK: puerto cerrado")
