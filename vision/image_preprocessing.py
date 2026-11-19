import cv2
import numpy as np
import os
from glob import glob
from tqdm import tqdm

# --- CONFIGURATION ---
INPUT_DIR = 'from_lab_labeled/images'   # images exported from Roboflow
OUTPUT_DIR = 'processed_images'
TARGET_SIZE = None   # KEEP None for YOLO (recommended)
# ---------------------

def preprocess_image(image_path, target_size=None):
    """
    Minimal, YOLO-safe preprocessing.
    - Loads image
    - Optional resize ONLY if target_size is provided
    """

    img = cv2.imread(image_path)

    if img is None:
        print(f"⚠️ Could not load image: {image_path}")
        return None

    # OPTIONAL resize (only if explicitly requested)
    if target_size is not None:
        img = cv2.resize(img, target_size, interpolation=cv2.INTER_LINEAR)

    return img


# Create output directory
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Collect images
image_files = (
    glob(os.path.join(INPUT_DIR, '*.jpg')) +
    glob(os.path.join(INPUT_DIR, '*.jpeg')) +
    glob(os.path.join(INPUT_DIR, '*.png'))
)

print(f"Found {len(image_files)} images")

processed_count = 0
for image_path in tqdm(image_files, desc="Preprocessing Images"):
    filename = os.path.basename(image_path)

    processed_img = preprocess_image(image_path, TARGET_SIZE)

    if processed_img is not None:
        output_path = os.path.join(OUTPUT_DIR, filename)
        cv2.imwrite(output_path, processed_img)
        processed_count += 1

print(f"\n✅ Done. {processed_count} images saved to '{OUTPUT_DIR}'")
