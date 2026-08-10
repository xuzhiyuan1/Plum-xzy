#!/bin/bash
# 三臂对照 @n=3 锚定配置: A=Vanilla(p0) B=PLUM+能耗记账(p2,green,λ=0) C=Green(p2,green,λ=1.5)
OBS=$(cat /tmp/obs_flag 2>/dev/null || echo 0)
export CORE_COUNT=5
declare -a seeds=(777 42 55 6 7 20 84 234 1000 81)
N=3; SIMT=1200; QOET=2
export CURRENT_DIR=$PWD
export RESULT_DIR=${CURRENT_DIR}/results
export NS3_DIR=$PWD/../emulation/ns-allinone-3.37/ns-3.37
export SOLVER_SCRIPT="${CURRENT_DIR}/../scripts/solver/solver.py"
OUT=${RESULT_DIR}/result_green_n3_arms.csv
echo "arm, policy, green, obsdeliv, nclient, seed, qoeType, avg_thp, min_thp, tail_thp, qoe, avg_rtt, rtt90" > $OUT
export OUT OBS N SIMT QOET

run_arm_point() {
    arm=$1; policy=$2; green=$3; seed=$4
    ns3_output=$(NS_GLOBAL_VALUE="RngRun=$seed" ./ns3 run "scratch/test_wifi_channel --mode=sfu --logLevel=0 --simTime=${SIMT} --policy=${policy} --nClient=${N} --qoeType=${QOET} --mlpred=0 --green=${green} --obsdeliv=${OBS}" 2>&1)
    avg_thp=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -a)
    min_thp=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -m)
    tail_thp=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -t)
    qoe=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -q ${QOET})
    avg_rtt=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -r)
    rtt90=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -r90)
    echo "$arm, $policy, $green, $OBS, $N, $seed, $QOET, $avg_thp, $min_thp, $tail_thp, $qoe, $avg_rtt, $rtt90" >> $OUT
    echo "done arm=$arm seed=$seed"
}
export -f run_arm_point
cd $NS3_DIR

run_one_arm() {
    arm=$1; policy=$2; green=$3; cfg=$4
    pkill -9 -f "solver.py" 2>/dev/null || true
    sleep 2
    if [ "$policy" != "0" ]; then
        GREEN_CFG=$cfg python3 $SOLVER_SCRIPT -n $N > ${CURRENT_DIR}/solver_arm_${arm}.log 2>&1 &
        sleep 3
    fi
    parallel --line-buffer -j${CORE_COUNT} run_arm_point ::: $arm ::: $policy ::: $green ::: "${seeds[@]}"
    pkill -9 -f "solver.py" 2>/dev/null || true
    echo "ARM_${arm}_DONE"
}
run_one_arm A 0 0 none
run_one_arm B 2 1 ${CURRENT_DIR}/../scripts/solver/green_cfg_lam0.json
run_one_arm C 2 1 ${CURRENT_DIR}/../scripts/solver/green_cfg_n3.json
echo "ARMSDONE"
