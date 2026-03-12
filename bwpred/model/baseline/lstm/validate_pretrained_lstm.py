import sys
import os
import glob
import re
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from tqdm import tqdm

# ==========================================
# 1. 路径修复 (针对 model/baseline/lstm 结构)
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
from torch.utils.data import DataLoader
from sklearn.metrics import f1_score, precision_score, recall_score

try:
    # 1. 导入同目录下的 LSTM 模块
    from pre_train_lstm import WifiDataset  #pyright: ignore
    from model_lstm import LSTMEncoder      #pyright: ignore
    
    # 2. 导入 BOCD (因为把 bocd 目录加到了 path，可以直接 import bocd 文件)
    # 尝试两种导入方式以防万一
    try:
        from bocd import infer_run_lengths
    except ImportError:
        from bocd.bocd import infer_run_lengths
        
except ImportError as e:
    print(f"Import Error details: {e}")
    print(f"Current sys.path: {sys.path}")
    raise e

# 辅助函数：计算延迟
def calc_delay(true_flags, pred_flags, tolerance=20):
    true_indices = np.where(true_flags == 1)[0]
    pred_indices = np.where(pred_flags == 1)[0]
    delays = []
    for t_true in true_indices:
        candidates = pred_indices[np.abs(pred_indices - t_true) <= tolerance]
        if len(candidates) > 0:
            closest_pred = candidates[np.argmin(np.abs(candidates - t_true))]
            delay = closest_pred - t_true
            delays.append(delay)
    return delays

def validate_pretrained_lstm():
    DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    SCALE_FACTOR = 20.0
    
    # === A. 路径配置 (适配 baseline/lstm 结构) ===
    # data 目录在 model 的上一级
    project_root = os.path.abspath(os.path.join(model_root, "../"))
    valid_dir = os.path.join(project_root, "data/valid_data")
    
    # === B. 寻找最新 LSTM 模型 ===
    search_patterns = [
        os.path.join(current_dir, "lstm_epoch_*.pth") # 只在当前 lstm 目录找
    ]
    model_files = []
    for pattern in search_patterns:
        model_files.extend(glob.glob(pattern))
        
    if not model_files:
        print(f"Error: No LSTM model files (lstm_epoch_*.pth) found in {current_dir}")
        return

    def extract_epoch(f):
        match = re.search(r'lstm_epoch_(\d+).pth', os.path.basename(f))
        return int(match.group(1)) if match else -1
        
    latest_model_path = max(model_files, key=extract_epoch)
    print(f"Loading latest LSTM model: {latest_model_path}")

    # === C. 加载数据与模型 ===
    if not os.path.exists(valid_dir):
        print(f"Error: Data directory not found: {valid_dir}")
        return

    valid_set = WifiDataset(valid_dir)
    valid_loader = DataLoader(valid_set, batch_size=1, shuffle=True)
    
    # 初始化 LSTM 模型
    model = LSTMEncoder(input_dim=1, d_model=64, hidden_size=128, num_layers=2).to(DEVICE)
    model.load_state_dict(torch.load(latest_model_path, map_location=DEVICE))
    model.eval()
    
    # === D. 推理循环 ===
    all_preds, all_targets = [], []
    all_delays = []
    total_mse = 0
    total_mae = 0
    count = 0
    plot_data = None 

    print("Running LSTM Pre-trained FORECAST evaluation...")
    
    with torch.no_grad():
        for i, (obs, true_bw, cp_flags, true_run_lens) in enumerate(tqdm(valid_loader)):
            # if i >= 5: break
                
            obs = obs.to(DEVICE)
            true_bw = true_bw.to(DEVICE)
            cp_flags = cp_flags.to(DEVICE)
            
            # 1. BOCD 推理
            obs_raw_np = (obs[0, :, 0].cpu().numpy() * SCALE_FACTOR)
            try:
                inferred_rl_np = infer_run_lengths(obs_raw_np)
            except:
                inferred_rl_np = np.zeros_like(obs_raw_np)
            
            # 对齐
            target_len = len(obs_raw_np)
            if len(inferred_rl_np) < target_len:
                diff = target_len - len(inferred_rl_np)
                inferred_rl_np = np.pad(inferred_rl_np, (diff, 0), 'constant')
            elif len(inferred_rl_np) > target_len:
                inferred_rl_np = inferred_rl_np[:target_len]
            
            inferred_rl_tensor = torch.as_tensor(inferred_rl_np, device=DEVICE).long().unsqueeze(0)
            
            # 2. 构造输入 (Shifted)
            inp_obs = obs[:, :-1, :]
            inp_rl  = inferred_rl_tensor[:, :-1]
            
            tgt_bw_norm = true_bw[:, 1:, :]
            tgt_cp = cp_flags[:, 1:, :]
            
            # 3. LSTM 推理
            outputs = model(inp_obs, inp_rl)
            
            # 4. 反归一化
            pred_bw_phys = outputs['recon_bw'] * SCALE_FACTOR
            tgt_bw_phys  = tgt_bw_norm * SCALE_FACTOR
            
            # 5. 记录
            mse_loss = nn.MSELoss()(pred_bw_phys, tgt_bw_phys)
            mae_loss = nn.L1Loss()(pred_bw_phys, tgt_bw_phys)
            total_mse += mse_loss.item()
            total_mae += mae_loss.item()
            count += 1
            
            probs = torch.sigmoid(outputs['cp_logits'])
            preds = (probs > 0.5).long()
            
            all_preds.extend(preds.cpu().numpy().flatten())
            all_targets.extend(tgt_cp.cpu().numpy().flatten())
            all_delays.extend(calc_delay(tgt_cp.cpu().numpy().flatten(), preds.cpu().numpy().flatten()))
            
            if i == 0:
                plot_data = {
                    'obs_raw': obs_raw_np[1:],
                    'true_bw': tgt_bw_phys[0].cpu().numpy().flatten(),
                    'pred_bw': pred_bw_phys[0].cpu().numpy().flatten(),
                    'prob': probs[0].cpu().numpy().flatten(),
                    'flags': tgt_cp[0].cpu().numpy().flatten(),
                    'preds': preds[0].cpu().numpy().flatten(),
                    'true_rl': true_run_lens[0, 1:].cpu().numpy().flatten(),
                    'inferred_rl': inferred_rl_np[1:]
                }

    # === E. 打印指标 ===
    avg_mse = total_mse / count
    avg_mae = total_mae / count
    f1 = f1_score(all_targets, all_preds, zero_division=0)
    
    if len(all_delays) > 0:
        avg_delay_step = np.mean(all_delays)
        delay_str = f"{avg_delay_step:.2f} steps"
    else:
        delay_str = "N/A"

    print("-" * 50)
    print(f"LSTM Pre-trained Results:")
    print(f"MSE (Mbps^2): {avg_mse:.4f}")
    print(f"MAE (Mbps)  : {avg_mae:.4f}")
    print(f"CP F1       : {f1:.4f}")
    print(f"Delay       : {delay_str}")
    print("-" * 50)
    
    # === F. 画图 ===
    if plot_data:
        plt.figure(figsize=(12, 10))
        plt.subplot(3, 1, 1)
        plt.plot(plot_data['obs_raw'], color='lightgray', label='Observed (t=1..T)')
        plt.plot(plot_data['true_bw'], color='green', linestyle='--', label='True Hidden')
        plt.plot(plot_data['pred_bw'], color='blue', alpha=0.8, label='LSTM Forecast')
        plt.title(f"1. LSTM Forecasting (MSE: {avg_mse:.4f}, MAE: {avg_mae:.4f})")
        plt.legend(loc='upper right')
        
        plt.subplot(3, 1, 2)
        plt.plot(plot_data['true_rl'], color='green', linestyle='--', alpha=0.5, label='True RL')
        plt.plot(plot_data['inferred_rl'], color='purple', label='BOCD RL')
        plt.title("2. Run Length")
        plt.legend(loc='upper right')
        
        plt.subplot(3, 1, 3)
        plt.plot(plot_data['prob'], color='red', label='LSTM CP Prob')
        plt.axhline(0.5, color='gray', linestyle=':')
        true_cp = np.where(plot_data['flags'] == 1)[0]
        for cp in true_cp:
            plt.axvline(x=cp, color='green', alpha=0.5, linestyle='--')
        
        save_path = os.path.join(current_dir, 'validate_pretrained_lstm_result.png')
        plt.tight_layout()
        plt.savefig(save_path)
        print(f"Visualization saved: {save_path}")

if __name__ == "__main__":
    validate_pretrained_lstm()