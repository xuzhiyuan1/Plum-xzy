#!/bin/bash

export CORE_COUNT=1

# 测试参数设置
declare -a seeds=(777)
declare -a nclients=(5)
declare -a simTime=(30)
declare -a policies=(0 2)  # 0 for vanilla, 2 for plum
declare -a qoeType=(2)
declare -a rounds=(test1 test2)

export NS3_VER="3.37"
export CURRENT_DIR=$PWD
export RESULT_DIR=${CURRENT_DIR}/results
export NS3_DIR=$PWD/../emulation/ns-allinone-${NS3_VER}/ns-${NS3_VER}

# 创建统一结果目录
mkdir -p ${RESULT_DIR}/practicable

run_ns3() {
    policy=$1
    seed=$2
    nclient=$3
    simt=$4
    qoet=$5
    round=$6
    
    # 策略名
    if [ $policy -eq 0 ]; then
        policy_name="vanilla"
    else
        policy_name="plum"
    fi
    
    output_file="${RESULT_DIR}/practicable/${policy_name}_seed${seed}_${round}.log"
    bandwidth_file="${RESULT_DIR}/practicable/${policy_name}_seed${seed}_${round}-bandwidth"
    
    echo "Running policy: $policy_name, nclient: $nclient, seed: $seed, qoeType: $qoet, round: $round..."
    
    # 运行ns3并直接输出到文件
    NS_GLOBAL_VALUE="RngRun=$seed" ./ns3 run "scratch/test_wifi_channel --mode=sfu --logLevel=1 --simTime=${simt} --policy=${policy} --nClient=${nclient} --qoeType=${qoet}" > $output_file 2>&1

    # 提取带宽相关日志
    grep '\[VcaClient\]\[Node' "$output_file" | grep 'UpdateBitrate' > "$bandwidth_file"
}

# 编译ns3
cd $NS3_DIR
./ns3

export -f run_ns3

parallel -j${CORE_COUNT} run_ns3 ::: ${policies[@]} ::: ${seeds[@]} ::: ${nclients[@]} ::: ${simTime} ::: ${qoeType[@]} ::: ${rounds[@]}

echo "Analysis complete. Results are in ${RESULT_DIR}/practicable directory."

cd ../../../evaluation
echo "当前脚本切换到路径：$(pwd)"

# 比较plum1和plum2
bandwidth_plum1="results/practicable/plum_seed777_test1-bandwidth"
bandwidth_plum2="results/practicable/plum_seed777_test2-bandwidth"
echo "==== 比较plum_seed777_test1-bandwidth 与 plum_seed777_test2-bandwidth 带宽日志 ===="
diff_output=$(diff -u "$bandwidth_plum1" "$bandwidth_plum2" | awk '/^@@/{c++} c<=5' | grep -E '^[+-]' | head -n 10)
if [ -z "$diff_output" ]; then
    echo "没有区别"
else
    echo "$diff_output"
fi

# 比较vanilla1和vanilla2
bandwidth_vanilla1="results/practicable/vanilla_seed777_test1-bandwidth"
bandwidth_vanilla2="results/practicable/vanilla_seed777_test2-bandwidth"
echo "==== 比较vanilla_seed777_test1-bandwidth 与 vanilla_seed777_test2-bandwidth 带宽日志 ===="
diff_output=$(diff -u "$bandwidth_vanilla1" "$bandwidth_vanilla2" | awk '/^@@/{c++} c<=5' | grep -E '^[+-]' | head -n 10)
if [ -z "$diff_output" ]; then
    echo "没有区别"
else
    echo "$diff_output"
fi

# 比较plum1和vanilla1
echo "==== 比较plum_seed777_test1-bandwidth 与 vanilla_seed777_test1-bandwidth 带宽日志 ===="
diff_output=$(diff -u "$bandwidth_plum1" "$bandwidth_vanilla1" | awk '/^@@/{c++} c<=5' | grep -E '^[+-]' | head -n 10)
if [ -z "$diff_output" ]; then
    echo "没有区别"
else
    echo "$diff_output"
fi
