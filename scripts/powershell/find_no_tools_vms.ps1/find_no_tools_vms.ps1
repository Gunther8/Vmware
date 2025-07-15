# 连接 vCenter
Connect-VIServer -Server <vcenter_ip> -User <user> -Password <password>

# 查询所有开机但未安装 VMware Tools 的虚拟机，按主机名称排序
Get-VM | Where-Object {
    $_.PowerState -eq "PoweredOn" -and 
    $_.ExtensionData.Guest.ToolsStatus -eq "toolsNotInstalled"
} | Select-Object Name, PowerState, @{N="ToolsStatus";E={$_.ExtensionData.Guest.ToolsStatus}} | Sort-Object Name

# 如需只筛选 Windows 系统虚拟机，请使用下面这段（取消注释即可）：
Get-VM | Where-Object { 
    $_.PowerState -eq "PoweredOn" -and 
    $_.GuestId -like "windows*" -and 
    $_.ExtensionData.Guest.ToolsStatus -eq "toolsNotInstalled" 
} | Select-Object Name, PowerState, @{N="ToolsStatus";E={$_.ExtensionData.Guest.ToolsStatus}}, GuestId | Sort-Object Name
