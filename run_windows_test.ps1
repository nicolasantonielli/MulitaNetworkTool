Param(
    # Vacio: el entorno queda en %LOCALAPPDATA%\Mulita\venv-win.
    # No puede vivir en la carpeta de Dropbox: guarda la ruta absoluta de Python
    # de la PC donde se creo y falla en la otra.
    [string]$VenvDirName = "",
    [switch]$RecreateVenv,
    [switch]$SkipTests,
    [switch]$TkLegacy,
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

function Test-VenvUsable {
    param(
        [Parameter(Mandatory = $true)][string]$Dir,
        [Parameter(Mandatory = $true)][string]$PythonExe
    )
    if (-not (Test-Path -LiteralPath $PythonExe)) {
        return $false
    }
    $cfgPath = Join-Path $Dir "pyvenv.cfg"
    if (-not (Test-Path -LiteralPath $cfgPath)) {
        return $false
    }
    foreach ($line in Get-Content -LiteralPath $cfgPath) {
        if ($line -match '^(home|executable)\s*=\s*(.+)$') {
            $candidate = $Matches[2].Trim()
            if ($Matches[1] -eq "home") {
                $candidate = Join-Path $candidate "python.exe"
            }
            if (-not (Test-Path -LiteralPath $candidate)) {
                Write-Host "Python base del entorno no existe en esta PC: $candidate"
                return $false
            }
        }
    }
    & $PythonExe -c "import sys" | Out-Null
    return $LASTEXITCODE -eq 0
}

$pythonCmd = Get-PythonCommand
$pythonExe = $pythonCmd[0]
$pythonArgs = @()
if ($pythonCmd.Count -gt 1) {
    $pythonArgs = $pythonCmd[1..($pythonCmd.Count - 1)]
}
if ([string]::IsNullOrWhiteSpace($VenvDirName)) {
    $venvDir = Join-Path $env:LOCALAPPDATA "Mulita\venv-win"
} elseif ([System.IO.Path]::IsPathRooted($VenvDirName)) {
    $venvDir = $VenvDirName
} else {
    $venvDir = Join-Path $Root $VenvDirName
}
$venvPy = Join-Path $venvDir "Scripts\python.exe"

$recreate = [bool]$RecreateVenv
if (-not $recreate -and (Test-Path -LiteralPath $venvDir) -and -not (Test-VenvUsable -Dir $venvDir -PythonExe $venvPy)) {
    Write-Host "El entorno virtual no sirve en esta PC. Se recrea."
    $recreate = $true
}

if ($recreate -and (Test-Path -LiteralPath $venvDir)) {
    Write-Host "Eliminando entorno virtual existente..."
    Remove-Item -LiteralPath $venvDir -Recurse -Force
}

if (-not (Test-Path -LiteralPath $venvPy)) {
    Write-Host "Creando entorno virtual en $venvDir ..."
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $venvDir) | Out-Null
    Invoke-Checked -Exe $pythonExe -Args (@($pythonArgs) + @("-m", "venv", $venvDir)) -Step "creacion del entorno virtual"
}

if (-not (Test-Path $venvPy)) {
    throw "No se pudo crear el entorno virtual en $venvDir"
}

Write-Host "Verificando pip en el entorno virtual..."
Invoke-Checked -Exe $venvPy -Args @("-m", "ensurepip", "--upgrade") -Step "bootstrap de pip"

Write-Host "Instalando dependencias del proyecto..."
Invoke-Checked -Exe $venvPy -Args @("-m", "pip", "install", "-r", "requirements.txt") -Step "instalacion de dependencias"

if (-not $TkLegacy) {
    Write-Host "Instalando dependencias para UI Qt Quick en Windows..."
    Invoke-Checked -Exe $venvPy -Args @("-m", "pip", "install", "PyQt5") -Step "instalacion de PyQt5"
}

if (-not $SkipTests) {
    Write-Host "Ejecutando tests..."
    Invoke-Checked -Exe $venvPy -Args @("-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py") -Step "ejecucion de tests"
}

if ($NoUi) {
    Write-Host "Listo: entorno preparado para Windows."
    exit 0
}

$env:MULITA_TEST = "1"
if ($TkLegacy) {
    # Fallback util para pruebas rapidas sin dependencias Qt.
    $launchArgs = @("main.py", "--tk", "--no-keyboard") + $AppArgs
}
else {
    # Modo por defecto: UI final en Qt Quick.
    # En escritorio Windows no suele haber teclado virtual Qt configurado.
    $launchArgs = @("main.py", "--no-keyboard") + $AppArgs
}

Write-Host "Iniciando app en modo test (simulacion)..."
Invoke-Checked -Exe $venvPy -Args $launchArgs -Step "arranque de la app"
