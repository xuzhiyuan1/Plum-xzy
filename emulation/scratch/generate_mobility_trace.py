import random

def generate_trace(filename="mobility_trace.csv", total_time=1200):
    with open(filename, 'w') as f:
        f.write("# Time(s), X(m), Y(m)\n")
        
        current_time = 0.0
        # 将 Y 固定在 5.0，只改变 X 模拟距离远近 (5m ~ 45m)
        curr_x = round(random.uniform(5.0, 15.0), 1)
        curr_y = 5.0 
        
        f.write(f"{current_time:.3f}, {curr_x}, {curr_y}\n")
        
        while current_time < total_time:
            # 缩短平稳期，让 BBR 疲于奔命 (10s ~ 25s)
            duration = random.uniform(10.0, 25.0)
            stable_end_time = current_time + duration
            
            if stable_end_time >= total_time:
                f.write(f"{total_time:.3f}, {curr_x}, {curr_y}\n")
                break
                
            # 写入平稳期的结束点
            f.write(f"{stable_end_time:.3f}, {curr_x}, {curr_y}\n")
            
            # === 核心：对齐训练集的 Transition Physics ===
            # 20% Instant, 40% Gradual, 40% Overshoot
            trans_type = random.choices(['instant', 'gradual', 'overshoot'], weights=[0.2, 0.4, 0.4])[0]
            
            new_x = round(random.uniform(5.0, 45.0), 1)
            
            if trans_type == 'instant':
                # 瞬间突变 (0.001秒瞬移)
                f.write(f"{(stable_end_time + 0.001):.3f}, {new_x}, {curr_y}\n")
                current_time = stable_end_time + 0.001
                
            elif trans_type == 'gradual':
                # 缓慢爬坡/下降 (花 2 到 6 秒慢慢走过去，NS-3会自动线性插值)
                ramp_time = random.uniform(2.0, 6.0)
                f.write(f"{(stable_end_time + ramp_time):.3f}, {new_x}, {curr_y}\n")
                current_time = stable_end_time + ramp_time
                
            elif trans_type == 'overshoot':
                # 超调 (先冲过头，再退回来)
                peak_time = random.uniform(1.0, 2.5)
                settle_time = random.uniform(1.5, 3.5)
                
                # 计算超调极值点 (比目标点再多冲 30%~50%)
                overshoot_margin = (new_x - curr_x) * random.uniform(0.3, 0.5)
                peak_x = round(new_x + overshoot_margin, 1)
                
                # 限制在物理范围内
                peak_x = max(2.0, min(peak_x, 50.0))
                
                # 写入超调冲刺点
                f.write(f"{(stable_end_time + peak_time):.3f}, {peak_x}, {curr_y}\n")
                # 写入回落稳定点
                f.write(f"{(stable_end_time + peak_time + settle_time):.3f}, {new_x}, {curr_y}\n")
                
                current_time = stable_end_time + peak_time + settle_time
                
            curr_x = new_x

    print(f"✅ 成功生成移动轨迹: {filename}")

if __name__ == "__main__":
    generate_trace()