#!/bin/bash
export CORE_COUNT=5
declare -a seeds=(777 42 55 6 7 20 84 234 1000 81)
N=3; SIMT=1200; QOET=2; OBS=1
export CURRENT_DIR=$PWD
export RESULT_DIR=${CURRENT_DIR}/results
export NS3_DIR=$PWD/../emulation/ns-allinone-3.37/ns-3.37
OUT=${RESULT_DIR}/result_green_n3_arms.csv
export OUT OBS N SIMT QOET
run_ve() {
    seed=$1
    ns3_output=$(NS_GLOBAL_VALUE="RngRun=$seed" ./ns3 run "scratch/test_wifi_channel --mode=sfu --logLevel=0 --simTime=${SIMT} --policy=0 --nClient=${N} --qoeType=${QOET} --mlpred=0 --green=1 --obsdeliv=${OBS}" 2>&1)
    avg_thp=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -a)
    min_thp=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -m)
    tail_thp=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -t)
    qoe=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -q ${QOET})
    avg_rtt=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -r)
    rtt90=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -r90)
    echo "AE, 0, 1, $OBS, $N, $seed, $QOET, $avg_thp, $min_thp, $tail_thp, $qoe, $avg_rtt, $rtt90" >> $OUT
    echo "done AE seed=$seed"
}
export -f run_ve
cd $NS3_DIR
pkill -9 -f "solver.py" 2>/dev/null || true
sleep 2
GREEN_CFG=${CURRENT_DIR}/../scripts/solver/green_cfg_vanilla.json python3 ${CURRENT_DIR}/../scripts/solver/solver.py -n $N > ${CURRENT_DIR}/solver_armAE.log 2>&1 &
sleep 3
parallel --line-buffer -j${CORE_COUNT} run_ve ::: "${seeds[@]}"
pkill -9 -f "solver.py" 2>/dev/null || true
echo "AEDONE"
