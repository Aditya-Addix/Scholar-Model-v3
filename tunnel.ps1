$ErrorActionPreference = "Stop"

function Ensure-LocalTunnelInstalled {
    $ltCommand = Get-Command lt -ErrorAction SilentlyContinue
    if ($null -eq $ltCommand) {
        Write-Host "[setup] localtunnel not found. Installing globally via npm..." -ForegroundColor Yellow
        npm install -g localtunnel
        $ltCommand = Get-Command lt -ErrorAction SilentlyContinue
        if ($null -eq $ltCommand) {
            throw "localtunnel installation failed. Could not locate 'lt' command."
        }
    }

    return $ltCommand.Source
}

function Start-TunnelProcess {
    param(
        [Parameter(Mandatory = $true)][string]$LtExecutable,
        [Parameter(Mandatory = $true)][int]$Port,
        [Parameter(Mandatory = $true)][string]$LogPath
    )

    if (Test-Path $LogPath) {
        Remove-Item $LogPath -Force
    }

    return Start-Process -FilePath $LtExecutable -ArgumentList @("--port", "$Port") -RedirectStandardOutput $LogPath -RedirectStandardError $LogPath -PassThru
}

function Get-TunnelUrlFromLog {
    param(
        [Parameter(Mandatory = $true)][string]$LogPath,
        [int]$TimeoutSeconds = 45
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Path $LogPath) {
            $content = Get-Content $LogPath -Raw -ErrorAction SilentlyContinue
            if ($content) {
                $match = [regex]::Match($content, "https://[^\s]+")
                if ($match.Success) {
                    return $match.Value
                }
            }
        }
        Start-Sleep -Seconds 1
    }

    return "URL_PENDING"
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendLog = Join-Path $root "backend-tunnel.log"
$frontendLog = Join-Path $root "frontend-tunnel.log"

$backendProcess = $null
$frontendProcess = $null

try {
    $ltExecutable = Ensure-LocalTunnelInstalled

    Write-Host "[tunnel] starting backend tunnel on port 8000..." -ForegroundColor Cyan
    $backendProcess = Start-TunnelProcess -LtExecutable $ltExecutable -Port 8000 -LogPath $backendLog

    Write-Host "[tunnel] starting frontend tunnel on port 3000..." -ForegroundColor Cyan
    $frontendProcess = Start-TunnelProcess -LtExecutable $ltExecutable -Port 3000 -LogPath $frontendLog

    $backendUrl = Get-TunnelUrlFromLog -LogPath $backendLog
    $frontendUrl = Get-TunnelUrlFromLog -LogPath $frontendLog

    Write-Host ""
    Write-Host "==============================================================" -ForegroundColor Green
    Write-Host "ðŸš€ ADDIX Scholars IS LIVE ON MOBILE: $frontendUrl" -ForegroundColor Green
    Write-Host "ðŸš€ ADDIX Scholars BACKEND (API) URL: $backendUrl" -ForegroundColor Green
    Write-Host "==============================================================" -ForegroundColor Green
    Write-Host ""

    Write-Host "Press Ctrl+C to stop both tunnels." -ForegroundColor Yellow

    if ($backendProcess) {
        Wait-Process -Id $backendProcess.Id
    }
    if ($frontendProcess) {
        Wait-Process -Id $frontendProcess.Id
    }
}
finally {
    if ($backendProcess -and -not $backendProcess.HasExited) {
        Stop-Process -Id $backendProcess.Id -Force
    }
    if ($frontendProcess -and -not $frontendProcess.HasExited) {
        Stop-Process -Id $frontendProcess.Id -Force
    }
}

