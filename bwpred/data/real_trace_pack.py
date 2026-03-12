import pandas as pd
import numpy as np
import os
import glob
import random
import shutil

# ==========================================
# 0. 路径配置
# ==========================================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../"))

# 输入目录
RESTAURANT_DIR = os.path.join(PROJECT_ROOT, "traces", "restaurant")
GAMING_DIR = os.path.join(PROJECT_ROOT, "traces", "gaming")

# 输出目录 (包含子文件夹)
OUTPUT_ROOT = os.path.join(CURRENT_DIR, "real_trace") # 修改了这里，保持整洁
TRAIN_DIR = os.path.join(OUTPUT_ROOT, "train_data")
VALID_DIR = os.path.join(OUTPUT_ROOT, "valid_data")

print(f"Project Root: {PROJECT_ROOT}")
print(f"Train Dir:    {TRAIN_DIR}")
print(f"Valid Dir:    {VALID_DIR}")
print("-" * 50)

# ==========================================
# 1. 加载函数 (保持不变)
# ==========================================
def load_restaurant_trace(filepath):
    try:
        df = pd.read_csv(filepath, sep=r'\s+', header=None, engine='python', on_bad_lines='skip')
        raw_bandwidth = df.iloc[:, 0].astype(str)
        bandwidth_data = raw_bandwidth.str.replace('Mbps', '', regex=False)
        bandwidth_data = pd.to_numeric(bandwidth_data, errors='coerce').dropna()
        return bandwidth_data.values.astype(np.float32)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return np.array([])

def load_gaming_trace(filepath):
    try:
        df = pd.read_csv(filepath, sep=',', header=None, on_bad_lines='skip')
        raw_bandwidth = df.iloc[:, 2] 
        bandwidth_data = pd.to_numeric(raw_bandwidth, errors='coerce').dropna()
        return bandwidth_data.values.astype(np.float32)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return np.array([])

# ==========================================
# 2. 辅助函数：保存与划分
# ==========================================
def save_dataset(samples, dataset_name):
    """
    samples: list of (filename, data_array)
    dataset_name: 'Restaurant' or 'Gaming'
    ratio: 2:1 (approx 0.67 for train)
    """
    if not samples:
        print(f"⚠️  No samples found for {dataset_name}.")
        return

    # 1. 随机打乱
    random.shuffle(samples)
    
    # 2. 计算切分点 (2:1)
    split_idx = int(len(samples) * 0.67)
    
    # 至少保证两边都有数据 (如果数据极少)
    if len(samples) > 1 and split_idx == 0: 
        split_idx = 1
    
    train_samples = samples[:split_idx]
    valid_samples = samples[split_idx:]
    
    print(f"\nProcessing {dataset_name}: Total {len(samples)}")
    print(f"  -> Train: {len(train_samples)} | Valid: {len(valid_samples)}")

    # 3. 保存到 Train
    for name, data in train_samples:
        save_path = os.path.join(TRAIN_DIR, name)
        np.save(save_path, data)
        
    # 4. 保存到 Valid
    for name, data in valid_samples:
        save_path = os.path.join(VALID_DIR, name)
        np.save(save_path, data)

# ==========================================
# 3. 主流程
# ==========================================
def pack_data():
    # 重置/创建目录
    if os.path.exists(TRAIN_DIR): shutil.rmtree(TRAIN_DIR)
    if os.path.exists(VALID_DIR): shutil.rmtree(VALID_DIR)
    os.makedirs(TRAIN_DIR, exist_ok=True)
    os.makedirs(VALID_DIR, exist_ok=True)

    # --- A. 收集 Restaurant 数据 ---
    restaurant_samples = []
    print("Loading Restaurant Traces...")
    for i in range(16):
        filename = f"real-rest-wifi_{i}.trace"
        filepath = os.path.join(RESTAURANT_DIR, filename)
        if os.path.exists(filepath):
            data = load_restaurant_trace(filepath)
            if len(data) > 50:
                save_name = f"restaurant_{i}.npy"
                restaurant_samples.append((save_name, data))
    
    # 执行划分和保存
    save_dataset(restaurant_samples, "Restaurant")

    # --- B. 收集 Gaming 数据 ---
    gaming_samples = []
    print("\nLoading Gaming Traces...")
    gaming_files = sorted(glob.glob(os.path.join(GAMING_DIR, "*.csv")))
    for filepath in gaming_files:
        basename = os.path.basename(filepath)
        data = load_gaming_trace(filepath)
        if len(data) > 50:
            safe_name = basename.replace('.csv', '').replace(' ', '_')
            save_name = f"gaming_{safe_name}.npy"
            gaming_samples.append((save_name, data))
            
    # 执行划分和保存
    save_dataset(gaming_samples, "Gaming")

    print("-" * 50)
    print(f"✅ Packaging Complete!")
    print(f"Train Data: {len(os.listdir(TRAIN_DIR))} files -> {TRAIN_DIR}")
    print(f"Valid Data: {len(os.listdir(VALID_DIR))} files -> {VALID_DIR}")

if __name__ == "__main__":
    pack_data()