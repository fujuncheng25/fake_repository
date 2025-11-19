import os
import random
import shutil
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import datasets, transforms
from torchvision.models import resnet18, ResNet18_Weights
from tqdm import tqdm

# 1) 设备
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("Using device:", device)

# 2) 预处理
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406],
                         [0.229, 0.224, 0.225]),
])

# 3) 数据集（ImageFolder: 每个猫个体一个子目录）
data_dir = "/kaggle/input/cat-individuals/cat_individuals_dataset"  # 改成你的路径
dataset = datasets.ImageFolder(data_dir, transform=transform)
num_cats = len(dataset.classes)
print("猫个体数量:", num_cats)

# 4) 模型：ResNet18 + Identity() -> 512维嵌入（与后端完全一致）
class CatEmbeddingModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.backbone = resnet18(weights=ResNet18_Weights.DEFAULT)
        self.backbone.fc = nn.Identity()  # 直接输出 [B, 512]

    def forward(self, x):
        x = self.backbone(x)              # [B, 512]
        return nn.functional.normalize(x, p=2, dim=1)

model = CatEmbeddingModel().to(device)

# 5) Triplet 采样器（同类正样，本类外负样）
class TripletDataset(Dataset):
    def __init__(self, base_dataset):
        self.ds = base_dataset
        self.targets = base_dataset.targets
        self.class_to_indices = {}
        for idx, y in enumerate(self.targets):
            self.class_to_indices.setdefault(y, []).append(idx)
        # 过滤只有1张图的类，避免取正样失败
        self.valid_classes = [c for c, idxs in self.class_to_indices.items() if len(idxs) >= 2]
        self.other_classes = {}
        all_classes = list(self.class_to_indices.keys())
        for c in all_classes:
            self.other_classes[c] = [x for x in all_classes if x != c and len(self.class_to_indices[x]) > 0]

    def __len__(self):
        return len(self.ds)

    def __getitem__(self, index):
        anchor_img, anchor_label = self.ds[index]
        # 选正样（同类不同图）
        pos_choices = self.class_to_indices.get(anchor_label, [])
        if len(pos_choices) < 2:
            # 若该类不足两张，随机换一个有效类作为锚点
            anchor_label = random.choice(self.valid_classes)
            index = random.choice(self.class_to_indices[anchor_label])
            anchor_img, _ = self.ds[index]
            pos_choices = self.class_to_indices[anchor_label]
        pos_index = index
        while pos_index == index:
            pos_index = random.choice(pos_choices)
        positive_img, _ = self.ds[pos_index]
        # 负样（不同类）
        neg_label = random.choice(self.other_classes[anchor_label])
        neg_index = random.choice(self.class_to_indices[neg_label])
        negative_img, _ = self.ds[neg_index]
        return anchor_img, positive_img, negative_img

triplet_ds = TripletDataset(dataset)
loader = DataLoader(triplet_ds, batch_size=64, shuffle=True, num_workers=4, pin_memory=True)

# 6) 损失与优化
criterion = nn.TripletMarginLoss(margin=1.0, p=2)
optimizer = optim.Adam(model.parameters(), lr=5e-4)
scaler = torch.cuda.amp.GradScaler(enabled=torch.cuda.is_available())

# 7) 训练
epochs = 5
for epoch in range(epochs):
    model.train()
    running = 0.0
    bar = tqdm(loader, desc=f"Epoch {epoch+1}/{epochs}", leave=False)
    for anchor, positive, negative in bar:
        anchor = anchor.to(device, non_blocking=True)
        positive = positive.to(device, non_blocking=True)
        negative = negative.to(device, non_blocking=True)

        optimizer.zero_grad(set_to_none=True)
        with torch.cuda.amp.autocast(enabled=torch.cuda.is_available()):
            emb_a = model(anchor)
            emb_p = model(positive)
            emb_n = model(negative)
            loss = criterion(emb_a, emb_p, emb_n)

        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()

        running += loss.item()
        bar.set_postfix(loss=f"{loss.item():.4f}")

    print(f"Epoch {epoch+1}, Avg Loss: {running/len(loader):.4f}")

# 8) 保存（关键修复：只保存 backbone 的 state_dict，键名与后端完全匹配）
save_name = "cat_resnet18.pth"
kaggle_path = "/kaggle/working/cat_resnet18.pth"

# ⚠️ 重要：后端期望直接是 ResNet18 的 state_dict，不是 CatEmbeddingModel 的
# 所以只保存 backbone 的权重，去掉 "backbone." 前缀
print("正在保存模型...")
backbone_state = model.backbone.state_dict()
torch.save(backbone_state, kaggle_path)
print(f"✅ 模型已保存到: {kaggle_path}")

# 同时保存到当前目录（可选，用于本地测试）
try:
    torch.save(backbone_state, save_name)
    print(f"✅ 同时保存到: {save_name}")
except Exception as e:
    print(f"⚠️  本地保存失败（不影响 Kaggle 使用）: {e}")

print(f"\n🎉 模型保存完成！可以直接从 Kaggle 下载: {kaggle_path}")

