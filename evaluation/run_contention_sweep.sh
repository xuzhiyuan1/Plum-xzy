#!/bin/bash
export CORE_COUNT=6
declare -a seeds=(777 42 55 6 7)
declare -a nclients=(6 8)
SIMT=1200; QOET=2
export CURRENT_DIR=$PWD
export RESULT_DIR=${CURRENT_DIR}/results
export NS3_DIR=$PWD/../emulation/ns-allinone-3.37/ns-3.37
OUT=${RESULT_DIR}/result_contention_sweep.txt
CSV=${RESULT_DIR}/result_contention_sweep.csv
export OUT CSV SIMT QOET
echo "policy, nclient, seed, avg_thp, min_thp, qoe" > $CSV
run_pt() {
    policy=$1; nclient=$2; seed=$3
    ns3_output=$(NS_GLOBAL_VALUE="RngRun=$seed" ./ns3 run "scratch/test_wifi_channel --mode=sfu --logLevel=0 --simTime=${SIMT} --policy=${policy} --nClient=${nclient} --qoeType=${QOET}" 2>&1)
    avg_thp=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -a)
    min_thp=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -m)
    qoe=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -q ${QOET})
    echo "At policy: $policy, nclient: $nclient, seed: $seed" >> $OUT
    echo "$ns3_output" >> $OUT
    echo "$policy, $nclient, $seed, $avg_thp, $min_thp, $qoe" >> $CSV
    echo "done p=$policy n=$nclient s=$seed"
}
export -f run_pt
cd $NS3_DIR
./ns3 >/dev/null 2>&1
rm -f $OUT
for cn in "${nclients[@]}"; do
    pkill -9 -f "solver.py" 2>/dev/null || true
    sleep 2
    python3 ${CURRENT_DIR}/../scripts/solver/solver.py -n $cn > ${CURRENT_DIR}/solver_sweep_n${cn}.log 2>&1 &
    sleep 3
    parallel --line-buffer -j${CORE_COUNT} run_pt ::: 0 2 ::: $cn ::: "${seeds[@]}"
done
pkill -9 -f "solver.py" 2>/dev/null || true
echo "SWEEPDONE"
