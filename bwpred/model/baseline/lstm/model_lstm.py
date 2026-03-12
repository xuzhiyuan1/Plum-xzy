import torch
import torch.nn as nn

class LSTMEncoder(nn.Module):
    def __init__(self, input_dim=1, d_model=64, hidden_size=128, num_layers=2, max_run_len=1000):
        super().__init__()
        
        # 1. 观测值投影
        self.obs_proj = nn.Linear(input_dim, d_model)
        
        # 2. Run Length 编码 
        self.run_len_embedding = nn.Embedding(max_run_len, d_model)
        
        # 3. LSTM 主干
        # 注意：LSTM 是时序模型，处理 t 时刻时，物理上无法看到 t+1 时刻的数据
        # 所以不需要像 Transformer 那样加 Mask，它天生就是 Causal (因果) 的
        self.lstm = nn.LSTM(
            input_size=d_model, 
            hidden_size=hidden_size, 
            num_layers=num_layers, 
            batch_first=True,
            dropout=0.1 if num_layers > 1 else 0
        )
        
        # 4. 输出头
        # 现在的任务是：根据 t 时刻的 hidden state，预测 t+1 时刻的值
        self.hazard_head = nn.Linear(hidden_size, 1) # 预测下一时刻突变概率
        self.recon_head = nn.Linear(hidden_size, 1)  # 预测下一时刻带宽
        self.rl_head = nn.Linear(hidden_size, 1)     # 预测下一时刻RL
        
        self.relu = nn.ReLU()

    def forward(self, obs, run_lengths):
        """
        Args:
            obs: [Batch, Seq_Len, 1] (归一化后的数据)
            run_lengths: [Batch, Seq_Len]
        """
        B, T, _ = obs.shape
        
        # 1. 特征融合
        x_obs = self.obs_proj(obs)  # [B, T, d_model]
        
        if run_lengths.dim() == 3: 
            run_lengths = run_lengths.squeeze(-1)
        run_lengths = torch.clamp(run_lengths, max=self.run_len_embedding.num_embeddings - 1)
        x_rl = self.run_len_embedding(run_lengths) 
        
        x = x_obs + x_rl 
        
        # 2. LSTM 推理
        self.lstm.flatten_parameters() 
        # out: [B, T, hidden_size]
        # LSTM 会按顺序处理：x[0]->h[0], x[1]->h[1]...
        # h[t] 只包含了 0...t 的信息，不包含 t+1
        out, (h_n, c_n) = self.lstm(x)
        
        out = self.relu(out)
        
        # 3. 预测
        hazard_logits = self.hazard_head(out)
        recon_bw = self.recon_head(out)
        pred_rl = self.rl_head(out)
        
        return {
            'cp_logits': hazard_logits,
            'recon_bw': recon_bw,
            'pred_rl': pred_rl
        }