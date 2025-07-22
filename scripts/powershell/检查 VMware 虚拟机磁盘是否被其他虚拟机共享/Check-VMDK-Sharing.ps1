# 登录 vCenter
Connect-VIServer -Server 10.10.10.10 -User 666@vSphere.local -Password 123456

# 指定目标虚拟机名称
$targetVMName = "666"

# 获取目标虚拟机对象
$targetVM = Get-VM -Name $targetVMName

# 获取目标虚拟机所用的所有磁盘文件路径
$targetDisks = $targetVM | Get-HardDisk | Select-Object -ExpandProperty Filename

# 初始化结果
$sharedDisks = @()

# 检查是否有其他虚拟机也使用了这些磁盘
foreach ($disk in $targetDisks) {
    Write-Host "`n[检查磁盘] $disk" -ForegroundColor Cyan

    $vmsUsingDisk = Get-VM | Where-Object {
        $_.Name -ne $targetVMName -and (
            ($_ | Get-HardDisk | Where-Object { $_.Filename -eq $disk }).Count -gt 0
        )
    }

    if ($vmsUsingDisk.Count -gt 0) {
        Write-Host "以下虚拟机也使用了该磁盘：" -ForegroundColor Yellow
        $vmsUsingDisk | Select-Object Name
        $sharedDisks += $disk
    } else {
        Write-Host "该磁盘未被其他虚拟机使用。" -ForegroundColor Green
    }
}

# 最终判断
if ($sharedDisks.Count -eq 0) {
    Write-Host "`n✅ 所有磁盘仅属于虚拟机 $targetVMName，可以安全删除。" -ForegroundColor Green
} else {
    Write-Host "`n⚠️ 以下磁盘被其他虚拟机使用，删除前请谨慎确认：" -ForegroundColor Red
    $sharedDisks
}