import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import numpy as np
import os
import glob
from pathlib import Path
from tqdm import tqdm
import sys

# ==========================================
# 1. 路径修复 (适配 model/baseline/lstm 结构)
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))

# 1. 定位到 'model' 目录 (往上跳两级: lstm -> baseline -> model)
# 这样才能找到 model 目录下的 bocd 文件夹
model_root = os.path.abspath(os.path.join(current_dir, "../.."))
sys.path.append(model_root)

# 2. 定位到 'bocd' 目录并加入 path (双重保险)
bocd_dir = os.path.join(model_root, "bocd")
sys.path.append(bocd_dir)

try:
    # 引入同目录下的 LSTM 模型
    from model_lstm import LSTMEncoder 
    # 引入 BOCD
    try:
        from bocd import infer_run_lengths
    except ImportError:
        from bocd.bocd import infer_run_lengths
except ImportError as e:
    print(f"Import Error details: {e}")
    print(f"Current sys.path: {sys.path}")
    raise e

# ==========================================
# 2. 真实数据 Dataset (完全复用 Transformer 版)
# ==========================================
class RealTraceDataset(Dataset):
    def __init__(self, data_dir, seq_len=1000):
        self.seq_len = seq_len
        self.files = sorted(glob.glob(os.path.join(data_dir, "*.npy")))
        
        # 归一化因子 (与 pre_train_lstm.py 保持一致)
        self.scale_factor = 20.0
        
        if len(self.files) == 0:
            print(f"Warning: No .npy files found in {data_dir}.")
        else:
            print(f"Found {len(self.files)} real traces for LSTM fine-tuning.")

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

        # BOCD
        try:
            inferred_rl = infer_run_lengths(obs_np)
        except Exception:
            inferred_rl = np.zeros_like(obs_np)
        
        # 归一化
        norm_obs = obs_np / self.scale_factor
        
        obs_tensor = torch.tensor(norm_obs, dtype=torch.float32).unsqueeze(-1)
        rl_tensor = torch.tensor(inferred_rl, dtype=torch.long)
        
        # Target 也是归一化的
        target_bw = obs_tensor.clone()
        
        return obs_tensor, rl_tensor, target_bw

# ==========================================
# 3. Fine-tuning 流程 (LSTM 版)
# ==========================================
def fine_tune():
    BATCH_SIZE = 16
    LR = 1e-5 # 微调使用小学习率
    EPOCHS = 10
    DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # 【路径修复】项目根目录需要往上跳 3 级 (lstm -> baseline -> model -> ProjectRoot)
    project_root = Path(current_dir).parent.parent.parent
    real_trace_dir = project_root / "data" / "real_trace" / "train_data"
    
    # 预训练模型路径
    pretrained_path = os.path.join(current_dir, "lstm_epoch_20.pth")
    
    if not os.path.exists(real_trace_dir): 
        print(f"Error: Data dir not found: {real_trace_dir}")
        return
    
    train_set = RealTraceDataset(str(real_trace_dir))
    if len(train_set) == 0: return
    
    train_loader = DataLoader(train_set, batch_size=BATCH_SIZE, shuffle=True)
    
    # 初始化 LSTM 模型
    # 参数必须与 pre_train_lstm.py 一致
    model = LSTMEncoder(input_dim=1, d_model=64, hidden_size=128, num_layers=2).to(DEVICE)
    
    if os.path.exists(pretrained_path):
        print(f"Loading pretrained LSTM weights from {pretrained_path}...")
        model.load_state_dict(torch.load(pretrained_path, map_location=DEVICE))
    else:
        print("Warning: Pretrained LSTM model not found, training from scratch.")
    
    optimizer = optim.Adam(model.parameters(), lr=LR)
    criterion_mse = nn.MSELoss()
    
    print(f"Start Prediction Fine-tuning (LSTM) on {DEVICE}...")
    
    model.train()
    for epoch in range(EPOCHS):
        total_loss = 0
        loop = tqdm(train_loader, desc=f"Fine-tune Epoch {epoch+1}/{EPOCHS}")
        
        for obs_full, rl_full, target_full in loop:
            obs_full = obs_full.to(DEVICE)
            rl_full = rl_full.to(DEVICE)
            
            # === 错位预测逻辑 (Shifted Prediction) ===
            # LSTM 不需要 Mask，但依然需要错位数据来训练"预测"能力
            
            # Input:  0 -> T-2
            inp_obs = obs_full[:, :-1, :]
            inp_rl  = rl_full[:, :-1]
            
            # Target: 1 -> T-1 (预测下一步)
            tgt_bw  = obs_full[:, 1:, :] 
            
            optimizer.zero_grad()
            
            # Forward
            outputs = model(inp_obs, inp_rl)
            
            # Loss
            loss_recon = criterion_mse(outputs['recon_bw'], tgt_bw)
            
            # 辅助 Loss
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
        
        # 保存文件名区分
        save_path = os.path.join(current_dir, f"lstm_finetuned_epoch_{epoch+1}.pth")
        torch.save(model.state_dict(), save_path)
        print(f"Checkpoint saved: {save_path}")

if __name__ == "__main__":
    fine_tune()