#!/bin/bash

# 【注意】因为加入了两次运行，且有报错风险，并发可以稍微调小一点排查问题
export CORE_COUNT=8

declare -a seeds=(777 42 55 6 7 20 84 234 1000 81)
# declare -a seeds=(777 42 55)
declare -a nclients=(3 4 5 6 7 8 9 10 11 12)
declare simTime=(1200)
declare -a policies=(2)    # 0=VANILLA, 2=PLUM
declare -a qoeTypes=(2)      # 默认用 2 (sqr_convex)
declare -a mlpreds=(0 1)     # 0=BBR, 1=Transformer

export filename_prefix="result_channel_model"

export NS3_VER="3.37"
export CURRENT_DIR=$PWD
export RESULT_DIR=${CURRENT_DIR}/results
export NS3_DIR=$PWD/../emulation/ns-allinone-${NS3_VER}/ns-${NS3_VER}

export SOLVER_SCRIPT="${CURRENT_DIR}/../scripts/solver/solver.py"

run_ns3_channel() {
    policy=$1
    seed=$2
    nclient=$3
    simt=$4
    qoet=$5
    mlpred=$6
    
    filename=${RESULT_DIR}/${filename_prefix}_independent
    output_file=${filename}.txt
    output_file_clean=${filename}.csv
    
    # 建立 fulllog 子目录存储每次运行的完整日志
    log_dir="${RESULT_DIR}/fulllog"
    mkdir -p "$log_dir"
    full_log_file="${log_dir}/${filename_prefix}_full_log_p${policy}_ml${mlpred}_s${seed}_n${nclient}_qoe${qoet}.txt"
    
    echo "======================================================================"
    echo "At policy: $policy, mlpred: $mlpred, nclient: $nclient, seed: $seed..."

    # ---------------- 第一次运行: 完整日志 (用来抓 Bug) ----------------
    echo "▶️ [Run 1/2] Executing NS-3 (logLevel=1)..."
    NS_GLOBAL_VALUE="RngRun=$seed" ./ns3 run "scratch/test_wifi_channel --mode=sfu --logLevel=1 --simTime=${simt} --policy=${policy} --nClient=${nclient} --qoeType=${qoet} --mlpred=${mlpred}" > "$full_log_file" 2>&1
    echo "✅ [Run 1/2] Done! Full log saved to $full_log_file"

    # ---------------- 第二次运行: 解析结果 (纯净版) ----------------
    echo "▶️ [Run 2/2] Executing NS-3 (logLevel=0)..."
    ns3_output=$(NS_GLOBAL_VALUE="RngRun=$seed" ./ns3 run "scratch/test_wifi_channel --mode=sfu --logLevel=0 --simTime=${simt} --policy=${policy} --nClient=${nclient} --qoeType=${qoet} --mlpred=${mlpred}" 2>&1)
    
    # ---------------- 解析 Log-Process 结果 ----------------
    avg_thp=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -a)
    min_thp=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -m)
    tail_thp=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -t)
    qoe=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -q ${qoet})
    avg_rtt=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -r)
    rtt90=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -r90)
    
    # 脏输出
    echo "At policy: $policy, mlpred: $mlpred, nclient: $nclient, seed: $seed, qoeType: $qoet" >> $output_file
    echo "$ns3_output" >> $output_file
    
    # 净输出 (CSV)
    echo "$policy, $mlpred, $nclient, $seed, $qoet, $avg_thp, $min_thp, $tail_thp, $qoe, $avg_rtt, $rtt90" >> $output_file_clean
}

cd $NS3_DIR
./ns3

export -f run_ns3_channel

mkdir -p ${RESULT_DIR}
# 打印 CSV 表头
echo "policy, mlpred, nclient, seed, qoeType, avg_thp, min_thp, tail_thp, qoe, avg_rtt, rtt90" > ${RESULT_DIR}/${filename_prefix}_independent.csv

# ================= 核心外层循环 (控制 Solver) =================
for current_n in "${nclients[@]}"; do
    echo "=========================================================="
    echo "🌟 PREPARING ENVIRONMENT FOR nclient = $current_n"
    echo "=========================================================="

    # 1. 暴力扫尾清理残留进程
    pkill -9 -f "solver.py" 2>/dev/null || true
    sleep 2

    # 2. 为当前 nclient 启动多线程版 Solver
    echo "🚀 Starting Solver for nclient=${current_n}..."
    python3 ${SOLVER_SCRIPT} -n $current_n > ${CURRENT_DIR}/solver_debug_n${current_n}.log 2>&1 &
    sleep 3 

    # 3. 启动并发任务 (使用 --line-buffer 防止输出卡死)
    parallel --line-buffer --eta -j${CORE_COUNT} run_ns3_channel ::: ${policies[@]} ::: ${seeds[@]} ::: $current_n ::: ${simTime} ::: ${qoeTypes[@]} ::: ${mlpreds[@]}

    echo "✅ Finished all parallel tasks for nclient = $current_n"
done

# 大扫除
pkill -9 -f "solver.py" 2>/dev/null || true
echo "🎉 ALL BATCH EXPERIMENTS COMPLETED!"