# VMware 虚拟机未安装 VMware Tools 批量查询脚本
## 功能说明

### `find_no_tools_vms.ps1`
查询所有已开机但未安装 VMware Tools 的虚拟机（可筛选 Windows）。

- **适用平台**：VMware vSphere 6.x/7.x/8.x
- **依赖环境**：PowerCLI
- **使用方法**：
    1. 打开 PowerShell，加载 PowerCLI
    2. 登录 vCenter：
       ```powershell
       Connect-VIServer -Server <vcenter_ip> -User <user> -Password <password>
       ```
    3. 执行脚本：
       ```powershell
       .\find_no_tools_vms.ps1
       ```
    4. 查看输出结果

- **高级用法**：如需仅输出 Windows 虚拟机，取消对应脚本内的注释即可。
