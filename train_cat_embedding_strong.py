"""
High-capacity cat embedding trainer with optional TPU acceleration.

This script trains a metric-learning backbone (default: ResNet-50, 2048-dim)
compatible with the CATalist recognition service. It supports:
  * GPU / CPU training via standard PyTorch.
  * TPU training via PyTorch/XLA when `torch_xla` is available.

Example (GPU):
    python train_cat_embedding_strong.py \
        --data-dir /data/cats \
        --output cat_resnet50.pth \
        --epochs 10 --batch-size 96

Example (TPU v3-8):
    python train_cat_embedding_strong.py \
        --data-dir gs://bucket/cats \
        --output cat_resnet50.pth \
        --epochs 12 --batch-size 224 \
        --image-size 256 --accumulation-steps 2 \
        --use-tpu --tpu-cores 8

Example (Notebook single cell):
    from train_cat_embedding_strong import quick_train
    quick_train(
        data_dir="/kaggle/input/cats",
        output_path="/kaggle/working/cat_resnet50.pth",
        backbone="resnet101",
        epochs=16,
        batch_size=224,
        image_size=256,
        accumulation_steps=2,
        use_tpu=True,
        tpu_cores=8,
    )
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
from dataclasses import dataclass
from typing import Dict, List, Tuple

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset, DistributedSampler
from torchvision import datasets, transforms
from torchvision.models import (
    ResNet50_Weights,
    ResNet101_Weights,
    ResNet152_Weights,
    resnet50,
    resnet101,
    resnet152,
)
from tqdm import tqdm

try:
    import torch_xla.core.xla_model as xm
    import torch_xla.distributed.parallel_loader as pl
    import torch_xla.distributed.xla_multiprocessing as xmp

    XLA_AVAILABLE = True
except ImportError:  # pragma: no cover - TPU optional
    xm = pl = xmp = None  # type: ignore
    XLA_AVAILABLE = False


def set_seed(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


class TripletDataset(Dataset):
    """Generates (anchor, positive, negative) tuples from an ImageFolder dataset."""

    def __init__(self, base_dataset: datasets.ImageFolder, min_images_per_class: int = 2):
        self.base = base_dataset
        self.targets = base_dataset.targets
        self.class_to_indices: Dict[int, List[int]] = {}
        for idx, label in enumerate(self.targets):
            self.class_to_indices.setdefault(label, []).append(idx)
        self.valid_classes = [
            c for c, idxs in self.class_to_indices.items() if len(idxs) >= min_images_per_class
        ]
        if not self.valid_classes:
            raise ValueError("Dataset must contain at least one class with >=2 images.")
        self.other_classes = {
            c: [o for o in self.class_to_indices.keys() if o != c and self.class_to_indices[o]]
            for c in self.class_to_indices.keys()
        }

    def __len__(self) -> int:
        return len(self.base)

    def _sample_positive(self, anchor_label: int, anchor_index: int) -> Tuple[torch.Tensor, int]:
        candidates = self.class_to_indices[anchor_label]
        if len(candidates) < 2:
            anchor_label = random.choice(self.valid_classes)
            anchor_index = random.choice(self.class_to_indices[anchor_label])
            anchor_img, _ = self.base[anchor_index]
            return anchor_img, anchor_label
        pos_index = anchor_index
        while pos_index == anchor_index:
            pos_index = random.choice(candidates)
        positive_img, _ = self.base[pos_index]
        return positive_img, anchor_label

    def __getitem__(self, index: int):
        anchor_img, anchor_label = self.base[index]

        if anchor_label not in self.valid_classes:
            anchor_label = random.choice(self.valid_classes)
            index = random.choice(self.class_to_indices[anchor_label])
            anchor_img, _ = self.base[index]

        positive_img, anchor_label = self._sample_positive(anchor_label, index)
        neg_label = random.choice(self.other_classes[anchor_label])
        neg_index = random.choice(self.class_to_indices[neg_label])
        negative_img, _ = self.base[neg_index]
        return anchor_img, positive_img, negative_img


class CatEmbeddingModel(nn.Module):
    """Backbone wrapper that exposes normalized embeddings."""

    def __init__(self, backbone_name: str = "resnet50", pretrained: bool = True):
        super().__init__()
        backbone_name = backbone_name.lower()
        self.backbone_name = backbone_name
        if backbone_name == "resnet50":
            weights = ResNet50_Weights.DEFAULT if pretrained else None
            self.backbone = resnet50(weights=weights)
            self.embedding_dim = 2048
        elif backbone_name == "resnet101":
            weights = ResNet101_Weights.DEFAULT if pretrained else None
            self.backbone = resnet101(weights=weights)
            self.embedding_dim = 2048
        elif backbone_name == "resnet152":
            weights = ResNet152_Weights.DEFAULT if pretrained else None
            self.backbone = resnet152(weights=weights)
            self.embedding_dim = 2048
        else:
            raise ValueError(f"Unsupported backbone '{backbone_name}'.")

        self.backbone.fc = nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.backbone(x)
        return nn.functional.normalize(x, p=2, dim=1)


@dataclass
class TrainConfig:
    data_dir: str
    output_path: str
    backbone: str
    epochs: int
    batch_size: int
    lr: float
    workers: int
    margin: float
    image_size: int
    crop_scale_min: float
    crop_scale_max: float
    accumulation_steps: int
    seed: int
    use_tpu: bool
    tpu_cores: int
    save_every: int
    metadata_path: str | None


def create_dataloader(
    dataset: Dataset,
    batch_size: int,
    workers: int,
    use_tpu: bool,
    drop_last: bool = False,
):
    if use_tpu:
        if not XLA_AVAILABLE:
            raise RuntimeError("torch_xla is required for TPU training.")
        sampler = DistributedSampler(
            dataset,
            num_replicas=xm.xrt_world_size(),
            rank=xm.get_ordinal(),
            shuffle=True,
            drop_last=drop_last,
        )
    else:
        sampler = None

    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=(sampler is None),
        sampler=sampler,
        num_workers=workers,
        pin_memory=not use_tpu,
        drop_last=drop_last,
    )
    return loader, sampler


def save_backbone_state(model: CatEmbeddingModel, path: str, use_tpu: bool) -> None:
    state = model.backbone.state_dict()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if use_tpu:
        xm.save(state, path)
    else:
        torch.save(state, path)


def train_single_process(cfg: TrainConfig) -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on device: {device}")

    base_dataset = datasets.ImageFolder(
        cfg.data_dir,
        transform=transforms.Compose(
            [
                transforms.RandomResizedCrop(
                    cfg.image_size,
                    scale=(cfg.crop_scale_min, cfg.crop_scale_max),
                ),
                transforms.RandomHorizontalFlip(),
                transforms.ColorJitter(brightness=0.25, contrast=0.25, saturation=0.25),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
                transforms.RandomErasing(p=0.2),
            ]
        ),
    )
    triplet_ds = TripletDataset(base_dataset)
    loader, _ = create_dataloader(triplet_ds, cfg.batch_size, cfg.workers, use_tpu=False)

    model = CatEmbeddingModel(cfg.backbone).to(device)
    criterion = nn.TripletMarginLoss(margin=cfg.margin, p=2)
    optimizer = optim.AdamW(model.parameters(), lr=cfg.lr)
    scaler = torch.cuda.amp.GradScaler(enabled=torch.cuda.is_available())

    accum = max(cfg.accumulation_steps, 1)
    for epoch in range(cfg.epochs):
        model.train()
        running = 0.0
        bar = tqdm(loader, desc=f"[GPU] Epoch {epoch+1}/{cfg.epochs}")
        optimizer.zero_grad(set_to_none=True)
        step_idx = 0
        for anchor, positive, negative in bar:
            step_idx += 1
            anchor = anchor.to(device, non_blocking=True)
            positive = positive.to(device, non_blocking=True)
            negative = negative.to(device, non_blocking=True)

            with torch.cuda.amp.autocast(enabled=torch.cuda.is_available()):
                emb_a = model(anchor)
                emb_p = model(positive)
                emb_n = model(negative)
                loss = criterion(emb_a, emb_p, emb_n)
                loss = loss / accum

            scaler.scale(loss).backward()
            if step_idx % accum == 0:
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad(set_to_none=True)

            running += loss.item() * accum
            bar.set_postfix(loss=f"{(loss.item() * accum):.4f}")

        if step_idx % accum != 0:
            scaler.step(optimizer)
            scaler.update()

        avg_loss = running / max(len(loader), 1)
        print(f"[GPU] Epoch {epoch+1} avg loss: {avg_loss:.4f}")
        if cfg.save_every and (epoch + 1) % cfg.save_every == 0:
            save_backbone_state(model, cfg.output_path, use_tpu=False)

    save_backbone_state(model, cfg.output_path, use_tpu=False)
    write_metadata(cfg, model.embedding_dim, avg_loss)
    print(f"Model saved to {cfg.output_path}")


def tpu_worker(index: int, cfg: TrainConfig) -> None:
    if not XLA_AVAILABLE:
        raise RuntimeError("torch_xla is required for TPU training.")

    set_seed(cfg.seed + index)
    device = xm.xla_device()
    if xm.is_master_ordinal():
        print("TPU cores:", xm.xrt_world_size())

    base_dataset = datasets.ImageFolder(
        cfg.data_dir,
        transform=transforms.Compose(
            [
                transforms.RandomResizedCrop(
                    cfg.image_size,
                    scale=(cfg.crop_scale_min, cfg.crop_scale_max),
                ),
                transforms.RandomHorizontalFlip(),
                transforms.ColorJitter(brightness=0.25, contrast=0.25, saturation=0.25),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
                transforms.RandomErasing(p=0.2),
            ]
        ),
    )
    triplet_ds = TripletDataset(base_dataset)
    loader, sampler = create_dataloader(
        triplet_ds,
        cfg.batch_size,
        cfg.workers,
        use_tpu=True,
        drop_last=True,
    )
    para_loader = pl.MpDeviceLoader(loader, device)

    model = CatEmbeddingModel(cfg.backbone).to(device)
    criterion = nn.TripletMarginLoss(margin=cfg.margin, p=2)
    optimizer = optim.AdamW(model.parameters(), lr=cfg.lr)

    accum = max(cfg.accumulation_steps, 1)
    for epoch in range(cfg.epochs):
        model.train()
        if sampler is not None:
            sampler.set_epoch(epoch)
        running = 0.0
        step_count = 0
        optimizer.zero_grad(set_to_none=True)
        for anchor, positive, negative in para_loader:
            emb_a = model(anchor)
            emb_p = model(positive)
            emb_n = model(negative)
            loss = criterion(emb_a, emb_p, emb_n)
            loss = loss / accum

            loss.backward()
            if (step_count + 1) % accum == 0:
                xm.optimizer_step(optimizer)
                xm.mark_step()
                optimizer.zero_grad(set_to_none=True)

            running += loss.item() * accum
            step_count += 1

        if step_count % accum != 0:
            xm.optimizer_step(optimizer)
            xm.mark_step()

        epoch_loss = running / max(step_count, 1)
        if xm.is_master_ordinal():
            print(f"[TPU] Epoch {epoch+1}/{cfg.epochs} avg loss: {epoch_loss:.4f}")
        if cfg.save_every and (epoch + 1) % cfg.save_every == 0 and xm.is_master_ordinal():
            save_backbone_state(model, cfg.output_path, use_tpu=True)

    if xm.is_master_ordinal():
        save_backbone_state(model, cfg.output_path, use_tpu=True)
        write_metadata(cfg, model.embedding_dim, epoch_loss)
        print(f"Model saved to {cfg.output_path}")


def write_metadata(cfg: TrainConfig, embedding_dim: int, final_loss: float) -> None:
    if not cfg.metadata_path:
        return
    meta = {
        "backbone": cfg.backbone,
        "embedding_dim": embedding_dim,
        "epochs": cfg.epochs,
        "batch_size": cfg.batch_size,
        "margin": cfg.margin,
        "learning_rate": cfg.lr,
        "final_loss": final_loss,
    }
    os.makedirs(os.path.dirname(cfg.metadata_path) or ".", exist_ok=True)
    with open(cfg.metadata_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    print(f"Metadata saved to {cfg.metadata_path}")


def parse_args() -> TrainConfig:
    parser = argparse.ArgumentParser(description="Train cat embedding model with ResNet-50+.")
    parser.add_argument("--data-dir", required=True, help="ImageFolder root (each cat id = class).")
    parser.add_argument("--output", required=True, help="Destination .pth for backbone state_dict.")
    parser.add_argument("--backbone", default="resnet50", choices=["resnet50", "resnet101", "resnet152"])
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--margin", type=float, default=0.9)
    parser.add_argument("--image-size", type=int, default=256, help="RandomResizedCrop output size.")
    parser.add_argument(
        "--crop-scale-min", type=float, default=0.7, help="Lower bound for RandomResizedCrop scale."
    )
    parser.add_argument(
        "--crop-scale-max", type=float, default=1.0, help="Upper bound for RandomResizedCrop scale."
    )
    parser.add_argument("--accumulation-steps", type=int, default=1, help="Gradient accumulation steps.")
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--use-tpu", action="store_true", help="Enable TPU + torch_xla workflow.")
    parser.add_argument("--tpu-cores", type=int, default=8, help="Number of TPU cores to use.")
    parser.add_argument("--save-every", type=int, default=0, help="Save checkpoint every N epochs.")
    parser.add_argument("--metadata", default=None, help="Optional JSON path to store training metadata.")
    args = parser.parse_args()

    return TrainConfig(
        data_dir=args.data_dir,
        output_path=args.output,
        backbone=args.backbone,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        workers=args.workers,
        margin=args.margin,
        image_size=args.image_size,
        crop_scale_min=args.crop_scale_min,
        crop_scale_max=args.crop_scale_max,
        accumulation_steps=args.accumulation_steps,
        seed=args.seed,
        use_tpu=args.use_tpu,
        tpu_cores=args.tpu_cores,
        save_every=args.save_every,
        metadata_path=args.metadata,
    )


def run_training(cfg: TrainConfig) -> None:
    set_seed(cfg.seed)
    if cfg.use_tpu:
        if not XLA_AVAILABLE:
            raise RuntimeError("torch_xla is not installed but --use-tpu was provided.")
        print("Launching TPU training (auto core count).")
        if cfg.tpu_cores:
            os.environ.setdefault("TPU_NUM_DEVICES", str(cfg.tpu_cores))
        xmp.spawn(
            tpu_worker,
            args=(cfg,),
            start_method="fork",
        )
    else:
        train_single_process(cfg)


def main() -> None:
    cfg = parse_args()
    run_training(cfg)


def quick_train(
    data_dir: str,
    output_path: str,
    backbone: str = "resnet50",
    epochs: int = 10,
    batch_size: int = 128,
    lr: float = 3e-4,
    workers: int = 8,
    margin: float = 0.9,
    image_size: int = 256,
    crop_scale_min: float = 0.7,
    crop_scale_max: float = 1.0,
    accumulation_steps: int = 1,
    seed: int = 1337,
    use_tpu: bool = False,
    tpu_cores: int = 8,
    save_every: int = 0,
    metadata_path: str | None = None,
) -> None:
    """
    Convenience wrapper so users can kick off training inside a single notebook cell,
    without touching argparse. The exported .pth is already in the correct format
    for CATalist (backbone-only state_dict).
    """
    cfg = TrainConfig(
        data_dir=data_dir,
        output_path=output_path,
        backbone=backbone,
        epochs=epochs,
        batch_size=batch_size,
        lr=lr,
        workers=workers,
        margin=margin,
        image_size=image_size,
        crop_scale_min=crop_scale_min,
        crop_scale_max=crop_scale_max,
        accumulation_steps=accumulation_steps,
        seed=seed,
        use_tpu=use_tpu,
        tpu_cores=tpu_cores,
        save_every=save_every,
        metadata_path=metadata_path,
    )
    run_training(cfg)


if __name__ == "__main__":
    main()

