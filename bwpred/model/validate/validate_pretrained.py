import sys
import os
import glob
import re
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from tqdm import tqdm

# ==========================================
# 1. 路径修复
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, "../encoder"))
sys.path.append(os.path.join(current_dir, ".."))

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from sklearn.metrics import f1_score, precision_score, recall_score

try:
    # 这里的 WifiDataset 已经在 pre_train.py 里做过归一化了 (/20.0)
    from pre_train import WifiDataset #pyright: ignore
    from model import BandwidthEncoder    
    from bocd.bocd import infer_run_lengths 
except ImportError as e:
    print(f"Import Error: {e}")
    raise e

# ==========================================
# 辅助函数
# ==========================================
def generate_square_subsequent_mask(sz):
    mask = (torch.triu(torch.ones(sz, sz)) == 1).transpose(0, 1)
    mask = mask.float().masked_fill(mask == 0, float('-inf')).masked_fill(mask == 1, float(0.0))
    return mask

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

# ==========================================
# 主验证流程
# ==========================================
def validate_pipeline():
    DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # 归一化因子 (必须与训练时保持一致)
    SCALE_FACTOR = 20.0
    
    # === A. 路径配置 ===
    project_root = os.path.abspath(os.path.join(current_dir, "../../"))
    valid_dir = os.path.join(project_root, "data/valid_data")
    encoder_dir = os.path.join(current_dir, "../encoder")
    
    # === B. 寻找最新模型 ===
    search_patterns = [
        os.path.join(encoder_dir, "encoder_epoch_*.pth"),
        os.path.join(current_dir, "encoder_epoch_*.pth")
    ]
    model_files = []
    for pattern in search_patterns:
        model_files.extend(glob.glob(pattern))
        
    if not model_files:
        print(f"Error: No model files found!")
        return

    def extract_epoch(f):
        match = re.search(r'encoder_epoch_(\d+).pth', os.path.basename(f))
        return int(match.group(1)) if match else -1
        
    latest_model_path = max(model_files, key=extract_epoch)
    print(f"Loading latest model: {latest_model_path}")

    # === C. 加载数据与模型 ===
    if not os.path.exists(valid_dir):
        print(f"Error: Data directory not found: {valid_dir}")
        return

    valid_set = WifiDataset(valid_dir)
    valid_loader = DataLoader(valid_set, batch_size=1, shuffle=True)
    
    model = BandwidthEncoder(input_dim=1, d_model=64, nhead=4, num_layers=3).to(DEVICE)
    model.load_state_dict(torch.load(latest_model_path, map_location=DEVICE))
    model.eval()
    
    # === D. 推理循环 ===
    all_preds, all_targets = [], []
    all_delays = []
    
    total_mse = 0
    total_mae = 0
    count = 0
    plot_data = None 

    print("Running FORECAST evaluation (Processing only 5 samples)...")
    
    with torch.no_grad():
        for i, (obs, true_bw, cp_flags, true_run_lens) in enumerate(tqdm(valid_loader)):
            if i >= 5: break
                
            obs = obs.to(DEVICE)
            true_bw = true_bw.to(DEVICE)
            cp_flags = cp_flags.to(DEVICE)
            
            # 1. BOCD 推理 (需使用反归一化的原始数据，因为BOCD参数基于物理数值)
            # obs 已经是归一化过的了，所以乘回去
            obs_raw_np = (obs[0, :, 0].cpu().numpy() * SCALE_FACTOR)
            inferred_rl_np = infer_run_lengths(obs_raw_np)
            
            # 对齐 RL 长度
            target_len = len(obs_raw_np)
            if len(inferred_rl_np) < target_len:
                diff = target_len - len(inferred_rl_np)
                inferred_rl_np = np.pad(inferred_rl_np, (diff, 0), 'constant')
            elif len(inferred_rl_np) > target_len:
                inferred_rl_np = inferred_rl_np[:target_len]
            
            inferred_rl_tensor = torch.as_tensor(inferred_rl_np, device=DEVICE).long().unsqueeze(0)
            
            # 2. 构造预测输入 (Shifted & Masked)
            # Input:  0 -> T-2
            # Target: 1 -> T-1
            inp_obs = obs[:, :-1, :]
            inp_rl  = inferred_rl_tensor[:, :-1]
            
            # 目标真值 (归一化的)
            tgt_bw_norm = true_bw[:, 1:, :] 
            tgt_cp = cp_flags[:, 1:, :]
            
            # 生成因果 Mask
            seq_len = inp_obs.size(1)
            src_mask = generate_square_subsequent_mask(seq_len).to(DEVICE)
            
            # 3. Encoder 推理
            outputs = model(inp_obs, inp_rl, src_mask=src_mask)
            
            # 4. 反归一化 (Denormalize) 用于计算物理误差
            pred_bw_phys = outputs['recon_bw'] * SCALE_FACTOR
            tgt_bw_phys  = tgt_bw_norm * SCALE_FACTOR
            
            # 5. 记录指标 (基于物理数值 Mbps)
            mse_loss = nn.MSELoss()(pred_bw_phys, tgt_bw_phys)
            mae_loss = nn.L1Loss()(pred_bw_phys, tgt_bw_phys)
            total_mse += mse_loss.item()
            total_mae += mae_loss.item()
            count += 1
            
            # 6. 记录分类
            probs = torch.sigmoid(outputs['cp_logits'])
            preds = (probs > 0.5).long()
            
            all_preds.extend(preds.cpu().numpy().flatten())
            all_targets.extend(tgt_cp.cpu().numpy().flatten())
            
            # 计算延迟
            delays = calc_delay(tgt_cp.cpu().numpy().flatten(), preds.cpu().numpy().flatten())
            all_delays.extend(delays)
            
            # 存图数据
            if i == 0:
                plot_data = {
                    # 画图时 Input 和 Pred 最好错开一位显示，或者直接画 Target vs Pred
                    # 这里画的是 t=1..T 的对比
                    'target_bw': tgt_bw_phys[0].cpu().numpy().flatten(),
                    'pred_bw': pred_bw_phys[0].cpu().numpy().flatten(),
                    'obs_raw': obs_raw_np[1:], # 对应的原始观测(后移一位)
                    'prob': probs[0].cpu().numpy().flatten(),
                    'flags': tgt_cp[0].cpu().numpy().flatten(),
                    'inferred_rl': inferred_rl_np[1:],
                    'true_rl': true_run_lens[0, 1:].cpu().numpy().flatten() # <--- 新增真实RL
                }

    # === E. 打印指标 ===
    avg_mse = total_mse / count
    avg_mae = total_mae / count
    f1 = f1_score(all_targets, all_preds, zero_division=0)
    precision = precision_score(all_targets, all_preds, zero_division=0)
    recall = recall_score(all_targets, all_preds, zero_division=0)
    
    if len(all_delays) > 0:
        avg_delay_step = np.mean(all_delays)
        avg_delay_time = avg_delay_step * 0.1 
        delay_str = f"{avg_delay_step:.2f} steps ({avg_delay_time:.3f} sec)"
    else:
        delay_str = "N/A"

    print("-" * 50)
    print(f"Pre-trained FORECAST Results:")
    print(f"MSE (Mbps^2): {avg_mse:.4f}")
    print(f"MAE (Mbps)  : {avg_mae:.4f}")
    print(f"CP F1       : {f1:.4f}")
    print(f"Delay       : {delay_str}")
    print("-" * 50)
    
    # === F. 画图 ===
    if plot_data:
        plt.figure(figsize=(12, 10))
        
        # 子图1：带宽预测
        plt.subplot(3, 1, 1)
        plt.plot(plot_data['obs_raw'], color='lightgray', label='Observed (t=1..T)')
        plt.plot(plot_data['target_bw'], color='green', linestyle='--', label='True BW (Target)')
        plt.plot(plot_data['pred_bw'], color='blue', alpha=0.8, label='Forecast (Next Step)')
        # <--- 修改：标题增加 MSE
        plt.title(f"1. Bandwidth Forecasting (MSE: {avg_mse:.4f} | MAE: {avg_mae:.4f})")
        plt.legend(loc='upper right')
        
        # 子图2：Run Length (Inferred vs True)
        plt.subplot(3, 1, 2)
        # <--- 修改：增加真实 RL 的绘制
        plt.plot(plot_data['true_rl'], color='green', linestyle='--', alpha=0.5, label='True Run Length')
        plt.plot(plot_data['inferred_rl'], color='purple', label='BOCD Inferred RL')
        plt.title("2. Run Length Estimation")
        plt.legend(loc='upper right')
        
        # 子图3：突变概率
        plt.subplot(3, 1, 3)
        plt.plot(plot_data['prob'], color='red', label='CP Prob')
        plt.axhline(0.5, color='gray', linestyle=':')
        true_cp = np.where(plot_data['flags'] == 1)[0]
        for cp in true_cp:
            plt.axvline(x=cp, color='green', alpha=0.5, linestyle='--')
        plt.title(f"3. CP Prediction (F1: {f1:.2f})")
        
        save_path = os.path.join(current_dir, 'validate_pretrained_result.png')
        plt.tight_layout()
        plt.savefig(save_path)
        print(f"Visualization saved to: {save_path}")

if __name__ == "__main__":
    validate_pipeline()