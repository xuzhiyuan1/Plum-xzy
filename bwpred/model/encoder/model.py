import torch
import torch.nn as nn
import math

class BandwidthEncoder(nn.Module):
    def __init__(self, input_dim=1, d_model=64, nhead=4, num_layers=3, max_len=5000, max_run_len=1000):
        super().__init__()
        
        # 1. 观测值投影
        self.obs_proj = nn.Linear(input_dim, d_model)
        
        # 2. 绝对位置编码 (可学习参数)
        self.pos_embedding = nn.Parameter(torch.randn(1, max_len, d_model))
        
        # 3. Run Length 编码 (关键：将游程长度映射为向量)
        self.run_len_embedding = nn.Embedding(max_run_len, d_model)
        
        # 4. Transformer Encoder
        encoder_layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=nhead, 
                                                   dim_feedforward=d_model*4, 
                                                   dropout=0.1, 
                                                   batch_first=True)
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        
        # 5. 输出头
        self.hazard_head = nn.Linear(d_model, 1) # 预测突变概率
        self.recon_head = nn.Linear(d_model, 1)  # 预测带宽重构
        self.rl_head = nn.Linear(d_model, 1)     # 辅助任务：预测RL (可选)

    def forward(self, obs, run_lengths, src_mask=None):
        """
        Args:
            obs: [Batch, Seq_Len, 1]
            run_lengths: [Batch, Seq_Len] (Long Tensor)
            src_mask: [Seq_Len, Seq_Len] (可选，用于因果掩码)
        """
        B, T, _ = obs.shape
        
        # 1. 基础特征
        x = self.obs_proj(obs) # [B, T, d_model]
        
        # 2. 注入位置信息
        # 绝对位置 (防止越界，截断一下)
        safe_T = min(T, self.pos_embedding.shape[1])
        x = x + self.pos_embedding[:, :safe_T, :]
        
        # Run Length 信息融合
        # 确保 run_lengths 维度匹配 [B, T]
        if run_lengths.dim() == 3: 
            run_lengths = run_lengths.squeeze(-1)
            
        # 防止 run_length 数值超过 Embedding 表大小
        run_lengths = torch.clamp(run_lengths, max=self.run_len_embedding.num_embeddings - 1)
        
        r_emb = self.run_len_embedding(run_lengths) # [B, T, d_model]
        x = x + r_emb
        
        # 3. Transformer 推理
        # 传入 mask 以支持自回归预测 (Auto-Regressive)
        memory = self.transformer(x, mask=src_mask)
        
        # 4. 预测
        hazard_logits = self.hazard_head(memory)
        recon_bw = self.recon_head(memory)
        pred_rl = self.rl_head(memory)
        
        return {
            'cp_logits': hazard_logits,
            'recon_bw': recon_bw,
            'pred_rl': pred_rl
        }