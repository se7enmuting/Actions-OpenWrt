# ImmortalWrt 25.12.2 · PVE 手动编译

适用于 g-pve / b-pve 下的 x86_64 路由虚拟机。两地共用固件，网络、密码、订阅及 DDNS 凭据在安装后分别配置。

## 如何运行

进入仓库 Actions → **21 Build ImmortalWrt 25.12 PVE (Manual)** → **Run workflow**。

- operation=build：编译固件；默认保存 Artifact，并发布独立 Release。
- operation=configure：只准备源码、解析并检查配置，不下载全部编译依赖、不编译固件、不发布 Release。
- publish_release=false：只上传 Artifact；Artifact 保留 30 天，Release 不自动清理。

本 Workflow 只有 workflow_dispatch 触发器。提交代码、PR、定时任务或 repository_dispatch 均不会触发它。不触碰旧 Workflow、旧 Release，也不远程部署。

## 插件范围

| 功能 | 实现 |
|---|---|
| 代理 | 官方源 OpenClash 0.48.002；Mihomo 1.19.33；官方源 PassWall 26.10.22，Xray＋sing-box |
| 动态 DNS | 原生 luci-app-ddns；Cloudflare、DNSPod 腾讯云 API v3，HTTPS 与 CA 证书 |
| 设备流量与固定上下行限速 | Bandix 0.12.12（LuCI 0.12.12-r5），在设备规则里配置全天生效的上下行速率 |
| 设备历史统计 | 原生 nlbwmon，按 MAC 汇总；数据库保存到 /etc/nlbwmon，每小时提交 |
| 全网历史统计 | 原生 vnStat2，安装后选择真实 WAN 设备，避免叠加 WAN/WAN6 重复计数 |
| 游戏、视频、聊天应用限制 | ImmortalWrt 官方源 OpenAppFilter，包含匹配本次内核编译的 kmod-oaf |
| 主题 | 官方源 Argon 2.4.7 与配置插件；保留 Bootstrap 备用 |
| 其他 | WOL、UPnP、IPv6、LuCI HTTPS、SFTP、tcpdump、iperf3、dig、QEMU Guest Agent |

不包含 KMS、DDNS-Go、PassWall2、SQM、EQoS、旧 wrtbwmon、ramfree、旧 control-* 插件。不添加设备断网/定时上网插件。Bandix/OAF 本身附带的时间、配额等界面仍按上游保留，但不预设规则。

## 来源与版本

系统内核、基础树锁定官方 v25.12.2 release；packages/luci 使用官方 openwrt-25.12 维护分支在 2026-11-04 核对的固定提交，其他 feeds 使用 release 自带提交。不是 master/SNAPSHOT，也不修改第三方插件源码强制适配。

sources.lock.json 固定全部输入。以后升级要主动审阅并修改锁文件，不会在每次构建时自动追最新。

Bandix 是唯一额外引入的插件源，LuCI 和后端打包仓库均固定提交。后端沿用作者 Makefile 下载并校验的预编译 Rust/eBPF 二进制，不宣称本 Workflow 从 Rust 源码重编该二进制。Mihomo 也使用上游正式版、校验 SHA256 后嵌入，选择不要求 AVX 的 amd64-compatible 版本。

OpenAppFilter 的官方集成目前使用上游 v6.1.8 后端，LuCI 包显示 6.1.4；这是官方配套集成，版本号不等于未维护。没有额外切换到上游 7.x 或修改旧版来强制兼容。

## 默认行为与试机

- Argon、简体中文、上海时区；保留官方默认管理地址 192.168.1.1，不嵌入任何现网配置或凭据。
- x86/64 官方内核已内建 VirtIO 网卡、磁盘、SCSI、balloon、console；固件另包含 qemu-ga。PVE 内仍需为新 VM 启用 Guest Agent。
- Bandix 默认接口 br-lan，只开流量模块与历史保存，关闭连接、DNS 和 GeoIP 分析。实际 LAN 接口不同时先修改。监听 127.0.0.1，通过 LuCI 使用。
- 关闭软件/硬件流量卸载，不装 Turbo ACC；Bandix 与应用过滤需要可观察的数据路径。
- OpenClash、PassWall、应用过滤及 UPnP 默认关闭，安装后按需配置。两个代理先只启用一个。应用识别不是对任意加密协议或代理隧道的完整保证。
- 单设备固定限速由 Bandix 的设备上下行规则承担；这是流量限速，不是 SQM 队列公平调度。无需额外安装仅支持 IPv4 的 EQoS。
- vnStat2 必须在 LuCI 里指定实际出口接口。PPPoE、VLAN、多 LAN、双栈及代理流量的计数口径均需在现场验证。多个统计插件的数字不能直接相加。
- 在独立 PVE VM 上启动，接隔离网络，避免默认 LAN 地址/DHCP 与现网冲突。输出并不自动安装到现有 VM。
- 优先测试设备 IPv4/IPv6 归并、直连与代理计数、上下行限速、指定应用阻断、CPU/内存及历史数据重启保留情况。应用过滤尤其需要分别测试直连、QUIC、代理及双栈场景。
- 不整包恢复 18.06 配置。网络接口顺序、WAN/LAN、拨号、DNS 与 IPv6 配置需重新核对。

## 输出与验证范围

输出 BIOS/UEFI 两种启动方式的 ext4、squashfs 镜像，以及 QCOW2 镜像；根分区 2048 MiB、内核分区 64 MiB。新 VM 建议分配至少 4 GiB 虚拟磁盘、2 GiB 内存。

构建先运行 make defconfig，严格核对显式配置，避免插件依赖不满足时被静默取消。构建成功后再核对包清单、BTF/eBPF/VirtIO 内核选项和镜像完整性，才上传固件及发布 Release。

每次输出带 resolved.config、kernel.config、config.buildinfo、包清单、build-lock.json 和 SHA256SUMS。失败构建保留配置及日志供排查。构建通过不等于实际网络功能已验收。

### 上游

- https://github.com/immortalwrt/immortalwrt
- https://github.com/immortalwrt/packages
- https://github.com/immortalwrt/luci
- https://github.com/timsaya/luci-app-bandix
- https://github.com/timsaya/openwrt-bandix
- https://github.com/MetaCubeX/mihomo
- https://github.com/destan19/OpenAppFilter
