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
#include <cstdlib>
#include <random>

using namespace ns3;

// ---- 方案A: 预测驱动分配 (traceMode=2) ----
// 基于 xzy-master 的上帝视角分配公式(已验证 n=8 QoE +78~100% vs 均分),
// 把"分配决策"里用的带宽从真实值换成【因果预测值】(只用过去样本),
// 物理链路容量仍用真实带宽。对比: 均分(0) / 上帝视角(1) / 预测分配(2)。

// xzy-ml 分支 videoconf(vca_server.cc) extern 的全局符号,必须在 scratch 定义
double_t oracle_trace_bw_kbps = 0.0;
double_t g_observed_cap_kbps[256] = {0.0};
bool g_lag_obs = false;
bool g_fast_pred = false;
bool g_pred_filter = false;
double_t g_fast_cap_kbps[256] = {0.0};
double_t global_ul_target_rate[50] = {0.0};
double_t global_dl_target_rate[50] = {0.0};

// 因果预测器状态(每客户端): pred(t) 只由 y(<t) 构成
static double_t g_pred_state[64] = {0.0};
static bool g_pred_inited[64] = {false};
static double_t g_pred_alpha = 1.0;   // 1.0=persistence(用上一步真实值); <1 = EWMA
static double_t g_pred_noise = 0.0;   // 预测相对误差std(高斯), 0=无噪声; 用于误差鲁棒性曲线
static std::mt19937 g_pred_rng(12345);

NS_LOG_COMPONENT_DEFINE("MulticastEmulation");

enum LOG_LEVEL
{
    ERROR,
    DEBUG,
    LOGIC
};

enum TRACE_MODE
{
    EVEN_SPLIT,     // 0: 均分
    UNEVEN_SPLIT,   // 1: 上帝视角(真实带宽驱动分配)
    PRED_SPLIT      // 2: 预测驱动分配(因果预测值驱动决策, 真实值仍是物理容量)
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
    traceFile.seekg(elem.curr_pos);
    if (elem.curr_pos == std::ios::beg && !traceFile.eof() && elem.dataset == TR_GAME)
    {
        std::getline(traceFile, traceLine); // skip the first line
    }
    std::getline(traceFile, traceLine);
    elem.curr_pos = traceFile.tellg();
    if (traceLine.find('.') == std::string::npos)
    {
        traceFile.close();
        return;
    }

    // bwValue.clear();
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

    // ---- 因果预测: pred(t) 仅由过去样本构成; 用后再吸收当前真实值 ----
    double_t decision_bw = total_bw; // UNEVEN_SPLIT(上帝视角)用真实值
    if (elem.mode == PRED_SPLIT)
    {
        uint32_t nid = elem.node_id % 64;
        if (!g_pred_inited[nid])
        {
            g_pred_state[nid] = total_bw; // 首步无历史,用首样本初始化(占比可忽略)
            g_pred_inited[nid] = true;
        }
        decision_bw = g_pred_state[nid];
        if (g_pred_noise > 1e-9)
        {
            std::normal_distribution<double> nd(0.0, g_pred_noise);
            decision_bw = std::max(0.1, decision_bw * (1.0 + nd(g_pred_rng)));
        }
        // 更新状态(在使用之后 => 因果): persistence(alpha=1)或EWMA
        g_pred_state[nid] = g_pred_alpha * total_bw + (1.0 - g_pred_alpha) * g_pred_state[nid];
    }

    if (elem.mode == EVEN_SPLIT)
    {
        ul_bw = total_bw / 2;
        dl_bw = total_bw / 2;

        dl_bw = std::min(dl_bw, elem.serverBwMbps);

        NS_LOG_DEBUG("BwAlloc Node: " << (uint16_t)elem.node_id << " ul_bw: " << ul_bw << " dl_bw: " << dl_bw);
    }
    else
    {
        if (global_know.clientSetTraceCount >= n_client)
        {
            global_know.clientSetTraceCount = 0;
            global_know.prevAmpleBwUserExist = global_know.newAmpleBwUserExist;
            global_know.prevMaxAbw = std::max(n_client * elem.minAppBitrateMbps, global_know.newMaxAbw);
            global_know.newMaxAbw = 0;
            global_know.newAmpleBwUserExist = 0;
        }

        double_t min_recv_rate = (n_client - 1) * elem.minAppBitrateMbps;
        double_t app_limit_bw = n_client * elem.maxAppBitrateMbps;

        // 决策一律用 decision_bw(上帝=真实, 预测=因果预测值)
        if (decision_bw < min_recv_rate)
        {
            ul_bw = decision_bw / 2;
            dl_bw = decision_bw / 2;
        }
        else
        {
            if (global_know.prevAmpleBwUserExist)
            {
                if (decision_bw < min_recv_rate + elem.maxAppBitrateMbps * 1.2)
                {
                    dl_bw = min_recv_rate;
                    ul_bw = decision_bw - dl_bw;

                    NS_LOG_LOGIC("ul_bw: " << ul_bw << "Mbps, dl_bw: " << dl_bw << "Mbps line135");
                }
                else
                {
                    ul_bw = elem.maxAppBitrateMbps * 1.2;
                    dl_bw = decision_bw - ul_bw;
                    NS_LOG_LOGIC("ul_bw: " << ul_bw << "Mbps, dl_bw: " << dl_bw << "Mbps line141");
                }
            }
            else
            {
                double_t min_ul_bw_for_the_rest = (n_client - global_know.clientSetTraceCount - 1) * elem.minAppBitrateMbps;
                double_t fair_share_for_the_rest = global_know.prevMaxAbw / (n_client - global_know.clientSetTraceCount);
                ul_bw = std::min(std::max(elem.minAppBitrateMbps, std::min(global_know.prevMaxAbw - min_ul_bw_for_the_rest, fair_share_for_the_rest)), decision_bw - min_recv_rate);
                dl_bw = decision_bw - ul_bw;

                NS_LOG_LOGIC("ul_bw: " << ul_bw << "Mbps, dl_bw: " << dl_bw << "Mbps"
                                       << " prevmaxabw: " << global_know.prevMaxAbw << "Mbps"
                                       << " decision_bw: " << decision_bw << "Mbps"
                                       << " min ul bw for the rest: " << min_ul_bw_for_the_rest << "Mbps"
                                       << " fair share for the rest: " << fair_share_for_the_rest << "Mbps");

                global_know.prevMaxAbw = std::max(0.0, global_know.prevMaxAbw - ul_bw);
            }
        }

        // PRED_SPLIT: 决策产出的是"比例", 物理容量仍是真实 total_bw => 按比例回缩放
        if (elem.mode == PRED_SPLIT)
        {
            double_t dsum = ul_bw + dl_bw;
            if (dsum > 0.001)
            {
                double_t r = ul_bw / dsum;
                ul_bw = r * total_bw;
                dl_bw = total_bw - ul_bw;
            }
            else
            {
                ul_bw = total_bw / 2;
                dl_bw = total_bw / 2;
            }
        }

        dl_bw = std::min(dl_bw, elem.serverBwMbps);

        NS_LOG_DEBUG("BwAlloc Node: " << (uint16_t)elem.node_id << " ul_bw: " << ul_bw << " dl_bw: " << dl_bw);

        elem.prev_ul_bw = ul_bw;
        elem.prev_dl_bw = dl_bw;

        // Update global Knowledge (预测模式下, 协调器知识也只能来自预测值)
        if (decision_bw >= app_limit_bw)
        {
            global_know.newAmpleBwUserExist = 1;
        }
        global_know.newMaxAbw = std::max(global_know.newMaxAbw, decision_bw);
        global_know.clientSetTraceCount++;
    }

    /* Set delay of n0-n1 as rtt/2 - 1, the delay of n1-n2 is 1ms */
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

    // std::string Version = "80211n_5GHZ";

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
    cmd.AddValue("traceMode", "0 even split, 1 oracle(god-view), 2 prediction-driven", trace_mode);
    cmd.AddValue("predAlpha", "predictor EWMA alpha (1.0=persistence)", g_pred_alpha);
    cmd.AddValue("predNoise", "relative gaussian noise std on prediction (0=off)", g_pred_noise);
    cmd.AddValue("ulProp", "Proportion of uplink bandwidth", ul_prop);
    cmd.AddValue("seed", "Random seed for trace selection", seed);
    cmd.AddValue("isTack", "Is TACK enabled", is_tack);
    cmd.AddValue("tackMaxCount", "Max TACK count", tack_max_count);
    cmd.AddValue("dataset", "Dataset to use", dataset);
    cmd.AddValue("serverBtl", "Server bottleneck in Mbps", server_bottleneck_mbps);

    cmd.Parse(argc, argv);
    Time::SetResolution(Time::NS);
    std::srand(seed);
    g_pred_rng.seed(seed * 7919 + 17); // 预测噪声与seed绑定,可复现

    // Config::SetDefault ("ns3::DropTailQueue<Packet>::MaxSize", QueueSizeValue (QueueSize ("1p")));
    // Config::SetDefault ("ns3::TcpSocket::SndBufSize", UintegerValue (5 << 20)); // if (rwnd > 5M)，retransmission (RTO) will accumulate
    // Config::SetDefault ("ns3::TcpSocket::RcvBufSize", UintegerValue (5 << 20)); // over 5M packets, causing packet metadata overflows.
    Config::SetDefault("ns3::TcpL4Protocol::SocketType", StringValue("ns3::TcpBbr"));
    Config::SetDefault("ns3::TcpSocket::SegmentSize", UintegerValue(1448));
    // Config::SetDefault("ns3::TcpSocketBase::MinRto", TimeValue(MilliSeconds(200)));

    if (is_tack)
    {
        Config::SetDefault("ns3::TcpSocketBase::IsTack", BooleanValue(true));
        Config::SetDefault("ns3::TcpSocket::DelAckCount", UintegerValue(tack_max_count));
    }
    else
    {
        Config::SetDefault("ns3::TcpSocket::DelAckCount", UintegerValue(1));
    }

    // set log level
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

    NS_LOG_DEBUG("[Scratch] SFU mode emulation started.");

    // Create nodes
    NodeContainer sfuCenter, clientNodes;
    clientNodes.Create(nClient);
    sfuCenter.Create(1);

    // Create backhaul links
    PointToPointHelper ulP2p[nClient], dlP2p[nClient];
    for (uint32_t i = 0; i < nClient; i++)
    {
        ulP2p[i].SetDeviceAttribute("DataRate", StringValue("10Mbps"));
        ulP2p[i].SetChannelAttribute("Delay", StringValue("10ms"));
        dlP2p[i].SetDeviceAttribute("DataRate", StringValue("10Mbps"));
        dlP2p[i].SetChannelAttribute("Delay", StringValue("10ms"));
    }

    // Install NetDevices on backhaul links
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

        if (vary_bw)
        {
            std::string trace_dir;
            if (static_cast<DATASET>(dataset) == TR_GAME)
            {
                trace_dir = "../../../scripts/traces/gaming/";
            }
            else if (static_cast<DATASET>(dataset) == TR_RESTAURANT)
            {
                trace_dir = "../../../scripts/traces/restaurant/";
            }

            std::string trace_name = GetRandomTraceFile(MAX_TRACE_COUNT, dataset);
            // std::string trace_dir = "../../../scripts/";
            // std::string trace_name = "trace-debug.csv";
            std::string tracefile = trace_dir + trace_name;
            TraceElem elem = {tracefile, static_cast<TRACE_MODE>(trace_mode), static_cast<DATASET>(dataset), ulDevices[i].Get(0), dlDevices[i].Get(1), trace_interval, simulationDuration, (double_t)maxBitrateKbps / 1000., minBitrateKbps / 1000., server_bottleneck_mbps / (double_t)nClient, i, ul_prop};
            BandwidthTrace(elem, nClient);
        }
    }

    InternetStackHelper stack;

    stack.Install(clientNodes);
    stack.Install(sfuCenter);

    // Assign IPv4 addresses for NetDevices
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

    // Install VcaClient Application for each user
    uint16_t client_ul = 80;
    uint16_t client_dl = 8080; // dl_port may increase in VcaServer, make sure it doesn't overlap with ul_port
    uint16_t client_peer = 80;

    std::list<Ipv4Address> serverUlAddrList;

    for (uint32_t id = 0; id < nClient; id++)
    {

        Ipv4Address clientUlAddr = ulIpIfaces[id].GetAddress(0);
        Ipv4Address clientDlAddr = dlIpIfaces[id].GetAddress(0);
        Ipv4Address serverUlAddr = ulIpIfaces[id].GetAddress(1);

        serverUlAddrList.push_back(serverUlAddr);

        // Ipv4Address serverDlAddr = dlIpIfaces[id].GetAddress(1);
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
        vcaClientApp->SetMaxBitrate(maxBitrateKbps);
        vcaClientApp->SetMinBitrate(minBitrateKbps);
        // vcaClientApp->SetLogFile("../../../evaluation/results/trlogs/transient_rate_n" + std::to_string(nClient) + "_p" + std::to_string(trace_mode) + "_d" + std::to_string(dataset) + "_i" + std::to_string(clientNodes.Get(id)->GetId()) + ".txt");
        clientNodes.Get(id)->AddApplication(vcaClientApp);

        Simulator::Schedule(Seconds(simulationDuration), &VcaClient::StopEncodeFrame, vcaClientApp);
        vcaClientApp->SetStartTime(Seconds(0.0));
        vcaClientApp->SetStopTime(Seconds(simulationDuration + 4));
    }

    // Install VcaServer Application for the server
    Ptr<VcaServer> vcaServerApp = CreateObject<VcaServer>();
    // vcaServerApp->SetLocalAddress(serverUlAddr);
    vcaServerApp->SetLocalAddress(serverUlAddrList);
    vcaServerApp->SetLocalUlPort(client_peer);
    vcaServerApp->SetPeerDlPort(client_dl);
    vcaServerApp->SetLocalDlPort(client_dl);
    vcaServerApp->SetNodeId(sfuCenter.Get(0)->GetId());
    vcaServerApp->SetSeparateSocket();
    vcaServerApp->SetNumNode(nClient);
    sfuCenter.Get(0)->AddApplication(vcaServerApp);
    vcaServerApp->SetStartTime(Seconds(0.0));
    vcaServerApp->SetStopTime(Seconds(simulationDuration + 2));

    if (savePcap)
    {
        AsciiTraceHelper ascii;
        ulP2p[0].EnablePcapAll("sfu-p2p");
        // dlP2p[0].EnablePcapAll("sfu-p2p");
        ulP2p[0].EnableAsciiAll(ascii.CreateFileStream("sfu-ul.tr"));
        // dlP2p[0].EnableAsciiAll(ascii.CreateFileStream("sfu-dl.tr"));
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