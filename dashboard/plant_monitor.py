"""
Plant monitoring module: captures an image from each group's camera, runs the
YOLOv8-seg model, and measures lettuce canopy height, width and area.

Measurement follows the "segmentation-first" method described in the thesis
(Section 3.1.3, Figure 17): area comes from the mask pixel count, height and
width from the mask's extreme pixel coordinates, with a bounding-box fallback.
"""
import base64
import os
import random

import cv2
import numpy as np
from ultralytics import YOLO

# --- Configuration ---
# Path to the trained YOLOv8-seg weights (not included in the repo, see README).
BEST_MODEL_PATH = os.environ.get("MODEL_PATH", "weights/best.pt")
CONFIDENCE_THRESHOLD = 0.5
TARGET_CLASS = "lettuce"  # compared case-insensitively ("Lettuce" / "lettuce")

# --- Group-specific calibration factors ---
# Pixels per centimetre for each camera, measured with a reference object of
# known size at the fixed camera-to-plant distance. Replace with your own values.
PIXELS_PER_CM_CONFIG = {
    'Low_PlantSensor': 25.5,     # Camera 1 - Low DO group
    'Medium_PlantSensor': 28.0,  # Camera 2 - Medium DO group
    'High_PlantSensor': 24.2,    # Camera 3 - High DO group
}

# --- Camera feeds / group configuration ---
# Values can be a USB camera index ('0', '1', '2'), a local image path,
# or an RTSP/HTTP stream URL.
SIMULATED_CAMERA_FEEDS = {
    'Low_PlantSensor': '0',
    'Medium_PlantSensor': '1',
    'High_PlantSensor': '2',
}

# Initialize model once for efficiency
try:
    PLANT_SEG_MODEL = YOLO(BEST_MODEL_PATH)
except Exception as e:
    PLANT_SEG_MODEL = None
    print(f"Warning: Could not load YOLO model from {BEST_MODEL_PATH}. Using dummy data. Error: {e}")


def _acquire_image(group_name: str, source: str):
    """Reads one frame from a USB camera index, a file path, or a stream URL."""
    if source.isdigit() or source.lower().startswith(('rtsp://', 'http://', 'https://')):
        cap = cv2.VideoCapture(int(source) if source.isdigit() else source)
        if not cap.isOpened():
            print(f"Error: Could not open camera/stream '{source}' for {group_name}.")
            return None
        ret, frame = cap.read()
        cap.release()  # Release the camera immediately after reading
        if not ret:
            print(f"Error: Could not read frame from '{source}' for {group_name}.")
            return None
        return frame
    if os.path.exists(source):
        return cv2.imread(source)
    print(f"Error: Invalid path/URL or configuration for {group_name}: {source}")
    return None


def measure_plant_dimensions(group_name: str, image_path: str) -> list:
    """
    Runs segmentation on the group's image and returns one dict per detected plant:
    [{'name': 'lettuce', 'height_cm': 7.4, 'width_cm': 6.2, 'area_cm2': 35.1,
      'confidence': 0.98, 'base64_image': '...'}, ...]
    """
    px_per_cm = PIXELS_PER_CM_CONFIG.get(group_name, 25.0)
    cm2_per_pixel = 1.0 / (px_per_cm ** 2)

    if PLANT_SEG_MODEL is None or not image_path:
        return _generate_dummy_data()

    image = _acquire_image(group_name, image_path)
    if image is None:
        return _generate_dummy_data()

    # retina_masks=True returns masks at the original image resolution,
    # so pixel measurements match the captured image.
    results = PLANT_SEG_MODEL(image, retina_masks=True, verbose=False)

    plant_metrics = []
    for r in results:
        if r.boxes is None:
            continue
        masks = r.masks.data.cpu().numpy() if r.masks is not None else None

        for i in range(len(r.boxes)):
            class_name = r.names[int(r.boxes.cls[i])]
            confidence = float(r.boxes.conf[i])
            if class_name.lower() != TARGET_CLASS or confidence <= CONFIDENCE_THRESHOLD:
                continue

            x1, y1, x2, y2 = [int(v) for v in r.boxes.xyxy[i].tolist()]

            # --- Measurement (segmentation-first) ---
            if masks is not None:
                binary_mask = masks[i] > 0.5
                # True leaf area (pixel count -> cm^2)
                area_cm2 = float(np.sum(binary_mask)) * cm2_per_pixel

                ys, xs = np.where(binary_mask)
                if len(xs) > 10 and len(ys) > 10:
                    height_px = ys.max() - ys.min()
                    width_px = xs.max() - xs.min()
                    x1, y1, x2, y2 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
                else:
                    height_px = y2 - y1
                    width_px = x2 - x1
            else:
                # Fallback (rare): use the bounding box
                height_px = y2 - y1
                width_px = x2 - x1
                area_cm2 = (height_px * width_px) * cm2_per_pixel

            plant_metrics.append({
                'name': class_name,
                'height_cm': float(height_px) / px_per_cm,
                'width_cm': float(width_px) / px_per_cm,
                'area_cm2': area_cm2,
                'confidence': confidence,
                'min_x': x1, 'min_y': y1, 'max_x': x2, 'max_y': y2,
            })

    # Annotate the image and encode it for display on the web page
    annotated_image = _annotate_image(image, plant_metrics)
    _, buffer = cv2.imencode('.jpg', annotated_image)
    base64_img = 'data:image/jpeg;base64,' + base64.b64encode(buffer.tobytes()).decode('ascii')

    # Attach the image once per group (the app separates it from the metrics)
    if plant_metrics:
        plant_metrics[0]['base64_image'] = base64_img

    return plant_metrics


def _annotate_image(image, plant_metrics):
    """Draws the bounding box and measurements for each plant."""
    annotated_image = image.copy()
    for plant in plant_metrics:
        min_x, min_y = plant['min_x'], plant['min_y']
        max_x, max_y = plant['max_x'], plant['max_y']
        cv2.rectangle(annotated_image, (min_x, min_y), (max_x, max_y), (0, 255, 0), 2)

        text = f"H: {plant['height_cm']:.1f}cm, W: {plant['width_cm']:.1f}cm, A: {plant['area_cm2']:.0f}cm2"
        # White outline for visibility, then black text on top
        cv2.putText(annotated_image, text, (min_x, max(min_y - 10, 15)), cv2.FONT_HERSHEY_DUPLEX, 0.5, (255, 255, 255), 4)
        cv2.putText(annotated_image, text, (min_x, max(min_y - 10, 15)), cv2.FONT_HERSHEY_DUPLEX, 0.5, (0, 0, 0), 2)
    return annotated_image


def _generate_dummy_data():
    """Generates random data for testing when the model or camera is unavailable."""
    h = round(random.uniform(5.0, 10.0), 1)
    w = round(random.uniform(5.0, 10.0), 1)
    return [{
        'name': 'lettuce',
        'height_cm': h,
        'width_cm': w,
        'area_cm2': round(h * w * 0.7, 1),
        'confidence': round(random.uniform(0.7, 0.9), 2),
        'base64_image': 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII='  # 1x1 placeholder
    }]
