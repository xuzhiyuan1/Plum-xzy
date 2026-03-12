import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import numpy as np
import os
import glob
from pathlib import Path
from tqdm import tqdm

# === 引入 LSTM 模型 ===
from model_lstm import LSTMEncoder

# ==========================================
# 1. 数据集定义 (加入归一化)
# ==========================================
class WifiDataset(Dataset):
    def __init__(self, data_dir):
        self.data_paths = sorted(glob.glob(os.path.join(data_dir, "*.pt")))
        if len(self.data_paths) == 0:
            raise ValueError(f"No .pt files found in {data_dir}")
        print(f"Found {len(self.data_paths)} files in {data_dir}")
        
        # 【关键修改】归一化因子
        # 必须与 Transformer 版本保持一致，解决预测值偏大的问题
        self.scale_factor = 20.0

    def __len__(self):
        return len(self.data_paths)

    def __getitem__(self, idx):
        data = torch.load(self.data_paths[idx])
        
        # 【关键修改】归一化处理
        obs = data['obs_trace'].float().unsqueeze(-1) / self.scale_factor
        true_bw = data['true_hidden'].float().unsqueeze(-1) / self.scale_factor
        
        cp_flags = data['cp_flags'].float().unsqueeze(-1)
        run_lens = data['run_lengths'].long()
        
        return obs, true_bw, cp_flags, run_lens

# ==========================================
# 2. 训练流程 (加入错位预测)
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
            print(f"Error: Data path not found: {train_dir}")
            return

    # 准备 Dataloader
    train_set = WifiDataset(str(train_dir))
    train_loader = DataLoader(train_set, batch_size=BATCH_SIZE, shuffle=True)
    
    # === 初始化 LSTM 模型 ===
    model = LSTMEncoder(input_dim=1, d_model=64, hidden_size=128, num_layers=2).to(DEVICE)
    
    optimizer = optim.Adam(model.parameters(), lr=LR)
    
    # Loss 定义
    pos_weight = torch.tensor([10.0]).to(DEVICE) 
    criterion_cp = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    criterion_mse = nn.MSELoss()
    
    print(f"Start Prediction Pre-Training (LSTM) on {DEVICE}...")
    
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
            # LSTM 不需要 Mask，但需要数据错位
            
            # Input:  Time 0 -> T-2
            inp_obs = obs[:, :-1, :]
            inp_rl  = run_lens[:, :-1]
            
            # Target: Time 1 -> T-1 (预测下一时刻)
            tgt_bw  = true_bw[:, 1:, :]
            tgt_cp  = cp_flags[:, 1:, :]
            tgt_rl  = run_lens[:, 1:].unsqueeze(-1).float()
            
            optimizer.zero_grad()
            
            # Forward
            # LSTM 输出的 output 长度将与 input 一致 (T-1)
            # output[t] 是基于 inp[0...t] 计算的，对应 target[t] (即物理上的 t+1)
            outputs = model(inp_obs, inp_rl)
            
            # Loss Calculation (对比错位后的 Target)
            loss_cp = criterion_cp(outputs['cp_logits'], tgt_cp)
            loss_recon = criterion_mse(outputs['recon_bw'], tgt_bw)
            loss_rl = criterion_mse(outputs['pred_rl'], tgt_rl)
            
            loss = 10.0 * loss_cp + 1.0 * loss_recon + 0.01 * loss_rl
            
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
            loop.set_postfix(loss=loss.item())
            
        # 保存模型
        if (epoch + 1) % 5 == 0:
            save_path = os.path.join(current_dir, f"lstm_epoch_{epoch+1}.pth")
            torch.save(model.state_dict(), save_path)
            print(f"Saved: {save_path}")

if __name__ == "__main__":
    train()