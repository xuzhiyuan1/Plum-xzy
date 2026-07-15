// test_wifi_trace_tuned.cc
// 方案 C: 保留原生 NS3 Wi-Fi (PHY / 速率自适应完全不动),
// 在信道上叠加"幅度可调、时间相关"的 AR(1) 距离调制,
// 把每个客户端有效带宽的波动幅度校准到真实 restaurant Wi-Fi trace 的水平,
// 再在该波动下对比 vanilla / Plum / Plum+预测 的 QoE。
//
// 基于 scratch/test_wifi_channel.cc 的 sfu 模式改写,只保留单一模式。

#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/applications-module.h"
#include <string.h>
#include <cstdlib>
#include <vector>
#include "ns3/flow-monitor-helper.h"
#include "ns3/ipv4-address.h"
#include "ns3/mobility-module.h"
#include "ns3/ssid.h"
#include "ns3/yans-wifi-helper.h"
#include "ns3/videoconf-module.h"

#include <fstream>
#include <sstream>
using namespace ns3;

// ---- vca_server.cc 通过 extern 引用的全局符号,必须在本 scratch 内定义,否则链接期 undefined symbol ----
double_t oracle_trace_bw_kbps = 0.0;
double_t g_observed_cap_kbps[256] = {0.0};
bool g_lag_obs = false;
bool g_fast_pred = false;
bool g_pred_filter = false;
double_t g_fast_cap_kbps[256] = {0.0};
double_t global_ul_target_rate[50] = {0.0};
double_t global_dl_target_rate[50] = {0.0};

NS_LOG_COMPONENT_DEFINE("WifiTraceTuned");

enum LOG_LEVEL
{
  ERROR,
  DEBUG,
  LOGIC
};

// ================= AR(1) 信道驱动 =================
// 每个 STA 到自己 AP 的距离按 AR(1) 演化:
//   d(t) = mu + rho*(d(t-1)-mu) + eps,  eps ~ N(0, sigma^2)
// 距离 -> LogDistance 路损 -> SNR -> 原生速率自适应 -> 吞吐波动。
// sigma 直接控制波动幅度,rho 控制时间相关性(像真实 trace 那样漂移而非白噪声)。
struct ChanState
{
  Ptr<MobilityModel> staMob;
  double apX;
  double apY;
  double dist;
};
static std::vector<ChanState> g_chan;
static Ptr<NormalRandomVariable> g_arNoise;
static double g_meanDist = 8.0;
static double g_rho = 0.9;
static double g_minDist = 1.0;
static double g_maxDist = 40.0;
static double g_bwStep = 0.5;
static double g_simDur = 120.0;
static std::ofstream g_distLog;
static bool g_logDist = false;

void DriveChannel()
{
  double now = Simulator::Now().GetSeconds();
  for (uint32_t i = 0; i < g_chan.size(); i++)
  {
    ChanState &c = g_chan[i];
    double eps = g_arNoise->GetValue(); // N(0, sigma^2)
    c.dist = g_meanDist + g_rho * (c.dist - g_meanDist) + eps;
    if (c.dist < g_minDist)
      c.dist = g_minDist;
    if (c.dist > g_maxDist)
      c.dist = g_maxDist;
    c.staMob->SetPosition(Vector(c.apX + c.dist, c.apY, 0.0));
    if (g_logDist)
      g_distLog << now << "," << i << "," << c.dist << "\n";
  }
  if (now + g_bwStep < g_simDur)
    Simulator::Schedule(Seconds(g_bwStep), &DriveChannel);
}

int main(int argc, char *argv[])
{
  std::string mode = "sfu";
  uint8_t logLevel = 0;
  double_t simulationDuration = 120.0; // in s
  uint32_t maxBitrateKbps = 10000;
  uint8_t policy = 0;
  uint32_t nClient = 1;
  bool printPosition = false;
  bool savePcap = false;
  bool saveTransRate = false;
  bool mlpred = false;
  double_t minBitrateKbps = 4.0;
  uint32_t kUlImprove = 3;
  double_t kDlYield = 0.5;
  uint32_t kLowUlThresh = 2e6;
  uint32_t kHighUlThresh = 5e6;
  bool is_tack = false;
  uint32_t tack_max_count = 32;
  int qoeType = 0;
  double dl_percentage = 0.5;

  // ---- AR(1) 信道调制参数 (方案 C 新增) ----
  double bwSigma = 0.0;   // AR(1) 噪声标准差(米);0=关闭波动(纯 baseline)
  double bwRho = 0.9;     // AR(1) 相关系数
  double bwStep = 0.5;    // 信道更新步长(s)
  double meanDist = 8.0;  // STA-AP 平均距离(m)
  double minDist = 1.0;   // 距离下限
  double maxDist = 45.0;  // 距离上限
  uint32_t chWidth = 20;  // wifi 信道带宽 MHz(10/20/40);容量旋钮,n=8 需更大容量
  uint32_t nWifiClients = 999; // 默认全部客户端在 wifi(带 AR(1) 波动); clamp 到 nClient。设小值可退回"少数 wifi+其余有线"
  std::string distLog = ""; // 距离时间序列日志路径;空=不写
  std::string transRateDir = ""; // 每客户端按秒码率日志目录;空=不写

  CommandLine cmd(__FILE__);
  cmd.AddValue("mode", "only sfu supported here", mode);
  cmd.AddValue("logLevel", "Log level: 0 error, 1 debug, 2 logic", logLevel);
  cmd.AddValue("simTime", "Total simulation time in s", simulationDuration);
  cmd.AddValue("maxBitrateKbps", "Max bitrate in kbps", maxBitrateKbps);
  cmd.AddValue("policy", "0 Vanilla, 1 Plum old, 2 Plum, 3 Fixed", policy);
  cmd.AddValue("nClient", "Number of clients", nClient);
  cmd.AddValue("printPosition", "Print position of nodes", printPosition);
  cmd.AddValue("minBitrate", "Minimum tolerable bitrate in kbps", minBitrateKbps);
  cmd.AddValue("savePcap", "Save pcap file", savePcap);
  cmd.AddValue("ulImpv", "UL improvement param", kUlImprove);
  cmd.AddValue("dlYield", "DL yield param", kDlYield);
  cmd.AddValue("lowUlThresh", "Low UL threshold", kLowUlThresh);
  cmd.AddValue("highUlThresh", "High UL threshold", kHighUlThresh);
  cmd.AddValue("saveTransRate", "Save transmission rate", saveTransRate);
  cmd.AddValue("mlpred", "Enable ML prediction for bandwidth", mlpred);
  cmd.AddValue("isTack", "Is TACK enabled", is_tack);
  cmd.AddValue("tackMaxCount", "Max TACK count", tack_max_count);
  cmd.AddValue("qoeType", "0 lin,1 log,2 sqr_concave,3 sqr_convex", qoeType);
  cmd.AddValue("dlpercentage", "for policy 3(FIXED), dl_percentage", dl_percentage);
  // AR(1) 开关
  cmd.AddValue("bwSigma", "AR(1) distance noise std in meters (0=off)", bwSigma);
  cmd.AddValue("bwRho", "AR(1) correlation coefficient", bwRho);
  cmd.AddValue("bwStep", "channel update step in s", bwStep);
  cmd.AddValue("meanDist", "mean STA-AP distance in m", meanDist);
  cmd.AddValue("minDist", "min STA-AP distance in m", minDist);
  cmd.AddValue("maxDist", "max STA-AP distance in m", maxDist);
  cmd.AddValue("chWidth", "wifi channel width MHz (10/20/40)", chWidth);
  cmd.AddValue("nWifiClients", "number of clients on wifi (rest on wired backhaul)", nWifiClients);
  cmd.AddValue("distLog", "path to write per-step distance log (empty=off)", distLog);
  cmd.AddValue("transRateDir", "dir to write per-client per-second rate logs (empty=off)", transRateDir);

  cmd.Parse(argc, argv);
  Time::SetResolution(Time::NS);

  Config::SetDefault("ns3::TcpL4Protocol::SocketType", StringValue("ns3::TcpBbr"));
  Config::SetDefault("ns3::TcpSocket::SegmentSize", UintegerValue(1448));

  if (is_tack)
  {
    Config::SetDefault("ns3::TcpSocketBase::IsTack", BooleanValue(true));
    Config::SetDefault("ns3::TcpSocket::DelAckCount", UintegerValue(tack_max_count));
  }

  if (static_cast<LOG_LEVEL>(logLevel) == LOG_LEVEL::ERROR)
  {
    LogComponentEnable("VcaServer", LOG_LEVEL_ERROR);
    LogComponentEnable("VcaClient", LOG_LEVEL_ERROR);
    LogComponentEnable("WifiTraceTuned", LOG_LEVEL_ERROR);
  }
  else if (static_cast<LOG_LEVEL>(logLevel) == LOG_LEVEL::DEBUG)
  {
    LogComponentEnable("VcaServer", LOG_LEVEL_DEBUG);
    LogComponentEnable("VcaClient", LOG_LEVEL_DEBUG);
    LogComponentEnable("WifiTraceTuned", LOG_LEVEL_DEBUG);
  }
  else if (static_cast<LOG_LEVEL>(logLevel) == LOG_LEVEL::LOGIC)
  {
    LogComponentEnable("VcaServer", LOG_LEVEL_LOGIC);
    LogComponentEnable("VcaClient", LOG_LEVEL_LOGIC);
    LogComponentEnable("WifiTraceTuned", LOG_LEVEL_LOGIC);
  }

  // ============ 单一 sfu 拓扑 ============
  NS_LOG_DEBUG("[Scratch] wifi-trace-tuned SFU emulation started.");

  double_t showPositionDeltaTime = 1;

  NodeContainer p2pNodes, sfuCenter, wifiStaNodes[nClient], wifiApNode[nClient];
  uint8_t nWifi[nClient];
  for (uint32_t i = 0; i < nClient; i++)
    nWifi[i] = 1;
  p2pNodes.Create(nClient + 1);
  for (uint8_t i = 0; i < nClient; i++)
  {
    wifiStaNodes[i].Create(nWifi[i]);
    wifiApNode[i] = p2pNodes.Get(i);
  }
  sfuCenter = p2pNodes.Get(nClient);

  // backhaul P2P
  PointToPointHelper pointToPoint[nClient];
  for (uint32_t i = 0; i < nClient; i++)
  {
    pointToPoint[i].SetDeviceAttribute("DataRate", StringValue("50Mbps"));
    pointToPoint[i].SetChannelAttribute("Delay", StringValue("10ms"));
  }
  NetDeviceContainer backhaulDevices[nClient];
  for (uint32_t i = 0; i < nClient; i++)
    backhaulDevices[i] = pointToPoint[i].Install(wifiApNode[i].Get(0), sfuCenter.Get(0));

  // WLAN 原生信道 (与 test_wifi_channel.cc 完全一致)
  YansWifiChannelHelper channel = YansWifiChannelHelper::Default();
  YansWifiPhyHelper phy;
  WifiMacHelper mac;
  Ssid ssid;
  WifiHelper wifi;
  NetDeviceContainer staDevices[nClient];
  NetDeviceContainer apDevices[nClient];

  // 802.11p 10MHz(与原版 test_wifi_channel 一致,干净); chWidth 此标准固定 10MHz
  (void)chWidth;
  wifi.SetStandard(WIFI_STANDARD_80211p);
  phy.Set("ChannelSettings", StringValue("{0, 10, BAND_5GHZ, 0}"));

  for (uint32_t i = 0; i < nClient; i++)
  {
    std::string id = "ssid" + std::to_string(i + 1);
    ssid = Ssid(id);
    phy.SetChannel(channel.Create());

    mac.SetType("ns3::StaWifiMac", "Ssid", SsidValue(ssid), "ActiveProbing", BooleanValue(false));
    staDevices[i] = wifi.Install(phy, mac, wifiStaNodes[i]);
    mac.SetType("ns3::ApWifiMac", "Ssid", SsidValue(ssid));
    apDevices[i] = wifi.Install(phy, mac, wifiApNode[i]);
  }

  // ---- Mobility: AP 用网格固定,STA 全部 ConstantPosition 由 AR(1) 驱动重定位 ----
  MobilityHelper mobility;
  mobility.SetPositionAllocator("ns3::GridPositionAllocator",
                                "MinX", DoubleValue(0.0),
                                "MinY", DoubleValue(0.0),
                                "DeltaX", DoubleValue(100.0),
                                "DeltaY", DoubleValue(1.0),
                                "GridWidth", UintegerValue(nClient),
                                "LayoutType", StringValue("RowFirst"));
  mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
  for (uint32_t i = 0; i < nClient; i++)
    mobility.Install(wifiApNode[i]);
  for (uint32_t i = 0; i < nClient; i++)
    mobility.Install(wifiStaNodes[i]);

  // 配置全局 AR(1) 参数并注册每个 STA 的信道状态
  g_meanDist = meanDist;
  g_rho = bwRho;
  g_minDist = minDist;
  g_maxDist = maxDist;
  g_bwStep = bwStep;
  g_simDur = simulationDuration;
  g_arNoise = CreateObject<NormalRandomVariable>();
  g_arNoise->SetAttribute("Mean", DoubleValue(0.0));
  g_arNoise->SetAttribute("Variance", DoubleValue(bwSigma * bwSigma));

  if (nWifiClients > nClient)
    nWifiClients = nClient;
  // 只对"在 wifi 上"的前 nWifiClients 个客户端做 AR(1) 波动
  for (uint32_t i = 0; i < nWifiClients; i++)
  {
    Ptr<MobilityModel> apMob = wifiApNode[i].Get(0)->GetObject<MobilityModel>();
    Vector apPos = apMob->GetPosition();
    Ptr<MobilityModel> staMob = wifiStaNodes[i].Get(0)->GetObject<MobilityModel>();
    ChanState cs;
    cs.staMob = staMob;
    cs.apX = apPos.x;
    cs.apY = apPos.y;
    cs.dist = meanDist;
    staMob->SetPosition(Vector(apPos.x + meanDist, apPos.y, 0.0));
    g_chan.push_back(cs);
  }

  if (!distLog.empty())
  {
    g_distLog.open(distLog.c_str());
    g_distLog << "time,client,dist_m\n";
    g_logDist = true;
  }
  // 只有开启波动时才调度信道驱动
  if (bwSigma > 0.0)
    Simulator::Schedule(Seconds(bwStep), &DriveChannel);

  // Internet stack
  InternetStackHelper stack;
  for (uint32_t i = 0; i < nClient; i++)
  {
    stack.Install(wifiApNode[i]);
    stack.Install(wifiStaNodes[i]);
  }
  stack.Install(sfuCenter);

  // IPv4
  Ipv4AddressHelper P2Paddress[nClient];
  Ipv4InterfaceContainer BackhaulIf[nClient];
  for (uint32_t i = 0; i < nClient; i++)
  {
    std::string ip = "10.1." + std::to_string(i + 1) + ".0";
    P2Paddress[i].SetBase(ns3::Ipv4Address(ip.c_str()), "255.255.255.0");
    BackhaulIf[i] = P2Paddress[i].Assign(backhaulDevices[i]);
  }
  Ipv4AddressHelper Wifiaddress[nClient];
  Ipv4InterfaceContainer APinterfaces[nClient];
  Ipv4InterfaceContainer Stainterfaces[nClient];
  for (uint32_t i = 0; i < nClient; i++)
  {
    std::string ip = "10.1." + std::to_string(i + 1 + nClient) + ".0";
    Wifiaddress[i].SetBase(ns3::Ipv4Address(ip.c_str()), "255.255.255.0");
    Stainterfaces[i] = Wifiaddress[i].Assign(staDevices[i]);
    APinterfaces[i] = Wifiaddress[i].Assign(apDevices[i]);
  }

  uint16_t client_ul = 80;
  uint16_t client_dl = 8080;
  uint16_t client_peer = 80;

  // VcaServer (SFU center)
  Ipv4Address serverAddr = BackhaulIf[0].GetAddress(1);
  Ptr<VcaServer> vcaServerApp = CreateObject<VcaServer>();
  vcaServerApp->SetLocalAddress(serverAddr);
  vcaServerApp->SetLocalUlPort(client_peer);
  vcaServerApp->SetPeerDlPort(client_dl);
  vcaServerApp->SetLocalDlPort(client_dl);
  vcaServerApp->SetNumNode(nClient);
  vcaServerApp->SetPolicy(static_cast<POLICY>(policy));
  vcaServerApp->SetDlpercentage(dl_percentage);
  vcaServerApp->SetQoEType(static_cast<QOE_TYPE>(qoeType));
  vcaServerApp->SetMlPred(mlpred);
  vcaServerApp->SetNodeId(sfuCenter.Get(0)->GetId());
  sfuCenter.Get(0)->AddApplication(vcaServerApp);
  vcaServerApp->SetStartTime(Seconds(0.0));
  vcaServerApp->SetStopTime(Seconds(simulationDuration + 2));

  // VcaClient per user
  for (uint32_t id = 0; id < nClient; id++)
  {
    for (uint8_t i = 0; i < nWifi[id]; i++)
    {
      Ipv4Address staAddr = Stainterfaces[id].GetAddress(i);
      Ipv4Address apAddr = BackhaulIf[id].GetAddress(i);

      // 前 nWifiClients 个客户端坐 wifi STA(带 AR(1) 波动); 其余走有线 backhaul。
      // (贴 Figure14 拓扑, 避免 n=8 全 wifi 的下行过载/饥饿)
      Ipv4Address local;
      Ptr<Node> local_node;
      if (id < nWifiClients)
      {
        local = staAddr;
        local_node = wifiStaNodes[id].Get(i);
      }
      else
      {
        local = apAddr;
        local_node = wifiApNode[id].Get(i);
      }
      Ptr<VcaClient> vcaClientApp = CreateObject<VcaClient>();
      vcaClientApp->SetFps(20);
      vcaClientApp->SetLocalAddress(local);
      vcaClientApp->SetPeerAddress(std::vector<Ipv4Address>{serverAddr});
      vcaClientApp->SetLocalUlPort(client_ul);
      vcaClientApp->SetLocalDlPort(client_dl);
      vcaClientApp->SetPeerPort(client_peer);
      vcaClientApp->SetNodeId(local_node->GetId());
      vcaClientApp->SetNumNode(nClient);
      vcaClientApp->SetPolicy(static_cast<POLICY>(policy));
      vcaClientApp->SetMlPred(mlpred);
      vcaClientApp->SetUlDlParams(kUlImprove, kDlYield);
      vcaClientApp->SetUlThresh(kLowUlThresh, kHighUlThresh);
      vcaClientApp->SetMaxBitrate(maxBitrateKbps);
      vcaClientApp->SetMinBitrate(minBitrateKbps);
      if (!transRateDir.empty())
        vcaClientApp->SetLogFile(transRateDir + "/transrate_node" +
                                 std::to_string(local_node->GetId()) + ".txt");
      local_node->AddApplication(vcaClientApp);

      Simulator::Schedule(Seconds(simulationDuration), &VcaClient::StopEncodeFrame, vcaClientApp);
      vcaClientApp->SetStartTime(Seconds(0.0));
      vcaClientApp->SetStopTime(Seconds(simulationDuration + 4));
    }
  }

  if (savePcap)
  {
    phy.SetPcapDataLinkType(WifiPhyHelper::DLT_IEEE802_11_RADIO);
    pointToPoint[0].EnablePcapAll("wtt");
    phy.EnablePcap("wtt-ap", apDevices[0].Get(0));
    phy.EnablePcap("wtt-sta", staDevices[0].Get(0));
  }

  FlowMonitorHelper flowmonHelper;
  flowmonHelper.InstallAll();

  Ipv4GlobalRoutingHelper::PopulateRoutingTables();

  Simulator::Stop(Seconds(simulationDuration + 5));
  Simulator::Run();
  flowmonHelper.SerializeToXmlFile("test-emulation.flowmon", true, true);
  if (g_logDist)
    g_distLog.close();
  Simulator::Destroy();
  return 0;
}
