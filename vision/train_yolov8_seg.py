from ultralytics import YOLO
import torch
import datetime
import os
from pathlib import Path
from multiprocessing import freeze_support

# ============================================================
# CONFIGURATION
# ============================================================
MODEL_PATH = "yolov8s-seg.pt"
DATA_YAML  = "data.yaml"

IMAGE_SIZE = 960
BATCH      = 8
EPOCHS     = 300

LR           = 0.0008
WEIGHT_DECAY = 0.0005
PATIENCE     = 30
SEED         = 42

# ============================================================
# AUGMENTATION SETTINGS (Plant-optimized, segmentation-safe)
# ============================================================
AUGMENTATIONS = dict(
    degrees=5,
    translate=0.10,
    scale=0.30,
    shear=0.0,
    perspective=0.0,

    hsv_h=0.015,
    hsv_s=0.60,
    hsv_v=0.40,

    flipud=0.3,
    fliplr=0.5,

    mosaic=0.0,
    mixup=0.0,
    copy_paste=0.0,
)

# ============================================================
# EXPERIMENT NAME
# ============================================================
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
EXP_NAME = f"lettuce_seg_{timestamp}"

# ============================================================
# DATASET UTILS
# ============================================================
def count_images(path):
    return len(list(Path(path).glob("*.*")))

# ============================================================
# MAIN
# ============================================================
def main():

    print("\n================ ENVIRONMENT =================")
    print("PyTorch:", torch.__version__)
    print("CUDA available:", torch.cuda.is_available())
    print("Using device:", "GPU" if torch.cuda.is_available() else "CPU")

    torch.manual_seed(SEED)

    # ========================================================
    # DATASET SUMMARY
    # ========================================================
    train_images = count_images("dataset_split/images/train")
    val_images   = count_images("dataset_split/images/val")
    test_images  = count_images("dataset_split/images/test")

    print("\n================ DATASET =====================")
    print(f"Train images: {train_images}")
    print(f"Val images:   {val_images}")
    print(f"Test images:  {test_images}")

    effective_exposures = train_images * EPOCHS
    print("\nEffective training image exposures:")
    print(f"{train_images} images × {EPOCHS} epochs = {effective_exposures:,}")

    # ========================================================
    # LOAD MODEL
    # ========================================================
    model = YOLO(MODEL_PATH)

    # ========================================================
    # TRAIN
    # ========================================================
    print("\n================ TRAINING ====================")
    results = model.train(
        data=DATA_YAML,
        epochs=EPOCHS,
        imgsz=IMAGE_SIZE,
        batch=BATCH,
        device=0 if torch.cuda.is_available() else "cpu",
        seed=SEED,

        optimizer="AdamW",
        lr0=LR,
        weight_decay=WEIGHT_DECAY,
        patience=PATIENCE,

        augment=True,
        **AUGMENTATIONS,

        workers=8,
        verbose=True,

        project="runs/plant_seg",
        name=EXP_NAME,
        pretrained=True,
    )

    # ========================================================
    # VALIDATION
    # ========================================================
    print("\n================ VALIDATION ==================")
    metrics = model.val(
        data=DATA_YAML,
        imgsz=IMAGE_SIZE,
        device=0 if torch.cuda.is_available() else "cpu",
    )

    print(metrics)

    # ========================================================
    # SAMPLE PREDICTIONS
    # ========================================================
    print("\n================ PREDICTIONS =================")
    os.makedirs("predictions", exist_ok=True)

    model.predict(
        source="dataset_split/images/val",
        imgsz=IMAGE_SIZE,
        conf=0.30,
        save=True,
        project="predictions",
        name=f"{EXP_NAME}_val"
    )

    print("\n================ DONE ========================")
    print(f"Training results: runs/plant_seg/{EXP_NAME}")
    print(f"Predictions: predictions/{EXP_NAME}_val")

# ============================================================
# ENTRY POINT (Windows safe)
# ============================================================
if __name__ == "__main__":
    freeze_support()
    main()
