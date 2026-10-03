<#
.SYNOPSIS
  小满（diannao）本地 GitHub 式版本控制工具（无远端服务器、无 .gitignore）

.DESCRIPTION
  本项目不做 GitHub 远端，也不需要 .gitignore：
    · 本地备份区 _backup/diannao.git 是一个【裸仓库】，通过 origin 扮演 GitHub 的角色；
      git push / pull / fetch / clone / tag / branch 全部照旧可用。
    · 忽略规则放在 .git/info/exclude（由 guard 维护），提交守卫会挡住密钥与体积产物，
      因此删除 .gitignore 之后依然不会误提交 .env / *.db / __pycache__ / eval_results.html。

  分支模型（与 GitHub 一致）：main（稳定，只接受合并）/ develop（集成）/
  feature/<名>（功能）/ hotfix/<名>（紧急修复）/ restore/<版本>-<时间>（回退验证）。

.NOTES
  本文件必须保存为 UTF-8 with BOM：Windows PowerShell 5.1 会把无 BOM 的 UTF-8 按 ANSI(GBK)
  解析，中文注释/文案会被截断并导致语法错误。若编辑后报 “Unexpected token”，请先补 BOM。

.EXAMPLE
  pwsh -File tools/vcs.ps1 status
  pwsh -File tools/vcs.ps1 save "feat(ui): 首页迁移到 UI v2"
  pwsh -File tools/vcs.ps1 save "chore: 备份" -WithData
  pwsh -File tools/vcs.ps1 feature ui-home
  pwsh -File tools/vcs.ps1 finish
  pwsh -File tools/vcs.ps1 release 0.3.0
  pwsh -File tools/vcs.ps1 rollback v0.2.0          # 安全回退：新建 restore 分支
  pwsh -File tools/vcs.ps1 rollback v0.2.0 -Hard    # 危险：直接重置当前分支
  pwsh -File tools/vcs.ps1 verify -Fast
#>
[CmdletBinding()]
param(
  [Parameter(Position = 0)][string]$Command = 'help',
  [Parameter(Position = 1)][string]$Arg,
  [switch]$Hard,
  [switch]$Force,
  [switch]$WithData,
  [switch]$Fast
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $Root

$BarePath    = (($Root -replace '\\', '/') + '/_backup/diannao.git')
$SnapshotDir = Join-Path $Root '_backup/db-snapshots'
$ExcludePath = Join-Path $Root '.git/info/exclude'
# ASCII 标记：幂等判断只用 ASCII，避免中文在 ANSI/UTF-8 之间往返导致判断失效
$GuardMarker = '# >>> diannao-local-exclude v1'
$DefaultHeader = @'
# git ls-files --others --exclude-from=.git/info/exclude
# Lines that start with '#' are comments.
'@

# ── 忽略规则块（写入 .git/info/exclude；等价于原 .gitignore）──────────────
$ExcludeBlock = @'
# >>> diannao-local-exclude v1  （本块由 tools/vcs.ps1 guard 维护）
# ==================================================================
# 小满（diannao）本地版控忽略规则
# 本项目不使用 .gitignore（文件已删除），忽略规则统一放在这里。
# 维护方式：tools/vcs.ps1 guard（幂等，可随时重刷；也用于新克隆环境）
# ==================================================================

# ── 本地备份区（裸仓库与数据快照，绝不入库）──
_backup/

# ── 运行产物：SQLite 长期记忆库（首次运行自动重建）──
data/*.db
data/*.db-journal
data/*.db-wal
data/*.db.bak

# ── Python 缓存 ──
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
.venv/
venv/
env/

# ── pytest 临时目录（测试必须用 --basetemp .pytest_tmp）──
.pytest_tmp/

# ── 密钥 / 环境变量 ──
.env
.env.*
!.env.example

# ── 评测产物（体积大且可再生）──
eval_results.csv
eval_results.html
eval_report.md

# ── 日志与临时文件 ──
*.log
_tune.py
_smoke.py
server.log
shot_online.png

# ── 编辑器 / 系统 ──
.vscode/
.idea/
.DS_Store
Thumbs.db
desktop.ini
'@

# 提交守卫：命中即拒绝提交（密钥）或自动撤出暂存（产物）
$SecretPatterns = @('(^|/)\.env$', '(^|/)\.env\.[^/]+$', '\.pem$', '\.key$', '(^|/)id_rsa', 'secrets?\.(json|ya?ml|txt)$')
$ArtifactPatterns = @('^_backup/', '^\.pytest_tmp/', '__pycache__/', '\.pyc$', '^data/.*\.db', '^eval_results\.', '^eval_report\.md$', '\.log$', '^\.venv/')

function Write-Head($t) { Write-Host ''; Write-Host "── $t " -ForegroundColor Cyan }
function Write-Ok($t)   { Write-Host "  ✓ $t" -ForegroundColor Green }
function Write-Warn2($t) { Write-Host "  ! $t" -ForegroundColor Yellow }
function Write-Err2($t) { Write-Host "  ✗ $t" -ForegroundColor Red }

function Invoke-Git {
  param([Parameter(ValueFromRemainingArguments = $true)][string[]]$GitArgs)
  # 2>&1：git 的提示信息走 stderr（如 Switched to branch…），并入正常输出，
  # 避免 Windows PowerShell 5.1 把它们渲染成红色 NativeCommandError。
  & git @GitArgs 2>&1 | ForEach-Object { $_.ToString() }
  if ($LASTEXITCODE -ne 0) { throw "git $($GitArgs -join ' ') 失败（exit $LASTEXITCODE）" }
}

function Get-CurrentBranch { (& git rev-parse --abbrev-ref HEAD).Trim() }
function Get-PythonExe {
  if ($env:DIANNAO_PYTHON -and (Test-Path $env:DIANNAO_PYTHON)) { return $env:DIANNAO_PYTHON }
  if (Test-Path 'E:\Python\python.exe') { return 'E:\Python\python.exe' }
  return 'python'
}

function Install-Guard {
  Write-Head 'guard：校验本地备份区 / origin / 忽略规则'
  # 1) 裸仓库
  if (-not (Test-Path $BarePath)) {
    & git init --bare -q $BarePath
    & git -C $BarePath symbolic-ref HEAD refs/heads/main
    Write-Ok "已创建本地裸仓库 $BarePath"
  } else { Write-Ok "本地裸仓库存在：$BarePath" }
  $bareHead = (& git -C $BarePath symbolic-ref --short HEAD).Trim()
  if ($bareHead -ne 'main') { & git -C $BarePath symbolic-ref HEAD refs/heads/main; Write-Ok '裸仓库默认分支已设为 main' }

  # 2) origin 指向本地裸仓库
  $url = ''
  try { $url = (& git remote get-url origin).Trim() } catch { }
  if ($url -ne $BarePath) {
    if ($url) { & git remote remove origin }
    & git remote add origin $BarePath
    Write-Ok "origin → $BarePath"
  } else { Write-Ok 'origin 已指向本地裸仓库' }

  # 3) 忽略规则：幂等判断只用 ASCII 标记；写文件用 .NET 显式指定 UTF-8 with BOM，
  #    避免 PowerShell 5.1 的 ANSI 往返把中文注释写坏（历史踩坑）。
  $content = if (Test-Path $ExcludePath) { Get-Content -Raw $ExcludePath } else { '' }
  if ($content -notmatch [regex]::Escape($GuardMarker)) {
    $custom = ($content -split "\r?\n") | Where-Object { $_ -and $_ -notmatch '^\s*#' }
    if ($custom) {
      $bakPath = "$ExcludePath.bak-" + (Get-Date -Format 'yyyyMMdd-HHmmss')
      Copy-Item -LiteralPath $ExcludePath -Destination $bakPath -Force
      Write-Warn2 "检测到已有自定义忽略规则，已备份到 $bakPath 后重写"
    }
    $text = $DefaultHeader + "`n`n" + $ExcludeBlock + "`n"
    [System.IO.File]::WriteAllText($ExcludePath, $text, (New-Object System.Text.UTF8Encoding($true)))
    Write-Ok '.git/info/exclude 已写入忽略规则（UTF-8 with BOM）'
  } else { Write-Ok '.git/info/exclude 忽略规则已就绪' }
}

function Test-Staged {
  $staged = @(& git diff --cached --name-only --diff-filter=ACMR)
  if (-not $staged -or $staged.Count -eq 0) { return $true }
  $secrets = @(); $artifacts = @()
  foreach ($f in $staged) {
    $p = $f -replace '\\', '/'
    foreach ($rx in $SecretPatterns) { if ($p -match $rx) { $secrets += $p; break } }
    foreach ($rx in $ArtifactPatterns) { if ($p -match $rx) { $artifacts += $p; break } }
  }
  if ($secrets.Count -gt 0) {
    Write-Err2 '检测到疑似密钥文件：已从暂存区撤出并中止提交 ——'
    foreach ($f in $secrets) { Write-Host "      $f"; & git reset -q -- $f }
    Write-Host '      （本项目约定：密钥永不入库；如确需提交请手动处理）'
    return $false
  }
  if ($artifacts.Count -gt 0 -and -not $Force) {
    Write-Warn2 '以下文件属于运行产物，已自动撤出暂存区：'
    foreach ($f in $artifacts) { Write-Host "      $f"; & git reset -q -- $f }
    Write-Host '      （强制提交请加 -Force；正常情况应被 .git/info/exclude 挡住）'
  }
  return $true
}

function Do-Snapshot {
  $ts = Get-Date -Format 'yyyyMMdd-HHmmss'
  $dest = Join-Path $SnapshotDir $ts
  New-Item -ItemType Directory -Force -Path $dest | Out-Null
  $n = 0
  foreach ($f in Get-ChildItem (Join-Path $Root 'data') -Filter '*.db' -ErrorAction SilentlyContinue) {
    Copy-Item $f.FullName (Join-Path $dest $f.Name) -Force; $n++
  }
  if ($n -gt 0) { Write-Ok "数据快照 $n 个 → _backup/db-snapshots/$ts" } else { Write-Warn2 'data/ 下没有可快照的 .db（尚未初始化记忆库）' }
}

switch ($Command.ToLower()) {

  'guard' { Install-Guard }

  'status' {
    Install-Guard
    Write-Head 'git status'
    & git status -sb
    Write-Head '最近 5 次提交'
    & git log --oneline --decorate -n 5
    Write-Head '落后/领先 origin'
    & git fetch -q origin 2>$null
    & git status -sb | Select-Object -First 1
  }

  'save' {
    Install-Guard
    $msg = $Arg
    if (-not $msg) { $msg = 'chore: 本地备份 ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') }
    & git add -A
    if (-not (Test-Staged)) { throw '提交被守卫中止（见上方提示）' }
    $staged = @(& git diff --cached --name-only)
    if (-not $staged -or $staged.Count -eq 0) { Write-Warn2 '没有需要提交的改动'; break }
    Write-Head "提交 $($staged.Count) 个文件"
    $staged | ForEach-Object { Write-Host "      $_" }
    Invoke-Git commit -q -m $msg
    $branch = Get-CurrentBranch
    Invoke-Git push -u origin $branch
    if ($WithData) { Do-Snapshot }
    Write-Ok "已提交并推送到本地 origin（分支 $branch）：$msg"
    & git log --oneline --decorate -n 1
  }

  'feature' {
    Install-Guard
    if (-not $Arg) { throw '用法：vcs.ps1 feature <名称>，例如 feature ui-home' }
    & git show-ref --verify --quiet refs/heads/develop
    $hasDevelop = ($LASTEXITCODE -eq 0)
    $base = if ($hasDevelop) { 'develop' } else { 'main' }
    Invoke-Git switch -c "feature/$Arg" $base
    Write-Ok "已基于 $base 创建并切换到 feature/$Arg"
    Write-Host '      完成后执行：pwsh -File tools/vcs.ps1 finish'
  }

  'finish' {
    Install-Guard
    $cur = Get-CurrentBranch
    if ($cur -notlike 'feature/*' -and $cur -notlike 'hotfix/*') { throw "当前分支 $cur 不是 feature/* 或 hotfix/*，无法 finish" }
    $target = if ($cur -like 'hotfix/*') { 'main' } else { 'develop' }
    & git show-ref --verify --quiet "refs/heads/$target"
    if ($LASTEXITCODE -ne 0) {
      Invoke-Git branch $target main
      Write-Ok "已从 main 创建 $target"
    }
    Invoke-Git switch $target
    Invoke-Git merge --no-ff -m "Merge branch '$cur' into $target" $cur
    Invoke-Git branch -d $cur
    Invoke-Git push -u origin $target
    Write-Ok "已把 $cur 以 --no-ff 合并进 $target 并删除该分支（等价 GitHub 上合并 PR 后删除分支）"
  }

  'release' {
    Install-Guard
    if (-not $Arg) { throw '用法：vcs.ps1 release <版本号>，例如 release 0.3.0' }
    $ver = $Arg.TrimStart('v')
    $cur = Get-CurrentBranch
    if ($cur -ne 'develop') { Write-Warn2 "当前不在 develop（在 $cur），仍继续（如需严格发布请先切回 develop）" }
    Invoke-Git switch main
    Invoke-Git merge --no-ff -m "Merge branch 'develop' (release v$ver)" develop
    Invoke-Git tag -a "v$ver" -m "release v$ver"
    Invoke-Git push -u origin main
    Invoke-Git push origin develop
    Invoke-Git push origin --tags
    if ($cur -ne 'main') { & git switch $cur | Out-Null }
    Write-Ok "已发布 v$ver：main 合并 develop、打标签并推送到本地 origin"
    & git tag -n1 --sort=-v:refname | Select-Object -First 5
  }

  'rollback' {
    Install-Guard
    if (-not $Arg) {
      Write-Head '可回退的版本（tag）'
      & git tag -n1 --sort=-v:refname
      Write-Host '      用法：vcs.ps1 rollback <tag|分支|commit>   [ -Hard ]'
      break
    }
    $ref = $Arg
    & git rev-parse --verify -q "$ref^{commit}" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "找不到版本：$ref" }
    if ($Hard) {
      Write-Warn2 "危险操作：把当前分支硬重置到 $ref（之后的本地提交将从当前分支消失，但本地 origin 仍保留，可 git reflog / fetch 找回）"
      Invoke-Git reset --hard $ref
      Write-Ok "已硬回退到 $ref"
    } else {
      $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
      $newBranch = "restore/$($ref -replace '[/\\]', '-')-$stamp"
      Invoke-Git switch -c $newBranch $ref
      Write-Ok "已创建并切换到 $newBranch（工作区内容 = $ref）"
      Write-Host '      验证无误后：git switch main && git merge --no-ff ' + $newBranch
      Write-Host '      确认放弃：  git switch main && git branch -D ' + $newBranch
    }
  }

  'log'      { & git log --graph --oneline --decorate -n 40 }
  'branches' { Install-Guard; & git branch -avv }
  'versions' { Write-Head '版本标签（新→旧）'; & git tag -n99 --sort=-v:refname }
  'sync'     { Install-Guard; Invoke-Git fetch origin --prune; & git status -sb }

  'verify' {
    $py = Get-PythonExe
    Install-Guard
    Write-Head "本地 CI：pytest（$py）"
    $pyArgs = @('-m', 'pytest', '-q', '--basetemp', '.pytest_tmp')
    if ($Fast) {
      $pyArgs += @('--ignore=tests/test_simulator.py', '--ignore=tests/test_event_ab.py', '--ignore=tests/test_baseline_fairness.py')
      Write-Host '      快速模式：跳过昂贵仿真测试'
    }
    & $py @pyArgs
    if ($LASTEXITCODE -eq 0) { Write-Ok '测试全部通过' } else { Write-Warn2 "pytest 退出码 $LASTEXITCODE（当前已知：缺 gradio/plotly 会导致 2 项失败，见 docs/ARD.md T-ENV-01）" }
  }

  'snapshot' { Do-Snapshot }

  'clone' {
    if (-not $Arg) { throw '用法：vcs.ps1 clone <目标目录>（灾难恢复演练：从本地备份区重新克隆）' }
    Invoke-Git clone $BarePath $Arg
    Write-Ok "已从本地备份区克隆到 $Arg"
  }

  default {
    Write-Host ''
    Write-Host '小满（diannao）本地 GitHub 式版本控制' -ForegroundColor Cyan
    Write-Host "  仓库根目录 : $Root"
    Write-Host "  本地远端   : $BarePath   （origin，扮演 GitHub）"
    Write-Host ''
    Write-Host '  常用命令：'
    Write-Host '    status                     查看工作区与最近提交'
    Write-Host '    save "<提交信息>"           提交全部改动并推送到本地 origin'
    Write-Host '    save "<信息>" -WithData     同时把 data/*.db 快照到 _backup/db-snapshots'
    Write-Host '    feature <名称>              从 develop 建功能分支'
    Write-Host '    finish                     功能分支 --no-ff 合并回 develop 并删除分支'
    Write-Host '    release <版本号>            develop 合并到 main + 打 tag + 推送（如 release 0.3.0）'
    Write-Host '    rollback [版本]            安全回退：新建 restore/<版本> 分支（不带参数则列出可回退版本）'
    Write-Host '    rollback <版本> -Hard      危险：直接硬重置当前分支'
    Write-Host '    log / branches / versions  历史 / 分支 / 版本标签'
    Write-Host '    verify [-Fast]             本地 CI：跑 pytest'
    Write-Host '    guard / sync / snapshot / clone <目录>'
    Write-Host ''
    Write-Host '  完整策略说明见 docs/VERSIONING.md'
  }
}
