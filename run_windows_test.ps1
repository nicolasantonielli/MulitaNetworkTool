Param(
    [string]$VenvDirName = ".venv-win",
    [switch]$RecreateVenv,
    [switch]$SkipTests,
    [switch]$NoUi,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$AppArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Get-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @("py", "-3")
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @("python")
    }
    throw "No se encontro Python. Instala Python 3.10+ y vuelve a intentar."
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$Exe,
        [Parameter(Mandatory = $false)][string[]]$Args = @(),
        [Parameter(Mandatory = $true)][string]$Step
    )
    & $Exe @Args
    if ($LASTEXITCODE -ne 0) {
        throw "Fallo en: $Step (codigo $LASTEXITCODE)"
    }
}

$pythonCmd = Get-PythonCommand
$pythonExe = $pythonCmd[0]
$pythonArgs = @()
if ($pythonCmd.Count -gt 1) {
    $pythonArgs = $pythonCmd[1..($pythonCmd.Count - 1)]
}
$venvDir = Join-Path $Root $VenvDirName
$venvPy = Join-Path $venvDir "Scripts\python.exe"

if ($RecreateVenv -and (Test-Path $venvDir)) {
    Write-Host "Eliminando entorno virtual existente..."
    Remove-Item -Recurse -Force $venvDir
}

if (-not (Test-Path $venvPy)) {
    Write-Host "Creando entorno virtual..."
    Invoke-Checked -Exe $pythonExe -Args (@($pythonArgs) + @("-m", "venv", $VenvDirName)) -Step "creacion del entorno virtual"
}

if (-not (Test-Path $venvPy)) {
    throw "No se pudo crear el entorno virtual en $VenvDirName"
}

Write-Host "Verificando pip en el entorno virtual..."
Invoke-Checked -Exe $venvPy -Args @("-m", "ensurepip", "--upgrade") -Step "bootstrap de pip"

Write-Host "Instalando dependencias del proyecto..."
Invoke-Checked -Exe $venvPy -Args @("-m", "pip", "install", "-r", "requirements.txt") -Step "instalacion de dependencias"

if (-not $SkipTests) {
    Write-Host "Ejecutando tests..."
    Invoke-Checked -Exe $venvPy -Args @("-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py") -Step "ejecucion de tests"
}

if ($NoUi) {
    Write-Host "Listo: entorno preparado para Windows."
    exit 0
}

# En Windows evitamos la UI Qt de Raspberry y usamos la interfaz TK.
$env:MULITA_TEST = "1"
$launchArgs = @("main.py", "--tk", "--no-keyboard") + $AppArgs

Write-Host "Iniciando app en modo test (simulacion)..."
Invoke-Checked -Exe $venvPy -Args $launchArgs -Step "arranque de la app"
