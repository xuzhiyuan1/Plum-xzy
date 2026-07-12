import socket
import struct
import torch
torch.set_num_threads(1)
import numpy as np
import sys
import os
import threading

# ==========================================
# 1. 路径修复：动态寻找依赖和模型
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, "../encoder"))
sys.path.append(os.path.join(current_dir, ".."))

try:
    from model import BandwidthEncoder 
    from bocd.bocd import infer_run_lengths
except ImportError as e:
    print(f"导入失败，请检查路径: {e}")
    sys.exit(1)

# ==========================================
# 2. 处理单个 Client 的线程函数
# ==========================================
def handle_client(conn, addr, model, DEVICE, SCALE_FACTOR, SEQ_LEN):
    print(f"✅ ns-3 Client connected from {addr}!")
    try:
        while True:
            # 接收 10 个 double (80 字节)
            data = b''
            while len(data) < 800:
                packet = conn.recv(800 - len(data))
                if not packet:
                    break
                data += packet
                
            if len(data) < 800:
                break
            
            history_bw = struct.unpack(f'{SEQ_LEN}d', data)
            obs_np = np.array(history_bw, dtype=np.float32)

            try:
                inferred_rl = infer_run_lengths(obs_np)
            except:
                inferred_rl = np.zeros_like(obs_np)
                
            obs_norm = obs_np / SCALE_FACTOR

            inp_obs = torch.tensor(obs_norm, dtype=torch.float32).unsqueeze(0).unsqueeze(-1).to(DEVICE)
            inp_rl = torch.tensor(inferred_rl, dtype=torch.long).unsqueeze(0).to(DEVICE)
            
            mask = (torch.triu(torch.ones(SEQ_LEN, SEQ_LEN)) == 1).transpose(0, 1)
            mask = mask.float().masked_fill(mask == 0, float('-inf')).masked_fill(mask == 1, float(0.0)).to(DEVICE)

            with torch.no_grad():
                outputs = model(inp_obs, inp_rl, src_mask=mask)
                pred_bw_phys = outputs['recon_bw'][0, -1, 0].item() * SCALE_FACTOR 

            # 打包 1 个 double 发回 C++
            conn.send(struct.pack('d', pred_bw_phys))

    except Exception as e:
        print(f"❌ Connection from {addr} closed or error: {e}")
    finally:
        conn.close()
        print(f"👋 Client {addr} disconnected.")


# ==========================================
# 3. 主程序：启动多线程监听
# ==========================================
def start_inference_server():
    DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    SCALE_FACTOR = 20.0
    SEQ_LEN = 100

    model_path = os.path.join(current_dir, "../encoder/finetuned_epoch_10.pth")
    if not os.path.exists(model_path):
        print(f"找不到模型文件: {model_path}")
        sys.exit(1)

    model = BandwidthEncoder(input_dim=1, d_model=64, nhead=4, num_layers=3).to(DEVICE)
    model.load_state_dict(torch.load(model_path, map_location=DEVICE))
    model.eval()
    print(f"🚀 Transformer Loaded from {model_path}")

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('127.0.0.1', 9999)) 
    
    # 允许排队等待的连接数增加到 10，防止并发请求被拒绝
    server_socket.listen(100) 
    print("⏳ Waiting for ns-3 clients to connect on port 9999...")

    try:
        while True:
            # 不断接收新客人的连接
            conn, addr = server_socket.accept()
            # 每来一个客人，就开一个新线程去接待它
            client_thread = threading.Thread(
                target=handle_client, 
                args=(conn, addr, model, DEVICE, SCALE_FACTOR, SEQ_LEN)
            )
            client_thread.daemon = True # 主程序退出时自动关闭子线程
            client_thread.start()
            
    except KeyboardInterrupt:
        print("\n🛑 Server manually shut down by user.")
    finally:
        server_socket.close()

if __name__ == "__main__":
    start_inference_server()