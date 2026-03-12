import numpy as np
import os
import shutil
import scipy.stats as stats
from tqdm import tqdm
import torch
import csv
import matplotlib.pyplot as plt

class WifiBandwidthSynthesizer:
    def __init__(self, 
                 min_bw=2.0, max_bw=50.0, 
                 sampling_rate=0.1): 
        self.min_bw = min_bw
        self.max_bw = max_bw
        self.dt = sampling_rate
        
    def _sample_duration(self, dist_type='weibull'):
        if dist_type == 'pareto':
            duration = (np.random.pareto(a=3.0) + 1) * 20 
        elif dist_type == 'weibull':
            duration = stats.weibull_min.rvs(c=1.5, scale=50)
        else:
            duration = np.random.exponential(scale=30)
        return int(np.clip(duration, 5, 300))

    def _get_next_bandwidth(self, current_bw):
        if np.random.rand() < 0.3:
            change = np.random.uniform(-0.2, 0.2) * current_bw
            new_bw = current_bw + change
        else:
            new_bw = np.random.uniform(self.min_bw, self.max_bw)
        return np.clip(new_bw, self.min_bw, self.max_bw)

    def _apply_transition_physics(self, signal, start_idx, end_idx, old_mu, new_mu):
        length = end_idx - start_idx
        
        # === 【修复】 ===
        # 如果段长度太短（例如在Trace末尾被截断），强制使用 'instant'
        # 避免 randint(2, 2) 这种导致 low >= high 的错误
        if length < 3:
            trans_type = 'instant'
        else:
            trans_type = np.random.choice(['instant', 'gradual', 'overshoot'], p=[0.2, 0.4, 0.4])
        
        segment = np.ones(length) * new_mu
        
        if trans_type == 'gradual':
            # 确保 high (min(...) + 1) 至少比 low (2) 大
            max_ramp = min(length, 15)
            if max_ramp < 2: 
                ramp_len = 2 # fallback
            else:
                ramp_len = np.random.randint(2, max_ramp + 1)
                
            ramp = np.linspace(old_mu, new_mu, ramp_len)
            segment[:ramp_len] = ramp
            
        elif trans_type == 'overshoot':
            settle_len = np.random.randint(3, min(length, 20) + 1)
            peak_val = new_mu + (new_mu - old_mu) * np.random.uniform(0.2, 0.5)
            peak_idx = int(settle_len * 0.3)
            
            if peak_idx > 0:
                segment[:peak_idx] = np.linspace(old_mu, peak_val, peak_idx)
                segment[peak_idx:settle_len] = np.linspace(peak_val, new_mu, settle_len - peak_idx)
        
        signal[start_idx:end_idx] = segment

    def generate_trace(self, duration_sec=100):
        n_samples = int(duration_sec / self.dt)
        raw_signal = np.zeros(n_samples)
        run_lengths = np.zeros(n_samples, dtype=np.int32)
        cp_flags = np.zeros(n_samples, dtype=np.int32)
        
        current_idx = 0
        current_bw = np.random.uniform(self.min_bw, self.max_bw)
        
        while current_idx < n_samples:
            duration = self._sample_duration('weibull')
            end_idx = min(current_idx + duration, n_samples)
            old_bw = current_bw if current_idx > 0 else current_bw
            
            if current_idx > 0:
                cp_flags[current_idx] = 1 
                self._apply_transition_physics(raw_signal, current_idx, end_idx, old_bw, current_bw)
            else:
                raw_signal[current_idx:end_idx] = current_bw
                
            segment_len = end_idx - current_idx
            run_lengths[current_idx:end_idx] = np.arange(segment_len)
            
            current_idx = end_idx
            current_bw = self._get_next_bandwidth(current_bw)

        noise_level = 0.05
        noise = np.random.normal(0, raw_signal * noise_level, n_samples)
        obs_signal = raw_signal + noise
        obs_signal = np.maximum(obs_signal, 0.1)

        return {
            'obs_trace': torch.tensor(obs_signal, dtype=torch.float32),
            'true_hidden': torch.tensor(raw_signal, dtype=torch.float32),
            'cp_flags': torch.tensor(cp_flags, dtype=torch.long),
            'run_lengths': torch.tensor(run_lengths, dtype=torch.long)
        }

# === 绘图辅助函数 ===
def plot_trace(trace_data, save_path):
    obs = trace_data['obs_trace'].numpy()
    clean = trace_data['true_hidden'].numpy()
    cps = np.where(trace_data['cp_flags'].numpy() == 1)[0]
    
    plt.figure(figsize=(10, 4))
    plt.plot(obs, label='Observed (Noisy)', color='#1f77b4', alpha=0.6)
    plt.plot(clean, label='Hidden (Clean)', color='orange', linewidth=2)
    
    for cp in cps:
        plt.axvline(x=cp, color='red', linestyle='--', alpha=0.3)
        
    plt.title(f"Preview: {os.path.basename(save_path)}")
    plt.legend(loc='upper right')
    plt.tight_layout()
    plt.savefig(save_path)
    plt.close()

# === CSV保存函数 ===
def save_trace_to_csv(trace_data, save_path):
    obs = trace_data['obs_trace'].numpy()
    hidden = trace_data['true_hidden'].numpy()
    flags = trace_data['cp_flags'].numpy()
    r_lens = trace_data['run_lengths'].numpy()
    
    with open(save_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['step', 'time_sec', 'obs_trace', 'true_hidden', 'cp_flag', 'run_length'])
        
        for t in range(len(obs)):
            writer.writerow([
                t,
                round(t * 0.1, 1),
                f"{obs[t]:.4f}",
                f"{hidden[t]:.4f}",
                flags[t],
                r_lens[t]
            ])

def generate_dataset(base_dir='./'):
    synthesizer = WifiBandwidthSynthesizer(min_bw=2.0, max_bw=50.0, sampling_rate=0.1)
    
    tasks = [
        ('pre_train_data', 1000),
        ('valid_data', 100)      
    ]
    
    print(f"Start generating synthetic data...")
    
    for folder_name, num_traces in tasks:
        dir_path = os.path.join(base_dir, folder_name)
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
        os.makedirs(dir_path)
        
        print(f"Generating {num_traces} traces into {dir_path}...")
        
        for i in tqdm(range(num_traces)):
            trace_data = synthesizer.generate_trace(duration_sec=100)
            
            # 1. 保存 .pt
            pt_path = os.path.join(dir_path, f'trace_{i:04d}.pt')
            torch.save(trace_data, pt_path)

            # 2. 保存 .csv
            csv_path = os.path.join(dir_path, f'trace_{i:04d}.csv')
            save_trace_to_csv(trace_data, csv_path)
            
            # 3. 保存预览图 (前5张)
            if i < 5:
                png_path = os.path.join(dir_path, f'trace_{i:04d}_preview.png')
                plot_trace(trace_data, png_path)
            
    print("Data generation complete. Check folder for _preview.png files!")

if __name__ == "__main__":
    generate_dataset()