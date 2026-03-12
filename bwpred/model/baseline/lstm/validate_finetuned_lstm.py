import sys
import os
import glob
import re
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from tqdm import tqdm

# ==========================================
# 1. 路径修复 (适配 model/baseline/lstm 结构)
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))

# 定位到 'model' 目录 (往上跳两级: lstm -> baseline -> model)
model_root = os.path.abspath(os.path.join(current_dir, "../.."))
# 定位到 'bocd' 目录
bocd_dir = os.path.join(model_root, "bocd")

# 将路径加入 sys.path
sys.path.append(model_root)
sys.path.append(bocd_dir)

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

try:
    # 1. 导入同目录下的 LSTM 模块
    from model_lstm import LSTMEncoder 
    
    # 2. 导入 BOCD
    try:
        from bocd import infer_run_lengths
    except ImportError:
        from bocd.bocd import infer_run_lengths
except ImportError as e:
    print(f"Import Error details: {e}")
    print(f"Current sys.path: {sys.path}")
    raise e

# ==========================================
# 2. 真实数据验证集
# ==========================================
class RealValidDataset(Dataset):
    def __init__(self, data_dir, seq_len=1000):
        self.seq_len = seq_len
        self.files = sorted(glob.glob(os.path.join(data_dir, "*.npy")))
        self.scale_factor = 20.0 # 归一化因子
        
        if len(self.files) == 0:
            print(f"Warning: No .npy files found in {data_dir}")
        else:
            print(f"Found {len(self.files)} real traces for validation.")

    def __len__(self):
        return len(self.files)

    def __getitem__(self, idx):
        raw_trace = np.load(self.files[idx]).flatten()
        
        if len(raw_trace) > self.seq_len:
            obs_np = raw_trace[:self.seq_len]
        else:
            padding = self.seq_len - len(raw_trace)
            obs_np = np.pad(raw_trace, (0, padding), 'constant')

        try:
            inferred_rl = infer_run_lengths(obs_np)
        except:
            inferred_rl = np.zeros_like(obs_np)
        
        obs_norm = obs_np / self.scale_factor
        
        obs_tensor = torch.tensor(obs_norm, dtype=torch.float32).unsqueeze(-1)
        rl_tensor = torch.tensor(inferred_rl, dtype=torch.long)
        raw_tensor = torch.tensor(obs_np, dtype=torch.float32).unsqueeze(-1)
        
        return obs_tensor, rl_tensor, raw_tensor

# ==========================================
# 3. 验证流程 (LSTM版 - 支持 Macro Average)
# ==========================================
def validate_finetuned_lstm():
    DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    SCALE_FACTOR = 20.0
    
    # === A. 路径配置 ===
    # data 目录在 model 的上一级
    project_root = os.path.abspath(os.path.join(model_root, "../"))
    valid_data_dir = os.path.join(project_root, "data/real_trace/valid_data")
    
    # === 创建结果保存目录 ===
    output_dir = os.path.join(current_dir, "validate_finetuned_lstm_result")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    print(f"Saving all visualization results to: {output_dir}")
    
    # === B. 寻找 LSTM 微调模型 ===
    search_patterns = [
        os.path.join(current_dir, "lstm_finetuned_epoch_*.pth")
    ]
    model_files = []
    for p in search_patterns:
        model_files.extend(glob.glob(p))
        
    if not model_files:
        print("Error: No 'lstm_finetuned_epoch_*.pth' found! Please run fine_tune_lstm.py first.")
        return

    def extract_epoch(f):
        match = re.search(r'lstm_finetuned_epoch_(\d+).pth', os.path.basename(f))
        return int(match.group(1)) if match else -1
        
    latest_model_path = max(model_files, key=extract_epoch)
    print(f"Loading latest LSTM Fine-Tuned model: {latest_model_path}")

    if not os.path.exists(valid_data_dir):
        print(f"Error: Valid dir not found: {valid_data_dir}")
        return
        
    valid_set = RealValidDataset(str(valid_data_dir))
    if len(valid_set) == 0: return
    # Shuffle=False 保证编号顺序一致，方便我们通过 index 获取文件名
    valid_loader = DataLoader(valid_set, batch_size=1, shuffle=False) 
    
    # === C. 初始化 LSTM 模型 ===
    model = LSTMEncoder(input_dim=1, d_model=64, hidden_size=128, num_layers=2).to(DEVICE)
    model.load_state_dict(torch.load(latest_model_path, map_location=DEVICE))
    model.eval()
    
    # === 初始化分类统计容器 ===
    stats = {
        "gaming": {"mse": 0, "mae": 0, "count": 0},
        "restaurant": {"mse": 0, "mae": 0, "count": 0},
        "other": {"mse": 0, "mae": 0, "count": 0}
    }

    print(f"Running LSTM FORECAST validation on ALL {len(valid_set)} traces...")
    
    with torch.no_grad():
        for i, (obs_norm, pseudo_rl, obs_raw) in enumerate(tqdm(valid_loader)):
            
            # 获取当前文件名以判断类别
            filename = os.path.basename(valid_set.files[i])
            if "gaming" in filename:
                category = "gaming"
            elif "restaurant" in filename:
                category = "restaurant"
            else:
                category = "other"

            obs_norm = obs_norm.to(DEVICE)
            pseudo_rl = pseudo_rl.to(DEVICE)
            obs_raw = obs_raw.to(DEVICE)
            
            # === 自回归预测输入构造 (错位) ===
            # Input: 0 -> T-2
            inp_obs = obs_norm[:, :-1, :]
            inp_rl  = pseudo_rl[:, :-1]
            
            # Target: 1 -> T-1
            tgt_bw_raw = obs_raw[:, 1:, :]
            
            # === Forward (移除 Mask) ===
            outputs = model(inp_obs, inp_rl)
            
            # 反归一化
            pred_bw_phys = outputs['recon_bw'] * SCALE_FACTOR
            
            # 指标计算 (Local)
            mse_loss = nn.MSELoss()(pred_bw_phys, tgt_bw_raw)
            mae_loss = nn.L1Loss()(pred_bw_phys, tgt_bw_raw)
            
            current_mse = mse_loss.item()
            current_mae = mae_loss.item()
            
            # === 更新对应类别的统计数据 ===
            stats[category]["mse"] += current_mse
            stats[category]["mae"] += current_mae
            stats[category]["count"] += 1
            
            # === 画图并保存 (加上类别标签) ===
            target_np = tgt_bw_raw[0].cpu().numpy().flatten()
            pred_np = pred_bw_phys[0].cpu().numpy().flatten()
            rl_np = pseudo_rl[0, 1:].cpu().numpy().flatten()
            
            plt.figure(figsize=(12, 6))
            
            plt.subplot(2, 1, 1)
            plt.plot(target_np, color='orange', alpha=0.6, label='Real Trace (Next Step)')
            plt.plot(pred_np, color='blue', linewidth=1.5, label='LSTM Forecast')
            plt.title(f"LSTM [{category}] - Trace {i} (MAE: {current_mae:.4f}, MSE: {current_mse:.4f})")
            plt.legend()
            
            plt.subplot(2, 1, 2)
            plt.plot(rl_np, color='purple', alpha=0.5, label='Run Length')
            plt.title("Run Length Context")
            
            # 按序号和类别命名
            save_path = os.path.join(output_dir, f"{i}_{category}.png")
            plt.tight_layout()
            plt.savefig(save_path)
            plt.close()

    # === 全局结果汇报 (Balanced) ===
    print("\n" + "=" * 50)
    print("LSTM Fine-Tuned Results (Balanced by Dataset)")
    print("=" * 50)

    # 计算各分项平均
    def calc_avg(cat_key):
        s = stats[cat_key]
        if s["count"] == 0:
            return 0.0, 0.0, 0
        return s["mse"] / s["count"], s["mae"] / s["count"], s["count"]

    g_mse, g_mae, g_count = calc_avg("gaming")
    r_mse, r_mae, r_count = calc_avg("restaurant")
    o_mse, o_mae, o_count = calc_avg("other")

    print(f"Gaming     (Count: {g_count}): MSE={g_mse:.4f}, MAE={g_mae:.4f}")
    print(f"Restaurant (Count: {r_count}): MSE={r_mse:.4f}, MAE={r_mae:.4f}")
    if o_count > 0:
        print(f"Other      (Count: {o_count}): MSE={o_mse:.4f}, MAE={o_mae:.4f}")

    # 计算宏平均 (Macro Average)
    if g_count > 0 and r_count > 0:
        final_mse = (g_mse + r_mse) / 2
        final_mae = (g_mae + r_mae) / 2
        print("-" * 50)
        print(f"FINAL MACRO-AVERAGE (Gaming + Restaurant) / 2:")
        print(f"MSE: {final_mse:.4f}")
        print(f"MAE: {final_mae:.4f}")
    else:
        print("-" * 50)
        print("Warning: One of the datasets is missing, showing global average instead.")
        total_mse = stats["gaming"]["mse"] + stats["restaurant"]["mse"] + stats["other"]["mse"]
        total_mae = stats["gaming"]["mae"] + stats["restaurant"]["mae"] + stats["other"]["mae"]
        total_count = g_count + r_count + o_count
        print(f"Global Average MSE: {total_mse/total_count:.4f}")
        print(f"Global Average MAE: {total_mae/total_count:.4f}")

    print("=" * 50)
    print(f"All plots saved to: {output_dir}")

if __name__ == "__main__":
    validate_finetuned_lstm()