[CmdletBinding()]
param(
    [ValidateSet("saturation", "control", "smoke")]
    [string]$Profile = "saturation",
    [string]$PythonExe = "python",
    [int]$Port = 8000,
    [switch]$SkipInstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonCommand = Get-Command $PythonExe -ErrorAction Stop
$pythonPath = $pythonCommand.Source
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$resultDir = Join-Path $scriptRoot "results\$Profile-$timestamp"
New-Item -ItemType Directory -Force -Path $resultDir | Out-Null

if (-not $SkipInstall) {
    & $pythonPath -m pip install --disable-pip-version-check -r (Join-Path $scriptRoot "requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudieron instalar las dependencias de carga."
    }
}

$env:TPM = "34000"
$env:MAX_CONC = "4"
$env:BASE_MS = "250"
$env:MS_PER_TOK = "8"
$env:MAX_TOKENS = "128"
$env:TARGET_HOST = "http://127.0.0.1:$Port"
$env:LOAD_PROFILE = $Profile
$env:STAGE_SECONDS = "60"
$env:CONTROL_RAMP_SECONDS = "10"
$env:CONTROL_TOTAL_SECONDS = "70"
$env:SMOKE_SECONDS = "8"
$env:WAIT_MIN_SECONDS = "0.05"
$env:WAIT_MAX_SECONDS = "0.15"

$stdoutPath = Join-Path $resultDir "stub.stdout.txt"
$stderrPath = Join-Path $resultDir "stub.stderr.txt"
$stubPath = Join-Path $scriptRoot "llm_stub.py"
$stubProcess = $null

try {
    $stubProcess = Start-Process -FilePath $pythonPath -ArgumentList @("-u", $stubPath, "$Port") -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath

    $ready = $false
    foreach ($attempt in 1..30) {
        $client = [System.Net.Sockets.TcpClient]::new()
        try {
            $connect = $client.ConnectAsync("127.0.0.1", $Port)
            if ($connect.Wait(250) -and $client.Connected) {
                $ready = $true
                break
            }
        } catch {
            # El siguiente intento conserva el error real del proceso en stderr.
        } finally {
            $client.Dispose()
        }
        Start-Sleep -Milliseconds 200
    }
    if (-not $ready) {
        throw "El stub no quedó escuchando en el puerto $Port. Revisa $stderrPath."
    }

    $prefix = Join-Path $resultDir "locust"
    $report = Join-Path $resultDir "report.html"
    $locustArgs = @(
        "-m", "locust",
        "--config", (Join-Path $scriptRoot "locust.conf"),
        "--host", "http://127.0.0.1:$Port",
        "--csv", $prefix,
        "--csv-full-history",
        "--html", $report
    )
    & $pythonPath @locustArgs
    $locustExitCode = $LASTEXITCODE

    & $pythonPath (Join-Path $scriptRoot "analyze_results.py") --prefix $prefix --profile $Profile
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo generar el resumen de resultados."
    }

    Write-Output "Resultados: $resultDir"
    Write-Output "Código de salida Locust: $locustExitCode"
    if ($Profile -eq "smoke" -and $locustExitCode -ne 0) {
        throw "El smoke produjo fallos; revisa el reporte generado."
    }
    if ($locustExitCode -notin @(0, 1)) {
        throw "Locust terminó con código inesperado $locustExitCode."
    }
} finally {
    if ($null -ne $stubProcess -and -not $stubProcess.HasExited) {
        Stop-Process -Id $stubProcess.Id -Force
        $stubProcess.WaitForExit()
    }
}
