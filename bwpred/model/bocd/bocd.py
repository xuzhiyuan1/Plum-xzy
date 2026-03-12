import numpy as np
import matplotlib.pyplot as plt
from scipy.special import gammaln

class BOCD_Gaussian:
    """
    自包含的贝叶斯在线突变点检测器 (Gaussian-Gamma Conjugate Prior)
    使用 Log-Space 计算以保证数值稳定性。
    """
    def __init__(self, hazard_rate=1/100.0, alpha0=1.0, beta0=1.0, kappa0=1.0, mu0=0.0, max_run_length=1000):
        # 风险函数参数 (几何分布)
        self.log_hazard = np.log(hazard_rate)
        self.log_1_minus_hazard = np.log(1 - hazard_rate)
        
        # 初始超参数
        self.alpha0 = alpha0
        self.beta0 = beta0
        self.kappa0 = kappa0
        self.mu0 = mu0
        
        # 剪枝参数
        self.max_run_length = max_run_length

        # 状态初始化
        # 这里的数组长度会随着时间步 t 动态增长，index i 代表 run_length = i
        self.alpha = np.array([self.alpha0])
        self.beta = np.array([self.beta0])
        self.kappa = np.array([self.kappa0])
        self.mu = np.array([self.mu0])
        
        # 记录 log 形式的 run_length 概率: log P(r_t | x_{1:t})
        self.log_R = np.array([0.0]) # log(1.0) = 0
        
    def reset(self):
        self.alpha = np.array([self.alpha0])
        self.beta = np.array([self.beta0])
        self.kappa = np.array([self.kappa0])
        self.mu = np.array([self.mu0])
        self.log_R = np.array([0.0])

    def update(self, x):
        """
        处理单个数据点 x，返回当前时间步最大概率的 run_length
        """
        # 1. 计算后验预测分布 (Student-t) 的 Log 概率
        # scale squared = beta * (kappa + 1) / (alpha * kappa)
        # degrees of freedom = 2 * alpha
        # 为了速度和数值稳定，手动展开 Student-t 的 Log PDF 公式
        
        df = 2 * self.alpha
        scale = np.sqrt(self.beta * (self.kappa + 1) / (self.alpha * self.kappa))
        
        # Log Student-t PDF:
        # log_prob = gammaln((df + 1) / 2) - gammaln(df / 2) 
        #            - 0.5 * log(df * pi) - log(scale) 
        #            - (df + 1) / 2 * log(1 + ((x - mu) / scale)^2 / df)
        
        term1 = gammaln((df + 1) / 2.0) - gammaln(df / 2.0)
        term2 = -0.5 * np.log(df * np.pi) - np.log(scale)
        term3 = - (df + 1) / 2.0 * np.log(1 + ((x - self.mu) / scale)**2 / df)
        
        log_pred_probs = term1 + term2 + term3
        
        # 2. 计算增长概率 (Growth Probabilities) 和 突变概率 (Changepoint Probabilities)
        # log_growth = log_R + log_pred + log(1-H)
        log_growth_probs = self.log_R + log_pred_probs + self.log_1_minus_hazard
        
        # log_cp = LogSumExp(log_R + log_pred + log(H))
        log_cp_prob = np.logaddexp.reduce(self.log_R + log_pred_probs + self.log_hazard)
        
        # 3. 组合新的 Run Length 分布
        new_log_R = np.concatenate((np.array([log_cp_prob]), log_growth_probs))
        
        # 4. 归一化 (Log Space: x - logsumexp(x))
        new_log_R -= np.logaddexp.reduce(new_log_R)
        self.log_R = new_log_R
        
        # 5. 更新超参数 (Sufficiency Statistics)
        # 对应 run_length=0 的新参数 (重置为先验)
        new_mu = np.array([self.mu0])
        new_kappa = np.array([self.kappa0])
        new_alpha = np.array([self.alpha0])
        new_beta = np.array([self.beta0])
        
        # 对应 run_length > 0 的参数更新
        # mu_{t+1} = (kappa * mu + x) / (kappa + 1)
        upd_mu = (self.kappa * self.mu + x) / (self.kappa + 1)
        # kappa_{t+1} = kappa + 1
        upd_kappa = self.kappa + 1
        # alpha_{t+1} = alpha + 0.5
        upd_alpha = self.alpha + 0.5
        # beta_{t+1} = beta + (kappa * (x-mu)^2) / (2*(kappa+1))
        upd_beta = self.beta + (self.kappa * (x - self.mu)**2) / (2 * (self.kappa + 1))
        
        self.mu = np.concatenate((new_mu, upd_mu))
        self.kappa = np.concatenate((new_kappa, upd_kappa))
        self.alpha = np.concatenate((new_alpha, upd_alpha))
        self.beta = np.concatenate((new_beta, upd_beta))
        
        # 6. 剪枝 (Pruning) - 可选，防止长时间运行变慢
        # 这里保留简单的阈值剪枝，如果 log 概率太小（比如 e^-20），就截断
        if len(self.log_R) > self.max_run_length:
            self.log_R = self.log_R[:self.max_run_length]
            self.mu = self.mu[:self.max_run_length]
            self.kappa = self.kappa[:self.max_run_length]
            self.alpha = self.alpha[:self.max_run_length]
            self.beta = self.beta[:self.max_run_length]

        # 返回当前概率最大的 Run Length
        return np.argmax(self.log_R)


def infer_run_lengths(obs_trace):
    """
    核心接口函数：对单条 trace 进行 BOCD 推理，返回推断出的 run_lengths
    
    Args:
        obs_trace (np.array): 形状为 (Seq_Len,) 的一维数组
        
    Returns:
        pred_run_lengths (np.array): 形状为 (Seq_Len,) 的整数数组
    """
    # 1. 数据预处理
    # 如果数据是 tensor 或 list，转为 numpy
    if hasattr(obs_trace, 'cpu'):
        data = obs_trace.cpu().numpy().flatten()
    else:
        data = np.array(obs_trace).flatten()
        
    seq_len = len(data)
    
    # 2. 配置参数 (针对 Bandwidth 数据的建议参数)
    # alpha: 形状参数 (类似样本数/2)
    # beta: 尺度参数 (主要控制方差的先验，带宽波动大，beta可以适当大一点)
    # kappa: 均值置信度 (越小越容易受新数据影响)
    # hazard_rate: 突变发生的概率，1/100 代表平均每 100 个点突变一次
    detector = BOCD_Gaussian(
        hazard_rate=1/50.0, 
        alpha0=1.0, 
        beta0=1.0, 
        kappa0=0.1, 
        mu0=np.mean(data[:10]) if seq_len > 10 else 0 # 用前几个数的均值初始化更稳健
    )
    
    pred_run_lengths = np.zeros(seq_len, dtype=int)
    
    # 3. 运行检测 (在线模拟)
    for t in range(seq_len):
        pred_rl = detector.update(data[t])
        pred_run_lengths[t] = pred_rl
        
    return pred_run_lengths

# ==========================================
# 调试用的主函数
# ==========================================
if __name__ == "__main__":
    # 测试一下功能
    print("Testing infer_run_lengths...")
    
    # 生成一段模拟的“带宽”数据：有噪声，有均值突变，也有方差突变
    np.random.seed(42)
    data_seg1 = np.random.normal(loc=10, scale=1, size=50) # 稳定低带宽
    data_seg2 = np.random.normal(loc=30, scale=5, size=50) # 突增带宽，且波动变大
    data_seg3 = np.random.normal(loc=5, scale=0.5, size=50) # 骤降带宽
    
    test_data = np.concatenate([data_seg1, data_seg2, data_seg3])
    
    rl = infer_run_lengths(test_data)
    
    # 绘图
    fig, ax1 = plt.subplots(figsize=(10, 5))

    color = 'tab:blue'
    ax1.set_xlabel('Time')
    ax1.set_ylabel('Data Value', color=color)
    ax1.plot(test_data, color=color, alpha=0.6, label='Observed Data')
    ax1.tick_params(axis='y', labelcolor=color)

    ax2 = ax1.twinx()  # 共享x轴
    color = 'tab:red'
    ax2.set_ylabel('Inferred Run Length', color=color)
    ax2.plot(rl, color=color, linestyle='--', linewidth=1.5, label='Run Length')
    ax2.tick_params(axis='y', labelcolor=color)

    plt.title("BOCD Result (Custom Implementation)")
    fig.tight_layout()
    plt.savefig('bocd_test_custom.png')
    plt.show()
    
    print("Test done. Saved bocd_test_custom.png")