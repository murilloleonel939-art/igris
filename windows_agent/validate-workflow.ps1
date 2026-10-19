$ErrorActionPreference = "Stop"
$workflow = Get-Content (Join-Path $PSScriptRoot "../.github/workflows/build-windows-agent.yml") -Raw
$required = @(
    "windows_agent/output/IgrisAgentSetup-v11.exe",
    "web/public/downloads/IgrisAgentSetup-v11.exe",
    "git add web/public/downloads/IgrisAgentSetup-v11.exe"
)
foreach ($value in $required) {
    if (-not $workflow.Contains($value)) { throw "Workflow incompleto: $value" }
}
if (-not $workflow.Contains("runs-on: windows-latest")) { throw "El build debe ejecutarse en Windows" }
if (-not $workflow.Contains("windows_agent/requirements.txt")) { throw "El workflow no vigila las dependencias del agente" }
if (-not $workflow.Contains("ISCC.exe")) { throw "El workflow no compila el instalador con Inno Setup" }
if (-not $workflow.Contains("Copy-Item windows_agent/output/IgrisAgentSetup-v11.exe web/public/downloads/IgrisAgentSetup-v11.exe -Force")) {
    throw "El instalador v11 no se copia al frontend"
}
$build = Get-Content (Join-Path $PSScriptRoot "build-exe.ps1") -Raw
foreach ($module in @("docx", "openpyxl", "pptx")) {
    if (-not $build.Contains("--collect-all $module")) { throw "El ejecutable no incluye recursos de $module" }
}
if (-not $build.Contains("--hidden-import websockets")) { throw "Falta soporte del cliente WebSocket" }
foreach ($import in @("--hidden-import tkinter", "--hidden-import _tkinter")) {
    if (-not $build.Contains($import)) { throw "Falta soporte de configuración gráfica: $import" }
}
$requirements = Get-Content (Join-Path $PSScriptRoot "requirements.txt") -Raw
foreach ($dependency in @("python-docx", "openpyxl", "python-pptx")) {
    if (-not $requirements.Contains($dependency)) { throw "Falta dependencia: $dependency" }
}
$iss = Get-Content (Join-Path $PSScriptRoot "igris-agent.iss") -Raw
foreach ($directive in @(
    'OutputBaseFilename=IgrisAgentSetup-v11',
    'Name: "{group}\IGRIS Windows Agent"',
    'Name: "{group}\Configurar IGRIS"',
    'Name: "{group}\Desinstalar IGRIS Windows Agent"',
    'CreateUninstallRegKey=yes',
    'UninstallDisplayName=IGRIS Windows Agent'
)) {
    if (-not $iss.Contains($directive)) { throw "El instalador no contiene: $directive" }
}
Write-Host "Configuración del instalador v11 coherente."
