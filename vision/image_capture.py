"""
Timed image capture from two USB cameras, used to build the lettuce dataset.
Saves one frame per camera every INTERVAL seconds. Press ESC to stop.
"""
import os
from datetime import datetime

import cv2

# Settings
SAVE_FOLDER_1 = "captured_images_1"  # output folder for camera 1
SAVE_FOLDER_2 = "captured_images_2"  # output folder for camera 2
INTERVAL = 5 * 60  # capture interval (seconds)
BRIGHTNESS = -20   # brightness offset applied to each frame (negative = darker)

os.makedirs(SAVE_FOLDER_1, exist_ok=True)
os.makedirs(SAVE_FOLDER_2, exist_ok=True)

# Open the cameras
cap1 = cv2.VideoCapture(0)
cap2 = cv2.VideoCapture(1)

cap1.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap1.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
cap1.set(cv2.CAP_PROP_EXPOSURE, -7.9)  # lower exposure (range depends on the camera)

cap2.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap2.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
cap2.set(cv2.CAP_PROP_EXPOSURE, -8)

if not cap1.isOpened() or not cap2.isOpened():
    print("Could not open the cameras")
    exit()

print("Press ESC to quit")

try:
    while True:
        ret1, frame1 = cap1.read()
        ret2, frame2 = cap2.read()

        if not ret1 or not ret2:
            print("Could not read a frame")
            break

        # Adjust brightness (alpha=1.0 keeps contrast, beta shifts brightness)
        frame1 = cv2.convertScaleAbs(frame1, alpha=1.0, beta=BRIGHTNESS)
        frame2 = cv2.convertScaleAbs(frame2, alpha=1.0, beta=BRIGHTNESS)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename1 = f"{SAVE_FOLDER_1}/camera1_{timestamp}.jpg"
        filename2 = f"{SAVE_FOLDER_2}/camera2_{timestamp}.jpg"

        cv2.imwrite(filename1, frame1)
        cv2.imwrite(filename2, frame2)
        print(f"Saved: {filename1}, {filename2}")

        # Wait for the next capture, checking for ESC once per second
        for _ in range(INTERVAL):
            if cv2.waitKey(1000) & 0xFF == 27:
                raise KeyboardInterrupt

except KeyboardInterrupt:
    print("\nStopped")

cap1.release()
cap2.release()
cv2.destroyAllWindows()
