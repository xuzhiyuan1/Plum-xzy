#!/bin/bash

export CORE_COUNT=16

declare -a seeds=(1 2 3 4 5 129 777 12946)
# declare -a seeds=(777)
declare -a nclients=(3 4 5 6 7 8 9 10 12)
# declare -a nclients=(3 4 5)
declare -a serverBtlneck=(100 300 500 1000)
# declare -a serverBtlneck=(100)
declare simTime=(120)
declare -a policies=(2) 
declare -a traceModes=(1)  
declare -a datasets=(0)    # 0=TR_GAME, 1=TR_RESTAURANT
declare -a mlpreds=(0 1)

export baseline_policy=0
export filename_prefix="result_trace_driven"

export NS3_VER="3.37"
export CURRENT_DIR=$PWD
export RESULT_DIR=${CURRENT_DIR}/results
export NS3_DIR=$PWD/../emulation/ns-allinone-${NS3_VER}/ns-${NS3_VER}

export SOLVER_SCRIPT="${CURRENT_DIR}/../scripts/solver/solver.py"

run_ns3_independent() {
    policy=$1
    seed=$2
    nclient=$3
    dataset=$4
    serverbw=$5
    simt=$6
    tracemode=$7
    mlpred=$8
    
    filename=${RESULT_DIR}/${filename_prefix}_independent
    output_file=${filename}.txt
    output_file_clean=${filename}.csv
    
    log_dir="${RESULT_DIR}/fulllog"
    mkdir -p "$log_dir"
    full_log_file="${log_dir}/${filename_prefix}_full_log_tm${tracemode}_ml${mlpred}_s${seed}_n${nclient}_d${dataset}_bw${serverbw}.txt"    
    echo "======================================================================"
    echo "At traceMode: $tracemode, nclient: $nclient, seed: $seed, serverBtlneck: $serverbw..."

    # ---------------- 第一次运行: 完整日志 ----------------
    # echo "▶️ [Run 1/2] Executing NS-3 (logLevel=1)..."
    # NS_GLOBAL_VALUE="RngRun=$seed" ./ns3 run "scratch/test_half_duplex --mode=sfu --logLevel=1 --simTime=${simt} --policy=${policy} --nClient=${nclient} --varyBw=1 --traceMode=${tracemode} --seed=${seed} --dataset=${dataset} --serverBtl=${serverbw} --mlpred=${mlpred}" > "$full_log_file" 2>&1
    # echo "✅ [Run 1/2] Done! Full log saved to $full_log_file"

    # ---------------- 第二次运行: 解析结果 (为了加速，直接跑 logLevel=0 即可) ----------------
    # echo "▶️ [Run 2/2] Executing NS-3 (logLevel=0)..."
    ns3_output=$(NS_GLOBAL_VALUE="RngRun=$seed" ./ns3 run "scratch/test_half_duplex --mode=sfu --logLevel=0 --simTime=${simt} --policy=${policy} --nClient=${nclient} --varyBw=1 --traceMode=${tracemode} --seed=${seed} --dataset=${dataset} --serverBtl=${serverbw} --mlpred=${mlpred}" 2>&1)
    
    # ---------------- 处理结果 ----------------
    avg_thp=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -a)
    min_thp=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -m)
    tail_thp=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -t)
    
    echo "At traceMode: $tracemode, mlpred: $mlpred, nclient: $nclient, seed: $seed, serverBtlneck: $serverbw" >> $output_file
    echo "$ns3_output" >> $output_file
    
    # 【修改 3】：CSV 输出中把 tracemode 提到前面
    echo "$tracemode, $mlpred, $nclient, $seed, $dataset, $serverbw, $avg_thp, $min_thp, $tail_thp" >> $output_file_clean
}

cd $NS3_DIR
./ns3

export -f run_ns3_independent

mkdir -p ${RESULT_DIR}

# 【修改 4】：CSV 表头更新
echo "traceMode, mlpred, nclient, seed, dataset, serverBtlneck, avg_thp, min_thp, tail_thp" > ${RESULT_DIR}/${filename_prefix}_independent.csv

for current_n in "${nclients[@]}"; do
    echo "=========================================================="
    echo "🌟 PREPARING ENVIRONMENT FOR nclient = $current_n"
    echo "=========================================================="

    pkill -9 -f "solver.py" 2>/dev/null || true
    sleep 2

    # 如果 policy=0 其实不需要 Python Solver，但为了防止偶尔测试 policy=2，这里留着也无妨
    echo "🚀 Starting Solver for nclient=${current_n}..."
    python3 ${SOLVER_SCRIPT} -n $current_n > ${CURRENT_DIR}/solver_debug_n${current_n}.log 2>&1 &
    sleep 3 

    # 替换变量顺序，注入 tracemodes
    parallel --line-buffer --eta -j${CORE_COUNT} run_ns3_independent ::: ${policies[@]} ::: ${seeds[@]} ::: $current_n ::: ${datasets[@]} ::: ${serverBtlneck[@]} ::: ${simTime} ::: ${traceModes[@]} ::: ${mlpreds[@]}

    echo "✅ Finished all parallel tasks for nclient = $current_n"
done

pkill -9 -f "solver.py" 2>/dev/null || true
echo "🎉 ALL BATCH EXPERIMENTS COMPLETED!"