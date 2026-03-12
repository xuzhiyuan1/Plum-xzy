import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import numpy as np
import os
import glob
from pathlib import Path
from tqdm import tqdm

# ==========================================
# 1. 路径与环境设置
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))
sys_path_bocd = os.path.join(current_dir, "..")
import sys
sys.path.append(sys_path_bocd)

from model import BandwidthEncoder
from bocd.bocd import infer_run_lengths

# ==========================================
# 2. 辅助函数：生成因果掩码
# ==========================================
def generate_square_subsequent_mask(sz):
    mask = (torch.triu(torch.ones(sz, sz)) == 1).transpose(0, 1)
    mask = mask.float().masked_fill(mask == 0, float('-inf')).masked_fill(mask == 1, float(0.0))
    return mask

# ==========================================
# 3. 真实数据 Dataset (带归一化)
# ==========================================
class RealTraceDataset(Dataset):
    def __init__(self, data_dir, seq_len=1000):
        self.seq_len = seq_len
        self.files = sorted(glob.glob(os.path.join(data_dir, "*.npy")))
        
        # 【关键修改】归一化因子
        # 真实数据通常在 0-15Mbps 左右，除以 20 可以将其映射到 0-1 之间
        # 这必须与 pre_train 中的处理保持一致
        self.scale_factor = 20.0
        
        if len(self.files) == 0:
            print(f"Warning: No .npy files found in {data_dir}.")
        else:
            print(f"Found {len(self.files)} real traces for fine-tuning.")

    def __len__(self):
        return len(self.files)

    def __getitem__(self, idx):
        # 加载原始数据
        raw_trace = np.load(self.files[idx]).flatten()
        
        # 随机切片
        if len(raw_trace) > self.seq_len:
            start_idx = np.random.randint(0, len(raw_trace) - self.seq_len)
            obs_np = raw_trace[start_idx : start_idx + self.seq_len]
        else:
            padding = self.seq_len - len(raw_trace)
            obs_np = np.pad(raw_trace, (0, padding), 'constant', constant_values=0)

        # BOCD (使用原始数据算 RL 比较准)
        try:
            inferred_rl = infer_run_lengths(obs_np)
        except Exception:
            inferred_rl = np.zeros_like(obs_np)
        
        # 【关键修改】归一化数据喂给模型
        norm_obs = obs_np / self.scale_factor
        
        obs_tensor = torch.tensor(norm_obs, dtype=torch.float32).unsqueeze(-1)
        rl_tensor = torch.tensor(inferred_rl, dtype=torch.long)
        
        # Target 是归一化后的数据（模型输出也是归一化的）
        target_bw = obs_tensor.clone()
        
        return obs_tensor, rl_tensor, target_bw

# ==========================================
# 4. Fine-tuning 流程 (自回归模式)
# ==========================================
def fine_tune():
    BATCH_SIZE = 16
    LR = 1e-5
    EPOCHS = 10
    DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    project_root = Path(current_dir).parent.parent
    real_trace_dir = project_root / "data" / "real_trace" / "train_data"
    pretrained_path = os.path.join(current_dir, "encoder_epoch_20.pth")
    
    if not os.path.exists(real_trace_dir): return
    
    train_set = RealTraceDataset(str(real_trace_dir))
    if len(train_set) == 0: return
    
    train_loader = DataLoader(train_set, batch_size=BATCH_SIZE, shuffle=True)
    
    model = BandwidthEncoder(input_dim=1, d_model=64, nhead=4, num_layers=3).to(DEVICE)
    
    if os.path.exists(pretrained_path):
        print(f"Loading pretrained weights from {pretrained_path}...")
        model.load_state_dict(torch.load(pretrained_path, map_location=DEVICE))
    else:
        print("Warning: Pretrained model not found, training from scratch.")
    
    optimizer = optim.Adam(model.parameters(), lr=LR)
    criterion_mse = nn.MSELoss()
    
    print(f"Start Prediction Fine-tuning on {DEVICE}...")
    
    model.train()
    for epoch in range(EPOCHS):
        total_loss = 0
        loop = tqdm(train_loader, desc=f"Fine-tune Epoch {epoch+1}/{EPOCHS}")
        
        for obs_full, rl_full, target_full in loop:
            obs_full = obs_full.to(DEVICE)
            rl_full = rl_full.to(DEVICE)
            
            # === 错位预测逻辑 ===
            # Input:  0 -> T-2
            # Target: 1 -> T-1 (预测下一步)
            
            inp_obs = obs_full[:, :-1, :]
            inp_rl  = rl_full[:, :-1]
            tgt_bw  = obs_full[:, 1:, :] # 真实数据的 Target 就是它自己下一步的值
            
            # 生成掩码
            seq_len = inp_obs.size(1)
            src_mask = generate_square_subsequent_mask(seq_len).to(DEVICE)
            
            optimizer.zero_grad()
            
            # Forward
            outputs = model(inp_obs, inp_rl, src_mask=src_mask)
            
            # Loss
            loss_recon = criterion_mse(outputs['recon_bw'], tgt_bw)
            
            # 辅助 Loss (RL一致性)
            if 'pred_rl' in outputs:
                tgt_rl = rl_full[:, 1:].unsqueeze(-1).float()
                loss_rl = criterion_mse(outputs['pred_rl'], tgt_rl)
                loss = loss_recon + 0.1 * loss_rl
            else:
                loss = loss_recon
            
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
            loop.set_postfix(loss=loss.item())

        if (epoch + 1) % 5 == 0:    
            save_path = os.path.join(current_dir, f"finetuned_epoch_{epoch+1}.pth")
            torch.save(model.state_dict(), save_path)
            print(f"Checkpoint saved: {save_path}")

if __name__ == "__main__":
    fine_tune()