"""Generate minimal PSADT v4 wrappers from silent install metadata."""

# ruff: noqa: E501

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class InstallerCommand:
    """Parsed silent install/uninstall command."""

    installer_type: str
    file_name: str | None
    arguments: str
    raw_command: str


def _escape_ps_string(value: str) -> str:
    return value.replace("'", "''")


def parse_installer_command(command: str | None) -> InstallerCommand | None:
    """Parse a silent install or uninstall command line."""
    if not command:
        return None

    raw = re.sub(r"\s+", " ", command.strip())

    msi_match = re.search(
        r"msiexec(?:\.exe)?\s+/(?:i|x|fa|f)\s+([^\s]+\.msi)\s*(.*)",
        raw,
        re.I,
    )
    if msi_match:
        return InstallerCommand(
            installer_type="MSI",
            file_name=msi_match.group(1),
            arguments=msi_match.group(2).strip(),
            raw_command=raw,
        )

    exe_match = re.search(r"([^\s\\]+\.(?:exe|msi))\s+(.*)", raw, re.I)
    if exe_match:
        ext = exe_match.group(1).rsplit(".", 1)[-1].lower()
        return InstallerCommand(
            installer_type="MSI" if ext == "msi" else "EXE",
            file_name=exe_match.group(1),
            arguments=exe_match.group(2).strip(),
            raw_command=raw,
        )

    return InstallerCommand(
        installer_type="Unknown",
        file_name=None,
        arguments=raw,
        raw_command=raw,
    )


def generate_psadt_v4_wrapper(
    *,
    software_title: str,
    vendor: str | None = None,
    installer_type: str | None = None,
    silent_install_switch: str | None = None,
    silent_uninstall_switch: str | None = None,
    processes_to_close: list[str] | None = None,
    psadt_version: str = "4.1.8",
) -> str:
    """Build a minimal PSADT v4 Invoke-AppDeployToolkit.ps1 from switch metadata."""
    app_name = _escape_ps_string(software_title)
    app_vendor = _escape_ps_string(vendor or "Unknown")
    install_cmd = parse_installer_command(silent_install_switch)
    uninstall_cmd = parse_installer_command(silent_uninstall_switch)
    resolved_installer_type = installer_type
    if not resolved_installer_type:
        resolved_installer_type = install_cmd.installer_type if install_cmd else "EXE"

    process_blocks = ""
    if processes_to_close:
        entries = ",\n        ".join(
            f"@{{ Name = '{_escape_ps_string(name)}'; Description = '{app_name}' }}"
            for name in processes_to_close
        )
        process_blocks = f"""
    AppProcessesToClose = @(
        {entries}
    )"""

    install_body = _render_install_body(install_cmd, resolved_installer_type)
    uninstall_body = _render_uninstall_body(
        app_name=app_name,
        uninstall_cmd=uninstall_cmd,
        installer_type=resolved_installer_type,
    )

    today = date.today().isoformat()
    return f"""<#
.SYNOPSIS
    PSAppDeployToolkit - Generated wrapper for {software_title}.

.DESCRIPTION
    Auto-generated PSADT v4 deployment script based on Silent Install HQ switch metadata.
    Place installers under the PSADT Files folder before deployment.

.EXAMPLE
    powershell.exe -File Invoke-AppDeployToolkit.ps1 -DeploymentType Install -DeployMode Silent

.EXAMPLE
    powershell.exe -File Invoke-AppDeployToolkit.ps1 -DeploymentType Uninstall -DeployMode Silent
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [ValidateSet('Install', 'Uninstall', 'Repair')]
    [string]$DeploymentType,

    [Parameter(Mandatory = $false)]
    [ValidateSet('Auto', 'Interactive', 'NonInteractive', 'Silent')]
    [string]$DeployMode,

    [Parameter(Mandatory = $false)]
    [switch]$SuppressRebootPassThru,

    [Parameter(Mandatory = $false)]
    [switch]$TerminalServerMode,

    [Parameter(Mandatory = $false)]
    [switch]$DisableLogging
)

$adtSession = @{{
    AppVendor = '{app_vendor}'
    AppName = '{app_name}'
    AppVersion = ''
    AppArch = ''
    AppLang = 'EN'
    AppRevision = '01'
    AppSuccessExitCodes = @(0)
    AppRebootExitCodes = @(1641, 3010){process_blocks}
    AppScriptVersion = '1.0.0'
    AppScriptDate = '{today}'
    AppScriptAuthor = 'mcp-server-silentinstallhq'
    RequireAdmin = $true
    InstallName = ''
    InstallTitle = ''
    DeployAppScriptFriendlyName = $MyInvocation.MyCommand.Name
    DeployAppScriptParameters = $PSBoundParameters
    DeployAppScriptVersion = '{psadt_version}'
}}

function Install-ADTDeployment {{
    [CmdletBinding()]
    param()

    $adtSession.InstallPhase = $adtSession.DeploymentType
    Show-ADTInstallationProgress -StatusMessage "Installing $($adtSession.AppName). Please wait..."
{install_body}
}}

function Uninstall-ADTDeployment {{
    [CmdletBinding()]
    param()

    $adtSession.InstallPhase = $adtSession.DeploymentType
    Show-ADTInstallationProgress -StatusMessage "Uninstalling $($adtSession.AppName). Please wait..."
{uninstall_body}
}}

function Repair-ADTDeployment {{
    [CmdletBinding()]
    param()

    $adtSession.InstallPhase = $adtSession.DeploymentType
    Install-ADTDeployment
}}

$ErrorActionPreference = [System.Management.Automation.ActionPreference]::Stop
$ProgressPreference = [System.Management.Automation.ActionPreference]::SilentlyContinue
Set-StrictMode -Version 1

try {{
    if (Test-Path -LiteralPath "$PSScriptRoot\\PSAppDeployToolkit\\PSAppDeployToolkit.psd1" -PathType Leaf) {{
        Import-Module -FullyQualifiedName @{{
            ModuleName = "$PSScriptRoot\\PSAppDeployToolkit\\PSAppDeployToolkit.psd1"
            Guid = '8c3c366b-8606-4576-9f2d-4051144f7ca2'
            ModuleVersion = '{psadt_version}'
        }} -Force
    }} else {{
        Import-Module -FullyQualifiedName @{{
            ModuleName = 'PSAppDeployToolkit'
            Guid = '8c3c366b-8606-4576-9f2d-4051144f7ca2'
            ModuleVersion = '{psadt_version}'
        }} -Force
    }}

    $iadtParams = Get-ADTBoundParametersAndDefaultValues -Invocation $MyInvocation
    $adtSession = Remove-ADTHashtableNullOrEmptyValues -Hashtable $adtSession
    $adtSession = Open-ADTSession @adtSession @iadtParams -PassThru
}}
catch {{
    $Host.UI.WriteErrorLine((Out-String -InputObject $_ -Width ([System.Int32]::MaxValue)))
    exit 60008
}}

try {{
    & "$($adtSession.DeploymentType)-ADTDeployment"
    Close-ADTSession
}}
catch {{
    Write-ADTLogEntry -Message "Deployment failed: $($_.Exception.Message)" -Severity 3
    Close-ADTSession -ExitCode 60001
}}
"""


def _render_install_body(
    install_cmd: InstallerCommand | None,
    installer_type: str,
) -> str:
    if install_cmd is None:
        return """
    Write-ADTLogEntry -Message "No silent install switch was provided." -Severity 2
    Show-ADTInstallationPrompt -Message "No silent install switch was provided." -ButtonRightText 'OK'
"""

    file_name = install_cmd.file_name
    arguments = _escape_ps_string(install_cmd.arguments)

    if installer_type.upper() == "MSI" or (file_name and file_name.lower().endswith(".msi")):
        file_pattern = _escape_ps_string(file_name or "*.msi")
        return f"""
    $installer = Get-ChildItem -Path "$($adtSession.DirFiles)" -File -Recurse |
        Where-Object {{ $_.Name -like '{file_pattern}' }} |
        Select-Object -First 1

    if (-not $installer) {{
        Write-ADTLogEntry -Message "MSI installer matching '{file_pattern}' was not found." -Severity 2
        Show-ADTInstallationPrompt -Message "Installer was not found in Files." -ButtonRightText 'OK'
        return
    }}

    Start-ADTMsiProcess -Action Install -FilePath $installer.FullName -Parameters '{arguments}'
"""

    file_pattern = _escape_ps_string(file_name or "*.exe")
    return f"""
    $installer = Get-ChildItem -Path "$($adtSession.DirFiles)" -File -Recurse |
        Where-Object {{ $_.Name -like '{file_pattern}' }} |
        Select-Object -First 1

    if (-not $installer) {{
        Write-ADTLogEntry -Message "Installer matching '{file_pattern}' was not found." -Severity 2
        Show-ADTInstallationPrompt -Message "Installer was not found in Files." -ButtonRightText 'OK'
        return
    }}

    Start-ADTProcess -FilePath $installer.FullName -ArgumentList '{arguments}'
"""


def _render_uninstall_body(
    *,
    app_name: str,
    uninstall_cmd: InstallerCommand | None,
    installer_type: str,
) -> str:
    if uninstall_cmd and uninstall_cmd.installer_type == "MSI":
        file_pattern = _escape_ps_string(uninstall_cmd.file_name or "*.msi")
        arguments = _escape_ps_string(uninstall_cmd.arguments)
        return f"""
    $installer = Get-ChildItem -Path "$($adtSession.DirFiles)" -File -Recurse |
        Where-Object {{ $_.Name -like '{file_pattern}' }} |
        Select-Object -First 1

    if ($installer) {{
        Start-ADTMsiProcess -Action Uninstall -FilePath $installer.FullName -Parameters '{arguments}'
        return
    }}

    Uninstall-ADTApplication -Name '{app_name}' -ApplicationType 'MSI'
"""

    if uninstall_cmd and uninstall_cmd.raw_command:
        arguments = _escape_ps_string(uninstall_cmd.arguments or uninstall_cmd.raw_command)
        return f"""
    $uninstallExe = Get-ChildItem -Path "$($adtSession.DirFiles)" -File -Recurse |
        Where-Object {{ $_.Extension -eq '.exe' }} |
        Select-Object -First 1

    if ($uninstallExe) {{
        Start-ADTProcess -FilePath $uninstallExe.FullName -ArgumentList '{arguments}'
        return
    }}

    Uninstall-ADTApplication -Name '{app_name}'
"""

    if installer_type.upper() == "MSI":
        return f"""
    Uninstall-ADTApplication -Name '{app_name}' -ApplicationType 'MSI'
"""

    return f"""
    Uninstall-ADTApplication -Name '{app_name}'
"""