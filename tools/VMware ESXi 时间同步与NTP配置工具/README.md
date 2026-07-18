# VMware ESXi 时间同步与NTP配置工具

一套基于 pyVmomi 开发的 vCenter 虚拟机时间同步排查 + ESXi 主机 NTP 批量配置工具，提供命令行和图形界面两种形式。

## 背景

修改 ESXi 主机时间前，如果虚拟机还开着"与主机同步时间"，主机时间一变会直接把这个跳变带进虚拟机（VMware Tools 重启/恢复时会立即同步过去，而不是缓慢过渡）。本工具的定位就是：**先摸清哪些VM开着同步、批量关掉，再批量改ESXi的NTP配置**，避免大规模误伤VM时间。

## 文件说明

- `vc_time_tool.py` —— 命令行工具，核心逻辑所在，GUI也复用这里的函数。
- `vc_time_gui.py` —— 图形界面版本，需要和 `vc_time_tool.py` 放在同一目录下运行。
- `vc_time_diag.py` —— 诊断脚本，dump单台VM的时间同步相关原始配置，排查扫描结果对不上时用。

## 主要功能

- **排查VM时间同步设置**：扫描所有VM是否开启"与主机同步时间"。同时兼容vSphere API 7.0前后的两套字段——`ToolsConfigInfo.syncTimeWithHost`（已废弃）和取代它的 `syncTimeWithHostAllowed`（vSphere 7+新版UI"启动和恢复时同步"实际生效的字段），避免新版UI配置的VM被误判为"未开启"。
- **批量关闭VM同步**：默认dry-run只打印清单，确认无误后加 `--confirm` 才真正执行；支持 `--vms` 只对指定VM生效。
- **批量配置ESXi NTP**：批量设置NTP服务器地址、开启ntpd开机自启并重启服务；同样是dry-run + `--confirm` 两步走，避免命令行手滑漏填参数误改全部生产主机。
- **检测主机与参考NTP源的时间差**（仅GUI）：直接向指定NTP服务器发一个标准NTP查询包，和ESXi主机当前时间比对，算出偏差秒数，偏差过大自动标红。
- **批量操作中自动重连**：几百台VM/主机的批量任务耗时较长，容易超过vCenter session空闲超时；命中 `NotAuthenticated` 时会自动用原凭据重新登录并继续，不需要重跑整个命令。

## 依赖

```
pip install pyvmomi
```

GUI额外需要 `tkinter`（Python自带；Ubuntu/Debian下如提示缺失：`sudo apt install python3-tk`）。

## 用法示例（CLI）

```bash
# 1) 排查所有VM是否开启"与主机同步时间"（改ESXi时间前必须先看这个）
python3 vc_time_tool.py --vcenter vcenter.example.com --user administrator@vsphere.local \
    check-vm-sync --csv vm_time_sync_report.csv

# 2) 批量取消所有开启了"与主机同步时间"的VM（先dry-run，确认后加--confirm执行）
python3 vc_time_tool.py --vcenter vcenter.example.com --user administrator@vsphere.local \
    disable-vm-sync
python3 vc_time_tool.py --vcenter vcenter.example.com --user administrator@vsphere.local \
    disable-vm-sync --confirm

# 3) 批量给ESXi主机配置NTP并重启ntpd（同样先dry-run，确认后加--confirm）
python3 vc_time_tool.py --vcenter vcenter.example.com --user administrator@vsphere.local \
    set-ntp --ntp 192.0.2.1
python3 vc_time_tool.py --vcenter vcenter.example.com --user administrator@vsphere.local \
    set-ntp --ntp 192.0.2.1 --confirm

# 4) 只对指定几台主机/VM生效
python3 vc_time_tool.py --vcenter vcenter.example.com --user administrator@vsphere.local \
    disable-vm-sync --vms VM1 VM2 --confirm
python3 vc_time_tool.py --vcenter vcenter.example.com --user administrator@vsphere.local \
    set-ntp --ntp 192.0.2.1 --hosts esxi01.example.com esxi02.example.com
```

GUI直接运行：

```bash
python3 vc_time_gui.py
```

## ⚠️ 注意事项

- 代码里默认**关闭了TLS证书校验**（`ssl.CERT_NONE`），适合内网自签证书的vCenter；如果你的环境需要校验证书，请自行修改 `connect_vcenter()`。
- `set-ntp` 会重启ESXi的ntpd服务，**重启后如果原时间偏差较大，ESXi会立即把时钟跳到新时间**（不是缓慢过渡），务必先确认好哪些VM还开着"与主机同步时间"、且已批量关闭，再执行这一步。
- `disable-vm-sync`、`set-ntp` 都要求二次确认（`--confirm`）才会真正生效，未加此参数只会打印将要修改的清单（dry-run）。
- vCenter账号密码建议用交互输入（不填 `--password` 参数），避免明文出现在shell历史记录里。

## License

本目录脚本遵循 MIT License 发布。
