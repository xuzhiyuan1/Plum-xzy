import numpy as np
from hmmlearn import hmm
import os
import glob
import joblib
from pathlib import Path

# ==========================================
# 1. 配置
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = Path(current_dir).parent.parent.parent
train_data_dir = project_root / "data" / "real_trace" / "train_data"
save_path = os.path.join(current_dir, "cs2p_hmm_model.pkl")

N_STATES = 6 
SCALE_FACTOR = 20.0 

# ==========================================
# 2. 数据加载 (增强版)
# ==========================================
def load_training_data(data_dir):
    print(f"Loading data from {data_dir}...")
    files = sorted(glob.glob(os.path.join(data_dir, "*.npy")))
    
    if len(files) == 0:
        raise ValueError("No .npy files found!")
        
    X_concat = []
    lengths = []
    
    total_raw_points = 0
    
    for f in files:
        raw = np.load(f).flatten()
        
        # 【防线1：处理无效值】
        # 将 NaN (空值) 和 Inf (无穷大) 替换为 0
        raw = np.nan_to_num(raw, nan=0.0, posinf=0.0, neginf=0.0)
        
        # 【防线2：归一化】
        norm = raw / SCALE_FACTOR
        
        # 【防线3：下采样】
        # 1500万数据太大了，会导致浮点数累积误差。
        # 每 10 个点取 1 个 (Step=10)，足够学习分布了。
        norm = norm[::10]
        
        if len(norm) < 10: continue # 忽略太短的序列
        
        X_concat.append(norm.reshape(-1, 1))
        lengths.append(len(norm))
        total_raw_points += len(norm)
        
    X = np.concatenate(X_concat)
    
    # 【防线4：截断极端值】
    # 防止某些极端大的噪点导致 K-Means 质心飞出天际
    # 假设归一化后大部分数据在 0~1 之间，超过 100 的肯定是异常值
    X = np.clip(X, a_min=0, a_max=100)
    
    return X, lengths

# ==========================================
# 3. 训练 HMM
# ==========================================
def train():
    if not os.path.exists(train_data_dir):
        print(f"Error: Path not found {train_data_dir}")
        return

    # 1. 准备数据
    X, lengths = load_training_data(train_data_dir)
    print(f"Effective training samples (after downsampling): {len(X)}")
    print(f"Max value in data: {np.max(X):.4f}, Min value: {np.min(X):.4f}")
    
    # 2. 初始化 Gaussian HMM
    # 【关键修复】：min_covar
    # 默认值是 1e-3。如果数据中有大量 0，方差会趋近于 0。
    # 这里的 scale 是 20，归一化后 0 还是 0。
    # 强制设置最小协方差，防止除以零错误。
    model = hmm.GaussianHMM(
        n_components=N_STATES, 
        covariance_type="diag", 
        n_iter=100, 
        verbose=True,
        min_covar=1e-3, # 防止方差过小
        tol=1e-4        # 收敛阈值
    )
    
    print(f"Start training HMM with {N_STATES} states...")
    try:
        model.fit(X, lengths)
        print("Training converged.")
        
        # 3. 打印结果
        means = model.means_.flatten()
        print("-" * 30)
        print("Learned States (Normalized Bandwidth Means):")
        sorted_means = np.sort(means)
        print(sorted_means)
        print(f"Physical Bandwidth Means (Mbps): {sorted_means * SCALE_FACTOR}")
        print("-" * 30)
        
        # 4. 保存
        joblib.dump(model, save_path)
        print(f"Model saved to: {save_path}")
        
    except Exception as e:
        print(f"Training failed with error: {e}")
        # 如果还是失败，尝试打印更详细的数据统计以便调试
        print("Data Statistics:")
        print(f"Mean: {np.mean(X)}, Std: {np.std(X)}")
        print(f"Has NaN: {np.isnan(X).any()}, Has Inf: {np.isinf(X).any()}")

if __name__ == "__main__":
    train()