#requires -version 5
<#
.SYNOPSIS
    Roda as 3 suítes de teste do Pipefy Validator em sequência.

.DESCRIPTION
    1) pytest -unit + endpoints do server.py (Flask test client)
    2) vitest -funções utilitárias do frontend V2
    3) smoke  -Robot Framework HTTP contra container vivo na porta 8080

    Sempre roda os 3 e reporta no fim. Use -SkipSmoke se o container não estiver no ar.

.PARAMETER SkipSmoke
    Pula os smoke tests.

.EXAMPLE
    .\run-all-tests.ps1
    .\run-all-tests.ps1 -SkipSmoke
#>
param(
    [switch]$SkipSmoke
)

$ErrorActionPreference = 'Continue'

$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repo

$results = New-Object System.Collections.Generic.List[object]
$totalStart = Get-Date

function Write-Header($title) {
    Write-Host ""
    Write-Host "===============================================" -ForegroundColor DarkGray
    Write-Host ("  {0}" -f $title) -ForegroundColor Cyan
    Write-Host "===============================================" -ForegroundColor DarkGray
}

function Add-Result($name, $passed, $seconds, $detail) {
    $results.Add([pscustomobject]@{
        Suite    = $name
        Passed   = $passed
        Seconds  = $seconds
        Detail   = $detail
    })
}

function Format-Seconds($ts) {
    return ('{0:N2}' -f $ts.TotalSeconds)
}

# 1) pytest --------------------------------------------------------------
Write-Header "1/3  pytest (server.py)"
$start = Get-Date
$pyOutput = & python -m pytest tests/python/ 2>&1 | Out-String
$exit = $LASTEXITCODE
Write-Host $pyOutput
$duration = (Get-Date) - $start
$secs = Format-Seconds $duration
if ($exit -eq 0) {
    # Linha de resumo: "============= 41 passed in 1.28s ============="
    $detail = if ($pyOutput -match '={3,}\s*(\d+)\s+passed') { "{0} testes" -f $Matches[1] } else { 'OK' }
    Add-Result 'pytest' $true $secs $detail
    Write-Host ("  -> pytest OK em {0}s" -f $secs) -ForegroundColor Green
} else {
    Add-Result 'pytest' $false $secs ("exit={0}" -f $exit)
    Write-Host ("  -> pytest FALHOU (exit {0})" -f $exit) -ForegroundColor Red
}

# 2) vitest --------------------------------------------------------------
Write-Header "2/3  vitest (frontend utils)"
$start = Get-Date
if (-not (Test-Path 'node_modules')) {
    Write-Host "node_modules ausente, rodando npm install..." -ForegroundColor Yellow
    & npm install --silent 2>&1 | Out-Null
}
$jsOutput = & npm test 2>&1 | Out-String
$exit = $LASTEXITCODE
Write-Host $jsOutput
$duration = (Get-Date) - $start
$secs = Format-Seconds $duration
if ($exit -eq 0) {
    # vitest output tem ANSI codes, regex tolerante: "Tests  ... 35 passed (35)"
    $clean = ($jsOutput -replace '\x1B\[[0-9;]*[a-zA-Z]', '')
    $detail = if ($clean -match 'Tests[^0-9]+(\d+)\s+passed') { "{0} testes" -f $Matches[1] } else { 'OK' }
    Add-Result 'vitest' $true $secs $detail
    Write-Host ("  -> vitest OK em {0}s" -f $secs) -ForegroundColor Green
} else {
    Add-Result 'vitest' $false $secs ("exit={0}" -f $exit)
    Write-Host ("  -> vitest FALHOU (exit {0})" -f $exit) -ForegroundColor Red
}

# 3) smoke ---------------------------------------------------------------
if ($SkipSmoke) {
    Write-Header "3/3  smoke (PULADO via -SkipSmoke)"
    Add-Result 'smoke' $true '0.00' 'pulado'
} else {
    Write-Header "3/3  smoke (Robot Framework HTTP)"
    $start = Get-Date

    $up = $false
    try {
        $hc = Invoke-WebRequest -Uri 'http://localhost:8080/api/configs' -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
        $up = ($hc.StatusCode -eq 200)
    } catch {
        $up = $false
    }

    if (-not $up) {
        Write-Host "Container nao responde em http://localhost:8080. Sobe com:" -ForegroundColor Yellow
        Write-Host "    docker-compose up -d" -ForegroundColor Yellow
        $duration = (Get-Date) - $start
        Add-Result 'smoke' $false (Format-Seconds $duration) 'container offline'
    } else {
        $smokeOutput = & python -m robot --outputdir results/smoke -t "HC-*" tests/smoke_api.robot 2>&1 | Out-String
        $exit = $LASTEXITCODE
        Write-Host $smokeOutput
        $duration = (Get-Date) - $start
        $secs = Format-Seconds $duration
        if ($exit -eq 0) {
            $detail = if ($smokeOutput -match '(\d+)\s+tests,\s+(\d+)\s+passed') { "{0}/{1} testes" -f $Matches[2], $Matches[1] } else { 'OK' }
            Add-Result 'smoke' $true $secs $detail
            Write-Host ("  -> smoke OK em {0}s" -f $secs) -ForegroundColor Green
        } else {
            Add-Result 'smoke' $false $secs ("exit={0}" -f $exit)
            Write-Host ("  -> smoke FALHOU (exit {0}) - veja results/smoke/log.html" -f $exit) -ForegroundColor Red
        }
    }
}

# Resumo final -----------------------------------------------------------
$totalDuration = (Get-Date) - $totalStart
Write-Header "RESUMO"
$allPassed = $true
foreach ($r in $results) {
    $icon = if ($r.Passed) { 'OK' } else { 'X ' }
    $color = if ($r.Passed) { 'Green' } else { 'Red' }
    if (-not $r.Passed) { $allPassed = $false }
    $line = "  [{0}] {1,-8} {2,8}s   {3}" -f $icon, $r.Suite, $r.Seconds, $r.Detail
    Write-Host $line -ForegroundColor $color
}
Write-Host ""
Write-Host ("Total: {0}s" -f (Format-Seconds $totalDuration)) -ForegroundColor Cyan

if ($allPassed) {
    Write-Host "Todas as suites passaram." -ForegroundColor Green
    exit 0
} else {
    Write-Host "Houve falhas. Verifique acima." -ForegroundColor Red
    exit 1
}
