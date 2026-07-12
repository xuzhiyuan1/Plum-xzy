#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/applications-module.h"
#include <string.h>
#include <cstdlib>
#include "ns3/flow-monitor-helper.h"
#include "ns3/ipv4-address.h"
#include "ns3/mobility-module.h"
#include "ns3/network-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/ssid.h"
#include "ns3/yans-wifi-helper.h"
#include "ns3/videoconf-module.h"

#include <fstream>
#include <sstream>
#include <csignal>
#include <cstdlib>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("MulticastEmulation");

enum LOG_LEVEL
{
    ERROR,
    DEBUG,
    LOGIC
};

enum TRACE_MODE
{
    EVEN_SPLIT,
    UNEVEN_SPLIT
};

enum DATASET
{
    TR_GAME,
    TR_RESTAURANT
};

struct GlobalKnowledge
{
    double_t prevMaxAbw = 50;
    double_t newMaxAbw = 0;
    bool prevAmpleBwUserExist = 1;
    bool newAmpleBwUserExist = 0;
    uint32_t clientSetTraceCount = 0;
};

static GlobalKnowledge global_know;
double_t oracle_trace_bw_kbps = 0.0;

// [sharedbw] 共享半双工介质 + 诊断:两条 P2P 用真实送达量耦合成一根总带宽 C
bool g_shared_bw = false;
bool g_diag_bw = false; // 仅诊断时打印 SharedDiag(会刷屏)
bool g_pred_filter = false; // 用中位数滤波代替 Transformer 作为预测器
uint64_t g_tx_bytes[256] = {0};
uint64_t g_tx_bytes_prev[256] = {0};
static void CountTx(uint32_t idx, Ptr<const Packet> pkt) { g_tx_bytes[idx] += pkt->GetSize(); }
double_t g_observed_cap_kbps[256] = {0.0}; // [sharedbw] 发布给服务端的"实际送达总吞吐"观测(kbps),EWMA 平滑

// =========================================================================
// 🌟 跨层桥梁：用于接收应用层 (VcaServer / Python) 传来的目标协同速率
// 这两个数组对底层的物理 Trace 是透明的，它们就是“大脑”下达的命令
// =========================================================================
double_t global_ul_target_rate[50] = {0.0};
double_t global_dl_target_rate[50] = {0.0};

struct TraceElem
{
    std::string trace;
    TRACE_MODE mode;
    DATASET dataset;
    Ptr<NetDevice> ul_snd_dev;
    Ptr<NetDevice> dl_snd_dev;
    uint16_t interval;    // in ms
    double_t simStopTime; // in s
    double_t maxAppBitrateMbps;
    double_t minAppBitrateMbps;
    double_t serverBwMbps;
    uint32_t node_id;
    double_t ul_prop = 0.5;
    double_t prev_ul_bw = 0.0;
    double_t prev_dl_bw = 0.0;
    std::streampos curr_pos = std::ios::beg;
};

static inline void SplitString(const std::string &s, std::vector<std::string> &v, const std::string &c)
{
    std::string::size_type pos1, pos2;
    pos2 = s.find(c);
    pos1 = 0;
    while (std::string::npos != pos2)
    {
        v.push_back(s.substr(pos1, pos2 - pos1));
        pos1 = pos2 + c.size();
        pos2 = s.find(c, pos1);
    }
    if (pos1 != s.length())
        v.push_back(s.substr(pos1));
}

void BandwidthTrace(TraceElem elem, uint32_t n_client)
{
    Ptr<PointToPointNetDevice> ulSndDev = StaticCast<PointToPointNetDevice, NetDevice>(elem.ul_snd_dev);
    Ptr<PointToPointNetDevice> dlSndDev = StaticCast<PointToPointNetDevice, NetDevice>(elem.dl_snd_dev);
    std::ifstream traceFile;

    std::string traceLine;
    std::vector<std::string> traceData;
    std::vector<std::string> bwValue;

    traceFile.open(elem.trace);

    if (!traceFile.is_open()) {
        NS_LOG_ERROR("CRITICAL BUG: Failed to open trace file: " << elem.trace);
        std::cout << "CRITICAL BUG: Failed to open trace file: " << elem.trace << std::endl;
        exit(1); 
    }

    traceFile.seekg(elem.curr_pos);
    if (elem.curr_pos == std::ios::beg && !traceFile.eof() && elem.dataset == TR_GAME)
    {
        std::getline(traceFile, traceLine); // skip the first line
    }
    std::getline(traceFile, traceLine);
    elem.curr_pos = traceFile.tellg();

    NS_LOG_DEBUG("[BandwidthTrace] Reading File: " << elem.trace 
              << " | Raw Line Content: '" << traceLine << "'");
              
    if (traceLine.find('.') == std::string::npos)
    {
        traceFile.close();
        return;
    }

    traceData.clear();
    double_t total_bw = 600, ul_bw = 300, dl_bw = 300;
    if (elem.dataset == TR_GAME)
    {
        SplitString(traceLine, traceData, ",");
        total_bw = std::stod(traceData[2]) * 1.5;
    }
    else if (elem.dataset == TR_RESTAURANT)
    {
        SplitString(traceLine, traceData, " ");
        SplitString(traceData[0], bwValue, "Mbps");
        total_bw = std::stod(bwValue[0]);
    }

    NS_LOG_INFO("elem.mode=" << elem.mode << " total_bw: " << total_bw << "Mbps");

    // ==========================================
    // 🚀 核心修改：无情的水管工，严格执行大脑的协同指令！
    // 物理层看不见 BBR，看不见 ML。它只认应用层传下来的比例，按比例切真实总带宽。
    // ==========================================
    double_t ul_target = global_ul_target_rate[elem.node_id];
    double_t dl_target = global_dl_target_rate[elem.node_id];
    double_t total_demand = ul_target + dl_target;
    double_t effective_total_bw = total_bw;

    if (total_demand > 0.001) 
    {
        // 【杀手锏逻辑】：如果算法 (Plum-) 因为预测滞后，以为带宽还很大，
        // 导致下达的 target_rate 总和大于当前的真实物理带宽...
        if (total_demand > total_bw * 1.1) // 容忍 10% 的 BBR 探测波动
        {
            // 真实 WiFi 效应：需求超出越多，碰撞越激烈，真实能发出去的吞吐量越低！
            double_t overload_ratio = total_demand / total_bw;
            
            // 惩罚公式：过载 2 倍，带宽减半。最低惩罚到总带宽的 20%
            effective_total_bw = total_bw / overload_ratio; 
            effective_total_bw = std::max(effective_total_bw, total_bw * 0.2);
            
            // NS_LOG_INFO("💥 [Overload Penalty] Demand: " << total_demand 
            //           << " > Actual: " << total_bw 
            //           << " -> Effective Bw crashed to: " << effective_total_bw);
        }

        // 使用受惩罚后的“有效总带宽”进行切分
        double_t alloc_ratio = ul_target / total_demand;
        ul_bw = effective_total_bw * alloc_ratio;
        dl_bw = effective_total_bw * (1.0 - alloc_ratio);
    }
    else // 仿真刚启动，求解器还没下达命令时，暂时 50/50 对开
    {
        ul_bw = total_bw / 2.0;
        dl_bw = total_bw / 2.0;
    }
    // ==========================================

    dl_bw = std::min(dl_bw, elem.serverBwMbps);

    // 记录 oracle 值，仅仅为了给 Python 传 log 用作对比，绝不参与实际带宽决策
    oracle_trace_bw_kbps = total_bw * 1000.0;

    elem.prev_ul_bw = ul_bw;
    elem.prev_dl_bw = dl_bw;

    NS_LOG_DEBUG("BwAlloc Node: " << (uint16_t)elem.node_id << " raw_ul_bw: " << ul_bw << " raw_dl_bw: " << dl_bw);

    // [sharedbw] 用上/下行的实际送达速率(PhyTxEnd 字节)做诊断与耦合
    uint32_t sd_ui = 2 * elem.node_id, sd_di = 2 * elem.node_id + 1;
    double_t sd_iv = elem.interval / 1000.0;
    double_t ul_used = (double_t)(g_tx_bytes[sd_ui] - g_tx_bytes_prev[sd_ui]) * 8.0 / sd_iv / 1e6;
    double_t dl_used = (double_t)(g_tx_bytes[sd_di] - g_tx_bytes_prev[sd_di]) * 8.0 / sd_iv / 1e6;
    g_tx_bytes_prev[sd_ui] = g_tx_bytes[sd_ui];
    g_tx_bytes_prev[sd_di] = g_tx_bytes[sd_di];
    if (g_shared_bw)
    {
        // 稳定共享:上行可用满 C;下行补上行没用掉的剩余 -> 总吞吐守恒 ~= C,分配由发送端决定
        double_t bw_floor = std::max(0.5, total_bw * 0.05);
        ul_bw = total_bw;
        dl_bw = std::max(bw_floor, total_bw - ul_used);
        // 发布"实际送达总吞吐"作为干净观测(EWMA 轻平滑),供服务端取代 pacing
        g_observed_cap_kbps[elem.node_id] = std::max(total_bw * 0.05, (ul_used + dl_used)) * 1000.0; // 原始带噪观测(不EWMA):基线会抖,交给预测器去噪
    }
    if (g_diag_bw) std::cout << "[SharedDiag] node=" << elem.node_id << " C=" << total_bw
              << " ul_used=" << ul_used << " dl_used=" << dl_used
              << " total_used=" << (ul_used + dl_used)
              << " ul_bw=" << ul_bw << " dl_bw=" << dl_bw << std::endl;
    std::string ulBwStr = std::to_string(ul_bw) + "Mbps";
    std::string dlBwStr = std::to_string(dl_bw) + "Mbps";

    // Set bandwidth
    ulSndDev->SetAttribute("DataRate", StringValue(ulBwStr));
    dlSndDev->SetAttribute("DataRate", StringValue(dlBwStr));

    if (Simulator::Now() < Seconds(elem.simStopTime + 2))
    {
        if (!traceFile.eof())
        {
            traceFile.close();
            Simulator::Schedule(MilliSeconds(elem.interval), &BandwidthTrace, elem, n_client);
        }
        else
        {
            traceFile.close();
            elem.curr_pos = std::ios::beg; // start from the beginning again
            Simulator::Schedule(MilliSeconds(elem.interval), &BandwidthTrace, elem, n_client);
        }
    }
};

std::string GetRandomTraceFile(uint32_t max_trace_count, uint8_t dataset)
{
    uint32_t trace_count = rand() % max_trace_count;

    if (static_cast<DATASET>(dataset) == TR_RESTAURANT)
    {
        return "real-rest-wifi_" + std::to_string(trace_count) + ".trace";
    }

    uint32_t n_line = 0;
    std::string trace_file;
    std::fstream index_file;
    index_file.open("../../../scripts/tracefile_names", std::ios::in);
    while (getline(index_file, trace_file) && n_line < trace_count)
    {
        n_line++;
        if (index_file.eof())
        {
            break;
        }
    }

    return trace_file;
};

int main(int argc, char *argv[])
{
    std::string mode = "p2p";
    uint8_t logLevel = 0;
    double_t simulationDuration = 10.0; // in s
    uint32_t maxBitrateKbps = 10000;
    uint8_t policy = 0;
    uint32_t nClient = 1;
    bool printPosition = false;
    bool savePcap = false;
    bool vary_bw = false;
    bool mlpred = false;
    uint8_t trace_mode = 0;
    uint8_t dataset = 0;
    double_t ul_prop = 0.5;
    double_t minBitrateKbps = 1000.0;
    uint16_t seed = 1;
    bool is_tack = false;
    uint32_t tack_max_count = 32;
    uint16_t trace_interval = 16;
    double_t server_bottleneck_mbps = 1000;

    uint32_t MAX_TRACE_COUNT = 1115;

    CommandLine cmd(__FILE__);
    cmd.AddValue("mode", "p2p or sfu mode", mode);
    cmd.AddValue("logLevel", "Log level: 0 for error, 1 for debug, 2 for logic", logLevel);
    cmd.AddValue("simTime", "Total simulation time in s", simulationDuration);
    cmd.AddValue("maxBitrateKbps", "Max bitrate in kbps", maxBitrateKbps);
    cmd.AddValue("policy", "0 for vanilla, 1 for Plum", policy);
    cmd.AddValue("nClient", "Number of clients", nClient);
    cmd.AddValue("printPosition", "Print position of nodes", printPosition);
    cmd.AddValue("minBitrate", "Minimum tolerable bitrate in kbps", minBitrateKbps);
    cmd.AddValue("savePcap", "Save pcap file", savePcap);
    cmd.AddValue("varyBw", "Emulate in varying bandwidth or not", vary_bw);
    cmd.AddValue("mlpred", "Enable ML prediction for bandwidth", mlpred);
    cmd.AddValue("traceMode", "0 for even split, 1 for uneven split", trace_mode);
    cmd.AddValue("ulProp", "Proportion of uplink bandwidth", ul_prop);
    cmd.AddValue("seed", "Random seed for trace selection", seed);
    cmd.AddValue("isTack", "Is TACK enabled", is_tack);
    cmd.AddValue("tackMaxCount", "Max TACK count", tack_max_count);
    cmd.AddValue("dataset", "Dataset to use", dataset);
    cmd.AddValue("serverBtl", "Server bottleneck in Mbps", server_bottleneck_mbps);
    cmd.AddValue("sharedbw", "Shared half-duplex medium", g_shared_bw);
    cmd.AddValue("diagbw", "print SharedDiag diagnostics", g_diag_bw);
    cmd.AddValue("predfilter", "use median filter instead of Transformer", g_pred_filter);

    cmd.Parse(argc, argv);
    Time::SetResolution(Time::NS);
    std::srand(seed);

    Config::SetDefault("ns3::TcpL4Protocol::SocketType", StringValue("ns3::TcpBbr"));
    Config::SetDefault("ns3::TcpSocket::SegmentSize", UintegerValue(1448));

    if (is_tack)
    {
        Config::SetDefault("ns3::TcpSocketBase::IsTack", BooleanValue(true));
        Config::SetDefault("ns3::TcpSocket::DelAckCount", UintegerValue(tack_max_count));
    }
    else
    {
        Config::SetDefault("ns3::TcpSocket::DelAckCount", UintegerValue(1));
    }

    if (static_cast<LOG_LEVEL>(logLevel) == LOG_LEVEL::ERROR)
    {
        LogComponentEnable("VcaServer", LOG_LEVEL_ERROR);
        LogComponentEnable("VcaClient", LOG_LEVEL_ERROR);
        LogComponentEnable("MulticastEmulation", LOG_LEVEL_ERROR);
    }
    else if (static_cast<LOG_LEVEL>(logLevel) == LOG_LEVEL::DEBUG)
    {
        LogComponentEnable("VcaServer", LOG_LEVEL_DEBUG);
        LogComponentEnable("VcaClient", LOG_LEVEL_DEBUG);
        LogComponentEnable("MulticastEmulation", LOG_LEVEL_DEBUG);
    }
    else if (static_cast<LOG_LEVEL>(logLevel) == LOG_LEVEL::LOGIC)
    {
        LogComponentEnable("VcaServer", LOG_LEVEL_LOGIC);
        LogComponentEnable("VcaClient", LOG_LEVEL_LOGIC);
        LogComponentEnable("MulticastEmulation", LOG_LEVEL_LOGIC);
    }

    signal(SIGPIPE, SIG_IGN); // [robust] 断管别杀仿真
    NS_LOG_DEBUG("[Scratch] SFU mode emulation started.");

    NodeContainer sfuCenter, clientNodes;
    clientNodes.Create(nClient);
    sfuCenter.Create(1);

    PointToPointHelper ulP2p[nClient], dlP2p[nClient];
    for (uint32_t i = 0; i < nClient; i++)
    {
        ulP2p[i].SetDeviceAttribute("DataRate", StringValue("10Mbps"));
        ulP2p[i].SetChannelAttribute("Delay", StringValue("10ms"));
        dlP2p[i].SetDeviceAttribute("DataRate", StringValue("10Mbps"));
        dlP2p[i].SetChannelAttribute("Delay", StringValue("10ms"));
    }

    NetDeviceContainer ulDevices[nClient], dlDevices[nClient];
    if (vary_bw)
    {
        if (static_cast<DATASET>(dataset) == TR_GAME)
        {
            MAX_TRACE_COUNT = 1115;
            trace_interval = 16;
        }
        else if (static_cast<DATASET>(dataset) == TR_RESTAURANT)
        {
            MAX_TRACE_COUNT = 16;
            trace_interval = 100;
        }
    }

    for (uint32_t i = 0; i < nClient; i++)
    {
        ulDevices[i] = ulP2p[i].Install(clientNodes.Get(i), sfuCenter.Get(0));
        dlDevices[i] = dlP2p[i].Install(clientNodes.Get(i), sfuCenter.Get(0));
        ulDevices[i].Get(0)->TraceConnectWithoutContext("PhyTxEnd", MakeBoundCallback(&CountTx, 2 * i));
        dlDevices[i].Get(1)->TraceConnectWithoutContext("PhyTxEnd", MakeBoundCallback(&CountTx, 2 * i + 1));

        if (vary_bw)
        {
            std::string trace_dir;
            if (static_cast<DATASET>(dataset) == TR_GAME)
                trace_dir = "../../../scripts/traces/gaming/";
            else if (static_cast<DATASET>(dataset) == TR_RESTAURANT)
                trace_dir = "../../../scripts/traces/restaurant/";

            std::string trace_name = GetRandomTraceFile(MAX_TRACE_COUNT, dataset);
            std::string tracefile = trace_dir + trace_name;
            TraceElem elem = {tracefile, static_cast<TRACE_MODE>(trace_mode), static_cast<DATASET>(dataset), ulDevices[i].Get(0), dlDevices[i].Get(1), trace_interval, simulationDuration, (double_t)maxBitrateKbps / 1000., minBitrateKbps / 1000., server_bottleneck_mbps / (double_t)nClient, i, ul_prop};
            BandwidthTrace(elem, nClient);
        }
    }

    InternetStackHelper stack;
    stack.Install(clientNodes);
    stack.Install(sfuCenter);

    Ipv4AddressHelper ipAddr;
    std::string ip;
    Ipv4InterfaceContainer ulIpIfaces[nClient], dlIpIfaces[nClient];
    for (uint32_t i = 0; i < nClient; i++)
    {
        ip = "10.1." + std::to_string(i) + ".0";
        ipAddr.SetBase(ns3::Ipv4Address(ip.c_str()), "255.255.255.0");
        ulIpIfaces[i] = ipAddr.Assign(ulDevices[i]);

        ip = "10.2." + std::to_string(i) + ".0";
        ipAddr.SetBase(ns3::Ipv4Address(ip.c_str()), "255.255.255.0");
        dlIpIfaces[i] = ipAddr.Assign(dlDevices[i]);
    }

    uint16_t client_ul = 80;
    uint16_t client_dl = 8080;
    uint16_t client_peer = 80;

    std::list<Ipv4Address> serverUlAddrList;

    for (uint32_t id = 0; id < nClient; id++)
    {
        Ipv4Address clientUlAddr = ulIpIfaces[id].GetAddress(0);
        Ipv4Address clientDlAddr = dlIpIfaces[id].GetAddress(0);
        Ipv4Address serverUlAddr = ulIpIfaces[id].GetAddress(1);

        serverUlAddrList.push_back(serverUlAddr);

        NS_LOG_DEBUG("SFU VCA Client NodeId " << clientNodes.Get(id)->GetId() << " Server NodeId " << sfuCenter.Get(0)->GetId());
        Ptr<VcaClient> vcaClientApp = CreateObject<VcaClient>();
        vcaClientApp->SetFps(20);
        vcaClientApp->SetLocalAddress(clientUlAddr, clientDlAddr);
        vcaClientApp->SetPeerAddress(std::vector<Ipv4Address>{serverUlAddr});
        vcaClientApp->SetLocalUlPort(client_ul);
        vcaClientApp->SetLocalDlPort(client_dl);
        vcaClientApp->SetPeerPort(client_peer);
        vcaClientApp->SetNodeId(clientNodes.Get(id)->GetId());
        vcaClientApp->SetNumNode(nClient);
        vcaClientApp->SetPolicy(static_cast<POLICY>(policy));
        vcaClientApp->SetMlPred(mlpred);
        vcaClientApp->SetMaxBitrate(maxBitrateKbps);
        vcaClientApp->SetMinBitrate(minBitrateKbps);
        clientNodes.Get(id)->AddApplication(vcaClientApp);

        Simulator::Schedule(Seconds(simulationDuration), &VcaClient::StopEncodeFrame, vcaClientApp);
        vcaClientApp->SetStartTime(Seconds(0.0));
        vcaClientApp->SetStopTime(Seconds(simulationDuration + 4));
    }

    Ptr<VcaServer> vcaServerApp = CreateObject<VcaServer>();
    vcaServerApp->SetLocalAddress(serverUlAddrList);
    vcaServerApp->SetLocalUlPort(client_peer);
    vcaServerApp->SetPeerDlPort(client_dl);
    vcaServerApp->SetLocalDlPort(client_dl);
    vcaServerApp->SetNodeId(sfuCenter.Get(0)->GetId());
    vcaServerApp->SetSeparateSocket();
    vcaServerApp->SetNumNode(nClient);
    vcaServerApp->SetPolicy(static_cast<POLICY>(policy));
    vcaServerApp->SetMlPred(mlpred);
    sfuCenter.Get(0)->AddApplication(vcaServerApp);
    vcaServerApp->SetStartTime(Seconds(0.0));
    vcaServerApp->SetStopTime(Seconds(simulationDuration + 2));

    if (savePcap)
    {
        AsciiTraceHelper ascii;
        ulP2p[0].EnablePcapAll("sfu-p2p");
        ulP2p[0].EnableAsciiAll(ascii.CreateFileStream("sfu-ul.tr"));
    }

    FlowMonitorHelper flowmonHelper;
    flowmonHelper.InstallAll();

    Ipv4GlobalRoutingHelper::PopulateRoutingTables();

    Simulator::Stop(Seconds(simulationDuration + 5));
    Simulator::Run();
    flowmonHelper.SerializeToXmlFile("test-emulation.flowmon", true, true);
    Simulator::Destroy();
    return 0;
}