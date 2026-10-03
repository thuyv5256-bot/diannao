# 小满 · 每日自动备份（供 Windows 计划任务调用；也可手动执行）
#
# 做什么：在仓库根目录执行一次 `tools/vcs.ps1 save`（= git add/commit/push 到本地 origin），
#         可选 -WithData 同时快照 data/*.db，并自动清理过旧快照、把过程写进 _backup/backup.log。
# 为什么：本项目不用 GitHub，靠本地裸仓库当远端；每日一次备份 = 每天至少一个可回退点。
# 失败影响：只影响备份，不影响开发；日志与退出码都会记录，计划任务里能看到 LastTaskResult。
#
# 用法：
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools/daily-backup.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools/daily-backup.ps1 -WithData

[CmdletBinding()]
param(
  [switch]$WithData,          # 同时快照 data/*.db（默认只提交代码与文档）
  [int]$KeepSnapshots = 14    # 保留最近 N 份数据快照，更旧的自动清理
)

$ErrorActionPreference = 'Continue'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Vcs  = Join-Path $Root 'tools/vcs.ps1'
$Log  = Join-Path $Root '_backup/backup.log'

function Write-Log($text) {
  $line = '{0}  {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $text
  Write-Host $line
  try {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Log) | Out-Null
    Add-Content -Path $Log -Value $line -Encoding UTF8
  } catch { Write-Host ('（日志写入失败：{0}）' -f $_.Exception.Message) }
}

Write-Log '── 每日自动备份开始 ──'

if (-not (Test-Path $Vcs)) {
  Write-Log ('失败：找不到 {0}' -f $Vcs)
  exit 2
}

$vcsArgs = @('save')
if ($WithData) { $vcsArgs += '-WithData' }
$out = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Vcs @vcsArgs 2>&1
$code = $LASTEXITCODE
$out | ForEach-Object { Write-Host $_ }
if ($code -ne 0) {
  Write-Log ('失败：vcs.ps1 save 退出码 {0}' -f $code)
  exit $code
}
if (($out | Out-String) -match '没有需要提交的改动') {
  Write-Log '完成：本次没有需要提交的改动'
} else {
  $head = (& git -C $Root log --oneline -n 1) 2>$null
  Write-Log ('完成：已提交并推送到本地 origin → {0}' -f $head)
}

# 清理过旧的数据快照（快照不入库，长期会累积）
$snapDir = Join-Path $Root '_backup/db-snapshots'
if (Test-Path $snapDir) {
  $dirs = @(Get-ChildItem $snapDir -Directory | Sort-Object Name)
  if ($dirs.Count -gt $KeepSnapshots) {
    $dirs | Select-Object -First ($dirs.Count - $KeepSnapshots) | ForEach-Object {
      Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
      Write-Log ('清理旧快照 {0}' -f $_.Name)
    }
  }
}

Write-Log '── 每日自动备份结束 ──'
exit 0
