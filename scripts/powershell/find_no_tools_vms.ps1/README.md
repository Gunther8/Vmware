# VMware VMs Without VMware Tools — Batch Query Script | VMware 虚拟机未安装 VMware Tools 批量查询脚本

## Overview | 功能说明

### `find_no_tools_vms.ps1`

Queries all powered-on virtual machines that do not have VMware Tools installed (optionally filtered to Windows VMs only).

查询所有已开机但未安装 VMware Tools 的虚拟机（可筛选 Windows）。

- **Platform | 适用平台**: VMware vSphere 6.x / 7.x / 8.x
- **Dependency | 依赖环境**: PowerCLI
- **Usage | 使用方法**:

    1. Open PowerShell and load PowerCLI.
       打开 PowerShell，加载 PowerCLI。
    2. Connect to vCenter | 登录 vCenter：
       ```powershell
       Connect-VIServer -Server <vcenter_ip> -User <user> -Password <password>
       ```
    3. Run the script | 执行脚本：
       ```powershell
       .\find_no_tools_vms.ps1
       ```
    4. Review the output | 查看输出结果。

- **Advanced usage | 高级用法**: To output Windows VMs only, uncomment the corresponding filter line in the script.
  如需仅输出 Windows 虚拟机，取消对应脚本内的注释即可。
