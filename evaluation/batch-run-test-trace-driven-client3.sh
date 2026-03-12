#!/bin/bash

export CORE_COUNT=20

declare -a seeds=(777)
declare -a nclients=(15)
declare -a serverBtlneck=(300)
declare simTime=(60)
declare -a policies=(0 1) #0 for vanilla, 1 for Plum
declare -a ulprops=(0.8)
declare -a ackmaxcounts=(16)
declare -a datasets=(1) #0 for TR_GAME, 1 for TR_RESTAURANT

export baseline_policy=0
export filename_prefix="result_trace_driven_client"


export NS3_THROUGHPUT_REGEX="\[VcaClient\]\[Result\] Throughput= ([0-9\.e\-]+)"

export NS3_VER="3.37"
export CURRENT_DIR=$PWD
export RESULT_DIR=${CURRENT_DIR}/results
export NS3_DIR=$PWD/../emulation/ns-allinone-${NS3_VER}/ns-${NS3_VER}

run_ns3_independent() {
    policy=$1
    seed=$2
    nclient=$3
    dataset=$4
    serverbw=$5
    simt=$6
    filename=${RESULT_DIR}/${filename_prefix}
    output_file=${filename}.txt
    output_file_clean=${filename}.csv
    echo At policy: $policy, nclient: $nclient, seed: $seed, output_file: $filename.txt/csv...
    ns3_output=$(NS_GLOBAL_VALUE="RngRun=$seed" ./ns3 run "scratch/test_half_duplex --mode=sfu --logLevel=0 --simTime=${simt} --policy=0 --nClient=${nclient} --varyBw --traceMode=${policy} --seed=${seed} --dataset=${dataset} --serverBtl=${serverbw}" 2>&1)
    avg_thp=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -a)
    min_thp=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -m)
    tail_thp=$(python3 ${CURRENT_DIR}/log-process.py -l "${ns3_output}" -t)
    
    # output to file
    # dirty output
    echo At policy: $policy, nclient: $nclient, seed: $seed >> $output_file
    echo $ns3_output >> $output_file
    # clean output
    echo $policy, $nclient, $seed, $dataset, $serverbw, $avg_thp, $min_thp, $tail_thp >> $output_file_clean
}


# compile first
cd $NS3_DIR
./ns3

export -f run_ns3_independent


# ======= Independent Topology =======
#      ======= Vanilla & Plum ========
echo "policy, nclient, seed, dataset, serverBtlneck, avg_thp, min_thp, tail_thp" > ${RESULT_DIR}/${filename_prefix}.csv

parallel -j${CORE_COUNT} run_ns3_independent ::: ${policies[@]} ::: ${seeds[@]} ::: ${nclients[@]} ::: ${datasets[@]} ::: ${serverBtlneck[@]} ::: ${simTime}





cd ../../../evaluation
echo "当前脚本切换到路径：$(pwd)"

# 结果分析
csv_file="results/result_trace_driven_client.csv"

if [ -f "$csv_file" ]; then
  echo ""
  echo "==== result_trace_driven_client.csv 分析 ===="
  # 获取所有不同的nclient值
  nclients=$(awk -F',' 'NR>1{print $2}' "$csv_file" | sort -n | uniq)
  for ncli in $nclients; do
    echo ""
    echo "nclient=($ncli)时："
    # Vanilla (policy=0)
    vanilla_line=$(awk -F',' -v ncli="$ncli" '$1==0 && $2==ncli {print $0}' "$csv_file" | head -n 1)
    if [ -n "$vanilla_line" ]; then
      avg_thp=$(echo $vanilla_line | awk -F',' '{print $6}')
      printf "Vanilla（policy=0）时 Average_throuput = %s kbps\n" "$avg_thp"
    else
      echo "Vanilla（policy=0）时 Average_throuput = 0.00kbps"
    fi
    # Plum (policy=1)
    plum_line=$(awk -F',' -v ncli="$ncli" '$1==1 && $2==ncli {print $0}' "$csv_file" | head -n 1)
    if [ -n "$plum_line" ]; then
      avg_thp=$(echo $plum_line | awk -F',' '{print $6}')
      printf "Plum（policy=1）时 Average_throuput = %s kbps\n" "$avg_thp"
    else
      echo "Plum（policy=1）时 Average_throuput = 0.00kbps"
    fi
  done
else
  echo "未找到csv结果文件：$csv_file"
fi
