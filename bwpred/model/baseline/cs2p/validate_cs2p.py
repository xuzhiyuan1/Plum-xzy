import numpy as np
import os
import glob
import joblib
import matplotlib.pyplot as plt
from pathlib import Path
from tqdm import tqdm
from sklearn.metrics import mean_squared_error, mean_absolute_error
import warnings

# 忽略 HMM 可能产生的计算警告
warnings.filterwarnings("ignore")

# ==========================================
# 1. 配置
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))
# 路径回退: cs2p -> baseline -> model -> BWPRED
project_root = Path(current_dir).parent.parent.parent
valid_data_dir = project_root / "data" / "real_trace" / "valid_data"
model_path = os.path.join(current_dir, "cs2p_hmm_model.pkl")
output_dir = os.path.join(current_dir, "validate_cs2p_result")

SCALE_FACTOR = 20.0 

if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# ==========================================
# 2. HMM 预测逻辑
# ==========================================
def predict_next_step_hmm(model, history):
    """
    history: 归一化后的历史观测值
    return: 下一步预测值 (归一化)
    """
    history = np.nan_to_num(history, nan=0.0, posinf=0.0, neginf=0.0)
    obs = np.array(history).reshape(-1, 1)
    
    try:
        log_prob, state_sequence = model.decode(obs, algorithm="viterbi")
        current_state = state_sequence[-1]
        
        transition_probs = model.transmat_[current_state]
        next_state = np.argmax(transition_probs)
        
        pred_value = model.means_[next_state][0]
        return pred_value
    except Exception as e:
        return np.mean(model.means_)

# ==========================================
# 3. 主验证流程 (支持类别权重平衡)
# ==========================================
def validate_cs2p():
    if not os.path.exists(model_path):
        print("Please run train_cs2p.py first!")
        return
        
    print(f"Loading HMM model from {model_path}...")
    model = joblib.load(model_path)
    
    files = sorted(glob.glob(os.path.join(valid_data_dir, "*.npy")))
    print(f"Found {len(files)} validation traces.")
    
    # === 初始化分类统计容器 ===
    stats = {
        "gaming": {"mse": 0, "mae": 0, "count": 0},
        "restaurant": {"mse": 0, "mae": 0, "count": 0},
        "other": {"mse": 0, "mae": 0, "count": 0} # 防止有不包含这两个关键词的文件
    }
    
    # 遍历所有文件
    for i, f in enumerate(tqdm(files)):
        filename = os.path.basename(f)
        
        # === 1. 确定类别 ===
        if "gaming" in filename:
            category = "gaming"
        elif "restaurant" in filename:
            category = "restaurant"
        else:
            category = "other"
        
        # === 2. 加载与清洗 ===
        raw_trace = np.load(f).flatten()
        raw_trace = np.nan_to_num(raw_trace, nan=0.0, posinf=0.0, neginf=0.0)
        norm_trace = raw_trace / SCALE_FACTOR
        
        preds_phys = []   
        targets_phys = [] 
        
        # 预测长度设定
        eval_len = min(len(norm_trace), 1000) 
        
        if eval_len < 10: continue

        # === 3. 预测循环 ===
        for t in range(eval_len - 1):
            history = norm_trace[:t+1] 
            target = raw_trace[t+1]    
            
            pred_norm = predict_next_step_hmm(model, history)
            pred_phys = pred_norm * SCALE_FACTOR
            
            preds_phys.append(pred_phys)
            targets_phys.append(target)
        
        # === 4. 统计误差 ===
        if len(targets_phys) > 0:
            mse = mean_squared_error(targets_phys, preds_phys)
            mae = mean_absolute_error(targets_phys, preds_phys)
            
            # 更新对应类别的统计数据
            stats[category]["mse"] += mse
            stats[category]["mae"] += mae
            stats[category]["count"] += 1
            
            plt.figure(figsize=(12, 5))
            plt.plot(targets_phys, color='orange', alpha=0.6, label='Real Trace')
            plt.plot(preds_phys, color='green', linewidth=1.5, label='CS2P Forecast')
            plt.title(f"CS2P [{category}] - {filename} - MAE: {mae:.4f}")
            plt.legend()
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, f"{i}.png"))
            plt.close()

    # === 5. 计算最终结果 (Macro-Average) ===
    print("\n" + "=" * 50)
    print("CS2P (HMM) Evaluation Results (Balanced)")
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

    # 计算宏平均 (Macro Average) = (Gaming_Avg + Restaurant_Avg) / 2
    # 只有当两个类别都有数据时才计算，否则回退到有的那个
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

if __name__ == "__main__":
    validate_cs2p()