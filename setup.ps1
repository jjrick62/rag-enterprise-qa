<#
.SYNOPSIS
    RAG Enterprise QA 一键部署脚本
.DESCRIPTION
    创建虚拟环境、安装依赖、下载模型、摄入文档、启动服务
.PARAMETER SkipModels
    跳过模型下载（模型已存在时使用）
.PARAMETER SkipIngest
    跳过文档摄入（ChromaDB 索引已存在时使用）
.PARAMETER Port
    服务端口，默认 8080
.EXAMPLE
    .\setup.ps1                          # 完整部署
    .\setup.ps1 -SkipModels              # 跳过模型下载
    .\setup.ps1 -SkipModels -SkipIngest  # 仅启动服务
#>

param(
    [switch]$SkipModels,
    [switch]$SkipIngest,
    [int]$Port = 8080
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $projectRoot "backend"

Write-Host @"
========================================
 RAG Enterprise QA — 部署脚本
========================================
 项目目录: $projectRoot
 后端目录: $backendDir
 服务端口: $Port
========================================
"@

# ── 1. 检查 Python ──
Write-Host "`n[1/5] 检查 Python 环境..." -ForegroundColor Cyan
try {
    $pyVersion = & python --version 2>&1
    Write-Host "  $pyVersion"
} catch {
    Write-Host "  [ERROR] Python 未找到，请先安装 Python 3.12+" -ForegroundColor Red
    exit 1
}

# ── 2. 创建虚拟环境 + 安装依赖 ──
Write-Host "`n[2/5] 配置虚拟环境..." -ForegroundColor Cyan
$venvPath = Join-Path $backendDir "venv"

if (-not (Test-Path $venvPath)) {
    Write-Host "  创建 venv..."
    & python -m venv $venvPath
}

$pip = Join-Path $venvPath "Scripts\pip.exe"
Write-Host "  安装依赖..."
& $pip install -r (Join-Path $backendDir "requirements.txt") -q 2>&1 | Select-Object -Last 3

# ── 3. 配置 .env ──
Write-Host "`n[3/5] 配置环境变量..." -ForegroundColor Cyan
$envFile = Join-Path $backendDir ".env"
$envExample = Join-Path $backendDir ".env.example"

if (-not (Test-Path $envFile)) {
    Copy-Item $envExample $envFile
    Write-Host "  已从 .env.example 创建 .env"
    Write-Host "  [TODO] 请编辑 $envFile 填入 MIMO_API_KEY" -ForegroundColor Yellow
} else {
    Write-Host "  .env 已存在，跳过"
}

# ── 4. 下载模型 ──
Write-Host "`n[4/5] 下载模型..." -ForegroundColor Cyan
if ($SkipModels) {
    Write-Host "  已跳过 (--SkipModels)"
} else {
    $downloadScript = Join-Path $backendDir "download_models.py"
    & (Join-Path $venvPath "Scripts\python.exe") $downloadScript
}

# ── 5. 摄入文档 ──
Write-Host "`n[5/5] 摄入文档到 ChromaDB..." -ForegroundColor Cyan
if ($SkipIngest) {
    Write-Host "  已跳过 (--SkipIngest)"
} else {
    Write-Host "  跳过（服务启动后在浏览器点击「全量重摄入」或调用 API）"
    Write-Host "  API: curl -X POST http://localhost:$Port/api/documents/reingest-all"
}

# ── 启动 ──
Write-Host "`n========================================" -ForegroundColor Green
Write-Host " 部署完成！启动服务..." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "  API:      http://localhost:$Port/api/health"
Write-Host "  前端:     http://localhost:$Port/"
Write-Host "  展示页:   http://localhost:$Port/showcase.html"
Write-Host "  按 Ctrl+C 停止服务"
Write-Host "========================================"

Set-Location $backendDir
& (Join-Path $venvPath "Scripts\python.exe") -m uvicorn main:app --host 0.0.0.0 --port $Port
