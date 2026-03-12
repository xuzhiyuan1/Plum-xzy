import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import numpy as np
import os
import glob
from pathlib import Path
from tqdm import tqdm

# 引入最新版的模型
from model import BandwidthEncoder

# ==========================================
# 0. 辅助函数：生成因果掩码
# ==========================================
def generate_square_subsequent_mask(sz):
    """
    生成上三角掩码，确保 t 时刻只能看到 0...t 的数据，看不到 t+1...
    """
    mask = (torch.triu(torch.ones(sz, sz)) == 1).transpose(0, 1)
    mask = mask.float().masked_fill(mask == 0, float('-inf')).masked_fill(mask == 1, float(0.0))
    return mask

# ==========================================
# 1. 数据集定义
# ==========================================
class WifiDataset(Dataset):
    def __init__(self, data_dir):
        self.data_paths = sorted(glob.glob(os.path.join(data_dir, "*.pt")))
        if len(self.data_paths) == 0:
            raise ValueError(f"No .pt files found in {data_dir}")
        print(f"Found {len(self.data_paths)} files in {data_dir}")
        
        # 归一化因子 (假设合成数据最大值约为 20-50 Mbps，这里统一除以 20)
        # 这有助于和真实数据的 Fine-tune 保持一致
        self.scale_factor = 20.0

    def __len__(self):
        return len(self.data_paths)

    def __getitem__(self, idx):
        data = torch.load(self.data_paths[idx])
        
        # 取出数据
        # 注意：这里我们对观测值进行归一化
        obs = data['obs_trace'].float().unsqueeze(-1) / self.scale_factor
        true_bw = data['true_hidden'].float().unsqueeze(-1) / self.scale_factor
        
        # 突变点标志和RunLength不需要归一化
        cp_flags = data['cp_flags'].float().unsqueeze(-1)
        run_lens = data['run_lengths'].long()
        
        return obs, true_bw, cp_flags, run_lens

# ==========================================
# 2. 训练流程
# ==========================================
def train():
    # 配置
    BATCH_SIZE = 32
    LR = 1e-3
    EPOCHS = 20
    DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # 路径自动定位
    current_dir = Path(__file__).parent.absolute()
    project_root = current_dir.parent.parent.parent 
    train_dir = project_root / "data/pre_train_data"
    
    if not train_dir.exists():
        train_dir = current_dir / "../../data/pre_train_data"
        if not train_dir.exists():
            print("Please check your data path in train_encoder.py")
            return

    # 准备 Dataloader
    train_set = WifiDataset(str(train_dir))
    train_loader = DataLoader(train_set, batch_size=BATCH_SIZE, shuffle=True)
    
    # 初始化模型
    model = BandwidthEncoder(input_dim=1, d_model=64, num_layers=3).to(DEVICE)
    optimizer = optim.Adam(model.parameters(), lr=LR)
    
    # Loss 定义
    pos_weight = torch.tensor([10.0]).to(DEVICE) 
    criterion_cp = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    criterion_mse = nn.MSELoss()
    
    print(f"Start Pre-Training on {DEVICE}...")
    
    for epoch in range(EPOCHS):
        model.train()
        total_loss = 0
        
        loop = tqdm(train_loader, desc=f"Epoch {epoch+1}/{EPOCHS}")
        for obs, true_bw, cp_flags, run_lens in loop:
            obs = obs.to(DEVICE)
            true_bw = true_bw.to(DEVICE)
            cp_flags = cp_flags.to(DEVICE)
            run_lens = run_lens.to(DEVICE)
            
            # === 关键修改：错位预测 (Shifted Prediction) ===
            # Input:  Time 0 -> T-2
            # Target: Time 1 -> T-1
            
            inp_obs = obs[:, :-1, :]
            inp_rl  = run_lens[:, :-1]
            
            # 预测目标：可以是下一时刻的观测值(obs)，也可以是下一时刻的真值(true_bw)
            # 在预训练阶段，预测真值(true_bw)有助于模型学习物理规律
            tgt_bw  = true_bw[:, 1:, :] 
            tgt_cp  = cp_flags[:, 1:, :]
            tgt_rl  = run_lens[:, 1:].unsqueeze(-1).float()
            
            # 生成掩码
            seq_len = inp_obs.size(1)
            src_mask = generate_square_subsequent_mask(seq_len).to(DEVICE)
            
            optimizer.zero_grad()
            
            # 传入 mask
            outputs = model(inp_obs, inp_rl, src_mask=src_mask)
            
            # 计算 Loss (对比错位后的目标)
            loss_cp = criterion_cp(outputs['cp_logits'], tgt_cp)
            loss_recon = criterion_mse(outputs['recon_bw'], tgt_bw)
            
            # 如果模型有 pred_rl 输出
            if 'pred_rl' in outputs:
                loss_rl = criterion_mse(outputs['pred_rl'], tgt_rl)
                loss = 10.0 * loss_cp + 1.0 * loss_recon + 0.01 * loss_rl
            else:
                loss = 10.0 * loss_cp + 1.0 * loss_recon
            
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
            loop.set_postfix(loss=loss.item())
            
        if (epoch + 1) % 5 == 0:
            save_path = os.path.join(current_dir, f"encoder_epoch_{epoch+1}.pth")
            torch.save(model.state_dict(), save_path)
            print(f"Saved: {save_path}")

if __name__ == "__main__":
    train()