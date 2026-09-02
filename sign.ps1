[CmdletBinding(DefaultParameterSetName = "Pfx")]
param(
    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Leaf })]
    [string]$ExecutablePath,

    [Parameter(Mandatory = $true, ParameterSetName = "Pfx")]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Leaf })]
    [string]$CertificatePath,

    [Parameter(Mandatory = $true, ParameterSetName = "Pfx")]
    [string]$CertificatePassword,

    [Parameter(Mandatory = $true, ParameterSetName = "Store")]
    [ValidatePattern("^[A-Fa-f0-9]{40}$")]
    [string]$CertificateThumbprint,

    [string]$TimestampUrl = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"

function Find-SignTool {
    $command = Get-Command "signtool.exe" -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $programFilesX86 = [Environment]::GetFolderPath("ProgramFilesX86")
    $kitsRoot = Join-Path $programFilesX86 "Windows Kits\10\bin"
    if (Test-Path -LiteralPath $kitsRoot) {
        $candidate = Get-ChildItem -LiteralPath $kitsRoot -Directory |
            Sort-Object Name -Descending |
            ForEach-Object { Join-Path $_.FullName "x64\signtool.exe" } |
            Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
            Select-Object -First 1
        if ($candidate) {
            return $candidate
        }
    }

    throw "signtool.exe nao encontrado. Instale o Windows SDK."
}

$signTool = Find-SignTool
$executable = (Resolve-Path -LiteralPath $ExecutablePath).Path
$arguments = @("sign", "/fd", "SHA256", "/tr", $TimestampUrl, "/td", "SHA256")

if ($PSCmdlet.ParameterSetName -eq "Pfx") {
    $certificate = (Resolve-Path -LiteralPath $CertificatePath).Path
    $arguments += @("/f", $certificate, "/p", $CertificatePassword)
}
else {
    $arguments += @("/sha1", $CertificateThumbprint)
}

$arguments += @("/d", "osu! MP Link Miner", $executable)
& $signTool @arguments
if ($LASTEXITCODE -ne 0) {
    throw "SignTool falhou ao assinar o executavel (codigo $LASTEXITCODE)."
}

& $signTool verify /pa /v $executable
if ($LASTEXITCODE -ne 0) {
    throw "A verificacao Authenticode falhou (codigo $LASTEXITCODE)."
}

$signature = Get-AuthenticodeSignature -LiteralPath $executable
if ($signature.Status -ne "Valid") {
    throw "A assinatura nao e valida: $($signature.StatusMessage)"
}

Write-Host "Assinatura valida: $($signature.SignerCertificate.Subject)"
