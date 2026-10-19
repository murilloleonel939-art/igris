$ErrorActionPreference = "Stop"
$workflow = Get-Content (Join-Path $PSScriptRoot "../.github/workflows/build-windows-agent.yml") -Raw
$required = @(
    "windows_agent/output/IgrisAgentSetup-v10.exe",
    "web/public/downloads/IgrisAgentSetup-v10.exe",
    "git add web/public/downloads/IgrisAgentSetup-v10.exe"
)
foreach ($value in $required) {
    if (-not $workflow.Contains($value)) { throw "Workflow incompleto: $value" }
}
$build = Get-Content (Join-Path $PSScriptRoot "build-exe.ps1") -Raw
foreach ($module in @("docx", "openpyxl", "pptx")) {
    if (-not $build.Contains("--collect-all $module")) { throw "El ejecutable no incluye recursos de $module" }
}
$requirements = Get-Content (Join-Path $PSScriptRoot "requirements.txt") -Raw
foreach ($dependency in @("python-docx", "openpyxl", "python-pptx")) {
    if (-not $requirements.Contains($dependency)) { throw "Falta dependencia: $dependency" }
}
$iss = Get-Content (Join-Path $PSScriptRoot "igris-agent.iss") -Raw
if (-not $iss.Contains('OutputBaseFilename=IgrisAgentSetup-v10')) { throw "El instalador no está versionado como v10" }
Write-Host "Configuración del instalador v10 coherente."
