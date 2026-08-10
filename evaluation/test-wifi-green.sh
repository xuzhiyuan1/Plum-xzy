#!/bin/bash
# Green-PLUM 闭环主实验 (A2): vanilla(policy0) vs plum(policy2) vs green(policy2+--green)
export CORE_COUNT=${CORE_COUNT:-6}
declare -a seeds=(777 42 55 6 7)
declare -a nclients=(6)
declare simTime=(1200)
declare -a combos=("0_0" "2_0" "2_1")   # policy_green
declare -a qoeTypes=(2)

export filename_prefix="result_green_closedloop_v2"
export NS3_VER="3.37"
export CURRENT_DIR=$PWD
export RESULT_DIR=${CURRENT_DIR}/results
export NS3_DIR=$PWD/../emulation/ns-allinone-${NS3_VER}/ns-${NS3_VER}
export SOLVER_SCRIPT="${CURRENT_DIR}/../scripts/solver/solver.py"
export GREEN_CFG="${CURRENT_DIR}/../scripts/solver/green_cfg.json"

run_ns3_green() {
    combo=$1; seed=$2; nclient=$3; simt=$4; qoet=$5
    policy=${combo%_*}; green=${combo#*_}
    mlpred=0
    filename=${RESULT_DIR}/${filename_prefix}
    output_file_clean=${filename}.csv
    log_dir="${RESULT_DIR}/fulllog_green"; mkdir -p "$log_dir"
    full_log_file="${log_dir}/${filename_prefix}_p${policy}_g${green}_s${seed}_n${nclient}.txt"

    echo "=== policy=$policy green=$green seed=$seed n=$nclient ==="
    NS_GLOBAL_VALUE="RngRun=$seed" ./ns3 run "scratch/test_wifi_channel --mode=sfu --logLevel=1 --simTime=${simt} --policy=${policy} --nClient=${nclient} --qoeType=${qoet} --mlpred=${mlpred} --green=${green} --obsdeliv=1" > "$full_log_file" 2>&1
    ns3_output=$(NS_GLOBAL_VALUE="RngRun=$seed" ./ns3 run "scratch/test_wifi_channel --mode=sfu --logLevel=0 --simTime=${simt} --policy=${policy} --nClient=${nclient} --qoeType=${qoet} --mlpred=${mlpred} --green=${green} --obsdeliv=1" 2>&1)

    avg_thp=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -a)
    min_thp=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -m)
    tail_thp=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -t)
    qoe=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -q ${qoet})
    avg_rtt=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -r)
    rtt90=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -r90)
    echo "$policy, $green, $nclient, $seed, $qoet, $avg_thp, $min_thp, $tail_thp, $qoe, $avg_rtt, $rtt90" >> $output_file_clean
}

cd $NS3_DIR
./ns3
export -f run_ns3_green
mkdir -p ${RESULT_DIR}
echo "policy, green, nclient, seed, qoeType, avg_thp, min_thp, tail_thp, qoe, avg_rtt, rtt90" > ${RESULT_DIR}/${filename_prefix}.csv

for current_n in "${nclients[@]}"; do
    pkill -9 -f "solver.py" 2>/dev/null || true
    sleep 2
    echo "Starting green-capable solver n=${current_n} (GREEN_CFG=$GREEN_CFG)"
    GREEN_CFG=$GREEN_CFG python3 ${SOLVER_SCRIPT} -n $current_n > ${CURRENT_DIR}/solver_green_n${current_n}.log 2>&1 &
    sleep 3
    parallel --line-buffer --eta -j${CORE_COUNT} run_ns3_green ::: ${combos[@]} ::: ${seeds[@]} ::: $current_n ::: ${simTime} ::: ${qoeTypes[@]}
done
pkill -9 -f "solver.py" 2>/dev/null || true
echo "ALLDONE"
