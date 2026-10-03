# 小满 · 安装/卸载「每日自动备份」Windows 计划任务（ARD T-ENV-04）
#
# 作用：每天固定时间执行一次 tools/daily-backup.ps1（= vcs.ps1 save，提交并推送到本地 origin）。
# 为什么要：本项目不用 GitHub，用项目内裸仓库当远端；每天一个备份点 = 永远有回退余地。
# 影响面：只是多一个用户级计划任务，不需要管理员权限；卸载一条命令即可。
#
# 用法：
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools/install-daily-backup.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools/install-daily-backup.ps1 -Time 22:30 -WithData
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools/install-daily-backup.ps1 -RunNow
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools/install-daily-backup.ps1 -Uninstall

[CmdletBinding()]
param(
  [string]$Time = '21:00',
  [string]$TaskName = 'diannao-daily-backup',
  [switch]$Uninstall,
  [switch]$RunNow,
  [switch]$WithData
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Wrapper = Join-Path $Root 'tools\daily-backup.ps1'

function Get-BackupTask { Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue }

if ($Uninstall) {
  $t = Get-BackupTask
  if ($t) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host ('已卸载计划任务：{0}' -f $TaskName)
  } else {
    Write-Host ('计划任务不存在（无需卸载）：{0}' -f $TaskName)
  }
  return
}

if (-not (Test-Path $Wrapper)) { throw ('找不到备份脚本：{0}' -f $Wrapper) }

$taskArg = '-NoProfile -ExecutionPolicy Bypass -File "{0}"{1}' -f $Wrapper, $(if ($WithData) { ' -WithData' } else { '' })
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $taskArg -WorkingDirectory $Root
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$userId = '{0}\{1}' -f $env:USERDOMAIN, $env:USERNAME
$principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType Interactive -RunLevel Limited

try {
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description '小满(diannao) 每日自动备份：提交并推送到本地 origin' -Force | Out-Null
  Write-Host ('已注册计划任务：{0}（每天 {1}，用户 {2}）' -f $TaskName, $Time, $userId)
} catch {
  Write-Warning ('Register-ScheduledTask 失败：{0}' -f $_.Exception.Message)
  Write-Host '改用 schtasks /Create 重试（用户态，无需管理员）…'
  $tr = 'powershell.exe ' + $taskArg
  & schtasks /Create /F /TN $TaskName /SC DAILY /ST $Time /TR $tr | Out-Host
}

$task = Get-BackupTask
if (-not $task) { throw '注册后仍查不到该计划任务，请手动检查 Task Scheduler' }
$info = Get-ScheduledTaskInfo -TaskName $TaskName
Write-Host ('状态：{0}　下次运行：{1}' -f $task.State, $info.NextRunTime)

if ($RunNow) {
  Write-Host '手动触发一次，验证端到端可用…'
  Start-ScheduledTask -TaskName $TaskName
  $n = 0
  do { Start-Sleep -Seconds 2; $task = Get-BackupTask; $n++ } while ($task.State -eq 'Running' -and $n -lt 60)
  $info = Get-ScheduledTaskInfo -TaskName $TaskName
  Write-Host ('上次运行：{0}　LastTaskResult={1}（0 = 成功）' -f $info.LastRunTime, $info.LastTaskResult)
}
