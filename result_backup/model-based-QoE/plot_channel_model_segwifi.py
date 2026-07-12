import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# --- 配置参数 ---
DATA_PATH = 'result_channel_model_independent.csv'
OUTPUT_FILE = 'mlpred_performance_comparison.png'

def main():
    # 1. 检查文件是否存在
    if not os.path.exists(DATA_PATH):
        print(f"错误: 找不到数据文件 {DATA_PATH}")
        print("请确保在 analyze 文件夹下运行此脚本。")
        return

    # 2. 读取数据
    print(f"正在读取数据: {DATA_PATH} ...")
    df = pd.read_csv(DATA_PATH)
    
    # 清理列名（去除可能包含的空格）
    df.columns = df.columns.str.strip()

    # 将 mlpred 转换为可读性更高的分类标签
    df['ML_Prediction'] = df['mlpred'].map({0: 'w/o ML Pred (0)', 1: 'w/ ML Pred (1)'})
    # 将 seed 转换为字符串，确保在图表中作为分类变量显示，而不是连续数字
    df['seed_category'] = df['seed'].astype(str)

    # 3. 计算总体百分比提升 ( (有 - 无) / 无 * 100% )
    mean_thp_0 = df[df['mlpred'] == 0]['avg_thp'].mean()
    mean_thp_1 = df[df['mlpred'] == 1]['avg_thp'].mean()
    pct_thp = ((mean_thp_1 - mean_thp_0) / mean_thp_0) * 100

    mean_qoe_0 = df[df['mlpred'] == 0]['qoe'].mean()
    mean_qoe_1 = df[df['mlpred'] == 1]['qoe'].mean()
    pct_qoe = ((mean_qoe_1 - mean_qoe_0) / mean_qoe_0) * 100

    # 4. 设置绘图风格
    sns.set_theme(style="whitegrid")
    
    # 创建 2x2 画板
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('WiFi Bandwidth Prediction Analysis (ML vs Baseline)', fontsize=18, fontweight='bold', y=0.98)

    # --- 图表 1: 汇总的 avg_thp 箱型图 (包含百分比) ---
    sns.boxplot(data=df, x='ML_Prediction', y='avg_thp', ax=axes[0, 0], palette='Set2')
    axes[0, 0].set_title(f'Overall Average Throughput (Improvement: {pct_thp:+.2f}%)', fontsize=14, fontweight='bold', color='darkred')
    axes[0, 0].set_ylabel('Average Throughput (avg_thp)', fontsize=12)
    axes[0, 0].set_xlabel('')

    # --- 图表 2: 汇总的 qoe 箱型图 (包含百分比) ---
    sns.boxplot(data=df, x='ML_Prediction', y='qoe', ax=axes[0, 1], palette='Set2')
    axes[0, 1].set_title(f'Overall QoE (Improvement: {pct_qoe:+.2f}%)', fontsize=14, fontweight='bold', color='darkred')
    axes[0, 1].set_ylabel('Quality of Experience (qoe)', fontsize=12)
    axes[0, 1].set_xlabel('')

    # --- 图表 3: 按 nclient 分组的 avg_thp 柱状图 ---
    sns.barplot(data=df, x='nclient', y='avg_thp', hue='ML_Prediction', ax=axes[1, 0], palette='Set2', errorbar='sd')
    axes[1, 0].set_title('Average Throughput by Number of Clients', fontsize=14)
    axes[1, 0].set_ylabel('Average Throughput (avg_thp)', fontsize=12)
    axes[1, 0].set_xlabel('Number of Clients (nclient)', fontsize=12)

    # --- 图表 4: 按 seed 分组的 avg_thp 柱状图 ---
    sns.barplot(data=df, x='seed_category', y='avg_thp', hue='ML_Prediction', ax=axes[1, 1], palette='Set2', errorbar='sd')
    axes[1, 1].set_title('Average Throughput by Seed', fontsize=14)
    axes[1, 1].set_ylabel('Average Throughput (avg_thp)', fontsize=12)
    axes[1, 1].set_xlabel('Seed', fontsize=12)

    # 优化布局并保存
    plt.tight_layout()
    plt.savefig(OUTPUT_FILE, dpi=300, bbox_inches='tight')
    print(f"绘图成功！图表已保存至: {OUTPUT_FILE}")

    # 5. 在终端打印详细的统计对比信息
    print("\n" + "="*50)
    print("             总体性能指标评估表             ")
    print("="*50)
    summary = df.groupby('ML_Prediction')[['avg_thp', 'qoe']].mean().round(4)
    print(summary)
    print("-" * 50)
    print(f"吞吐量 (avg_thp) 提升比例: {pct_thp:+.2f}%")
    print(f"体验质量 (qoe) 提升比例:   {pct_qoe:+.2f}%")
    print("="*50 + "\n")

if __name__ == '__main__':
    main()