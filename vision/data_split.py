import os
import random
import shutil

# =====================================================
# Configuration
# =====================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

IMAGES_DIR = os.path.join(BASE_DIR, "processed_images")
LABELS_DIR = os.path.join(BASE_DIR, "from_lab_labeled", "labels")  # YOLO-format labels from Roboflow

OUTPUT_DIR = os.path.join(BASE_DIR, "dataset_split")
OUTPUT_IMAGES = os.path.join(OUTPUT_DIR, "images")
OUTPUT_LABELS = os.path.join(OUTPUT_DIR, "labels")

SPLIT_RATIO = {
    'train': 0.70,
    'val': 0.15,
    'test': 0.15
}

IMG_EXT = [".jpg", ".jpeg", ".png"]

# =====================================================
# Create output folder structure
# =====================================================
for split in ["train", "val", "test"]:
    os.makedirs(os.path.join(OUTPUT_IMAGES, split), exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_LABELS, split), exist_ok=True)

# =====================================================
# Collect images
# =====================================================
images = [
    f for f in os.listdir(IMAGES_DIR)
    if os.path.splitext(f)[1].lower() in IMG_EXT
]

random.seed(42)
random.shuffle(images)

total = len(images)

train_end = int(total * SPLIT_RATIO['train'])
val_end = train_end + int(total * SPLIT_RATIO['val'])

splits = {
    "train": images[:train_end],
    "val": images[train_end:val_end],
    "test": images[val_end:]
}

# =====================================================
# Copy images + labels
# =====================================================
for split, files in splits.items():
    for img in files:
        src_img = os.path.join(IMAGES_DIR, img)
        dst_img = os.path.join(OUTPUT_IMAGES, split, img)

        label_name = os.path.splitext(img)[0] + ".txt"
        src_label = os.path.join(LABELS_DIR, label_name)
        dst_label = os.path.join(OUTPUT_LABELS, split, label_name)

        if not os.path.exists(src_label):
            print(f"⚠️ Skipping {img} (no label)")
            continue

        shutil.copy(src_img, dst_img)
        shutil.copy(src_label, dst_label)

print("\n🎉 Dataset split completed successfully!")
print(f"Total images used: {sum(len(v) for v in splits.values())}")
print(f"Train: {len(splits['train'])}, Val: {len(splits['val'])}, Test: {len(splits['test'])}")
