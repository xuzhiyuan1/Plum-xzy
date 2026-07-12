#!/usr/bin/env python3.9

import argparse
import math
import numpy as np
import scipy.optimize as opt
import matplotlib.pyplot as plt
import socket
import struct
import threading
from enum import Enum
from struct import unpack


class QoeType(Enum):
    lin = 0
    log = 1
    sqr_concave = 3
    sqr_convex = 2


def qoe(dl_bw, params):
    qoe = 0.0
    if params[2] == "lin":
        qoe = params[3] * dl_bw
    elif params[2] == "sqr_concave" or params[2] == "sqr_convex":
        qoe = (params[3] * dl_bw + params[4]) * dl_bw
    elif params[2] == "log":
        qoe = params[3] * math.log(dl_bw + 1)

    return qoe


def calc_avg_qoe(qoes):
    avg_qoe = 0.0
    if len(qoes) == 0:
        return avg_qoe
    avg_qoe = np.sum(qoes) / len(qoes)
    return avg_qoe


def calc_std_dev_qoe(avg_qoe, qoes):
    std_dev_qoe = 0.0
    if len(qoes) == 0:
        return std_dev_qoe
    for i in range(len(qoes)):
        std_dev_qoe += (qoes[i] - avg_qoe) ** 2
    std_dev_qoe /= len(qoes)
    std_dev_qoe = std_dev_qoe ** 0.5
    return std_dev_qoe


def utility(x, args):
    rho = args[0]
    qoes = []
    for dl_bw in x:
        qoes.append(qoe(dl_bw, args))
    avg_qoe = calc_avg_qoe(qoes)
    qoe_fairness = 1 - 2 * calc_std_dev_qoe(avg_qoe, qoes)
    return (rho - 1) * avg_qoe - rho * qoe_fairness


def solve(N, B, params):
    # parameters: N users, Bi bandwidth of user i, Bmax maximum bandwidth for the application
    # parameters: params = [rho, Bmax, QoE type, alpha, beta, v]

    B_ul_max = params[1] / params[5]

    # Constraints
    cons = [{'type': 'ineq', 'fun': lambda x: np.sum(np.minimum(
        B - x, B_ul_max * np.ones(N))) - np.max(np.minimum(B, B_ul_max * np.ones(N) + x))}]

    bnds = []
    for i in range(N):
        bnds.append((0, min(B[i], params[1])))

    x = []

    res = opt.minimize(utility, x0=np.ones(N) * params[7], constraints=tuple(
        cons), bounds=tuple(bnds), callback=x.append, args=(params), method=params[6])

    # print(res.x) # 注释掉，防止高并发时终端刷屏

    if(params[8]):
        plt.plot(x[:], [utility(x[i], params) for i in range(len(x))], 'o-')
        plt.savefig('opt-process.png')

    return res.x

# ==========================================
# 新增：单线程处理函数，处理每个 ns-3 客户端
# ==========================================
def handle_solver_client(csk, N):
    max_num = 20
    try:
        while True:
            recv_req = csk.recv(1024)
            if recv_req == b'':
                continue

            try:
                num_users, num_view, qoe_type, rst, rho, max_bitrate, qoe_func_alpha, qoe_func_beta, capacity_string = unpack(
                    '2Hil4d%ds' % (max_num * 8), recv_req)
            except struct.error:
                continue

            if rst:
                break # 收到结束信号，退出循环，释放当前 socket

            capacities = unpack('%dd' % max_num, capacity_string)[:N]

            assert(num_users == N)

            qoe_type_name = QoeType(qoe_type).name

            if max_bitrate <= 0:
                print('MaxBitrate must be positive')
                break
            if qoe_type_name not in ['lin', 'log', 'sqr_concave', 'sqr_convex']:
                print('QoeType must be one of ''lin'', ''log'', ''sqr_concave'', ''sqr_convex''')
                break
                
            if qoe_type_name == 'lin':
                qoe_func_alpha = 1.0 / max_bitrate
            elif qoe_type_name == 'log':
                qoe_func_alpha = 1.0 / math.log(max_bitrate + 1)
            elif qoe_type_name == 'sqr_concave':
                if qoe_func_alpha < 0 and qoe_func_alpha >= - 1.0 / max_bitrate / max_bitrate:
                    qoe_func_alpha = qoe_func_alpha
                else:
                    qoe_func_alpha = - 1.0 / max_bitrate / max_bitrate
                qoe_func_beta = 1.0 / max_bitrate - qoe_func_alpha * max_bitrate
            elif qoe_type_name == 'sqr_convex':
                if qoe_func_alpha > 0 and qoe_func_alpha < 1 / max_bitrate / (max_bitrate - 2):
                    qoe_func_alpha = qoe_func_alpha
                else:
                    qoe_func_alpha = 1.0 / max_bitrate / max_bitrate
                qoe_func_beta = 1.0 / max_bitrate - qoe_func_alpha * max_bitrate
                
            if num_view > num_users:
                num_view = num_users

            solution = solve(N, capacities, [
                             rho, max_bitrate, qoe_type_name, qoe_func_alpha, qoe_func_beta, num_view, 'SLSQP', 30000.0, False]).tolist()

            csk.send(struct.pack('%dd' % N, *solution))
            
    except Exception as e:
        print(f"Error handling client: {e}")
    finally:
        try:
            csk.shutdown(socket.SHUT_RDWR)
        except:
            pass
        csk.close()

# ==========================================
# 修改：服务端监听函数，使用多线程分发
# ==========================================
def socket_server(N):
    if N < 3:
        print('N must be greater than 2')
        return

    addr = ("127.0.0.1", 11996 + N)
    sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    sk.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sk.bind(addr)
    # 将排队长度设为 100，防止 20 个 ns-3 进程同时连上来时被操作系统拒绝
    sk.listen(100) 
    print(f"🚀 Multi-threaded Solver listening on port {11996 + N}, ready for 20x parallel runs...")

    try:
        while True:
            # 持续监听，收到新请求就开一个新线程去计算
            csk, c_addr = sk.accept()
            t = threading.Thread(target=handle_solver_client, args=(csk, N))
            t.daemon = True
            t.start()
    except KeyboardInterrupt:
        print("Server shutdown.")
    finally:
        sk.close()


def main():

    qoeFuncAlpha = 1.0
    qoeFuncBeta = 0.0
    numView = 25
    init_bw = 100.0

    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--N', type=int, default=3,
                        help='number of users')
    parser.add_argument('-s', '--Server', action='store_false',
                        default=True, help='run as a socket server')
    parser.add_argument('-b', '--Bandwidth', nargs='+',
                        default=[10, 10, 10], help='available bandwidth for each users path')
    parser.add_argument('-r', '--Rho', type=float, default=0.5,
                        help='rho in the utility function')
    parser.add_argument('-m', '--MaxBitrate', type=float,
                        default=10.0, help='maximum bitrate for the application')
    parser.add_argument('-q', '--QoeType', type=str, default='lin',
                        help='type of the QoE function, to choose from [''lin'', ''log'', ''sqr_concave'', ''sqr_convex'']')
    parser.add_argument('-a', '--QoeFuncAlpha', type=float,
                        default=0, help='alpha in the QoE function')
    parser.add_argument('-v', '--ViewNum', type=float,
                        default=25, help='number of views')
    parser.add_argument('-p', '--Plot', action='store_true',
                        default=False, help='plot the utility function')
    parser.add_argument('-i', '--InitBandwidth', type=float,
                        default=20.0, help='initial bandwidth for the optimization')
    parser.add_argument('-t', '--Method', type=str, default='SLSQP',
                        help='method to solve the optimization problem')
    args = parser.parse_args()

    if args.N < 3:
        print('N must be greater than 2')
        return

    if args.Server:
        socket_server(args.N)
        return

    if len(args.Bandwidth) != args.N:
        print('Number of bandwidths must be equal to N')
        return
    if args.Rho <= 0 or args.Rho >= 1:
        print('Rho must be in (0,1)')
        return
    if args.ViewNum < 2:
        print('ViewNum must be greater than 1')
        return

    if args.MaxBitrate <= 0:
        print('MaxBitrate must be positive')
        return
    if args.QoeType not in ['lin', 'log', 'sqr_concave', 'sqr_convex']:
        print('QoeType must be one of ''lin'', ''log'', ''sqr_concave'', ''sqr_convex''')
        return
    if args.QoeType == 'lin':
        qoeFuncAlpha = 1.0 / args.MaxBitrate
    elif args.QoeType == 'log':
        qoeFuncAlpha = 1.0 / math.log(args.MaxBitrate + 1)
    elif args.QoeType == 'sqr_concave':
        if args.QoeFuncAlpha < 0 and args.QoeFuncAlpha >= - 1.0 / args.MaxBitrate / args.MaxBitrate:
            qoeFuncAlpha = args.QoeFuncAlpha
        else:
            qoeFuncAlpha = - 1.0 / args.MaxBitrate / args.MaxBitrate
        qoeFuncBeta = 1.0 / args.MaxBitrate - qoeFuncAlpha * args.MaxBitrate
    elif args.QoeType == 'sqr_convex':
        if args.QoeFuncAlpha > 0 and args.QoeFuncAlpha < 1 / args.MaxBitrate / (args.MaxBitrate - 2):
            qoeFuncAlpha = args.QoeFuncAlpha
        else:
            qoeFuncAlpha = 1.0 / args.MaxBitrate / args.MaxBitrate
        qoeFuncBeta = 1.0 / args.MaxBitrate - qoeFuncAlpha * args.MaxBitrate

    if args.ViewNum > args.N:
        numView = args.N
    else:
        numView = args.ViewNum

    if args.Method not in ['SLSQP', 'COBYLA']:
        print('Method must be one of ''SLSQP'', ''COBYLA''')
        return

    params = [args.Rho, args.MaxBitrate, args.QoeType, qoeFuncAlpha,
              qoeFuncBeta, numView, args.Method, args.InitBandwidth, args.Plot]

    capacities = np.array(args.Bandwidth)
    capacities = capacities.astype(float)
    solve(args.N, capacities, params)


if __name__ == "__main__":
    main()