"""PSADT wrapper generator tests."""

from silentinstallhq_mcp.psadt.generator import (
    generate_psadt_v4_wrapper,
    parse_installer_command,
)
from silentinstallhq_mcp.scraper.parser import parse_guide_summaries, rank_guide_for_psadt

BASE_URL = "https://silentinstallhq.com"


def test_parse_msi_install_command():
    cmd = parse_installer_command(
        "MsiExec.exe /i Proximity.msi ALLUSERS=1 LAUNCHPROXIMITY=0 ACCEPTEULA=1 /qn"
    )
    assert cmd is not None
    assert cmd.installer_type == "MSI"
    assert cmd.file_name == "Proximity.msi"
    assert "/qn" in cmd.arguments


def test_generate_wrapper_contains_core_psadt_elements():
    script = generate_psadt_v4_wrapper(
        software_title="Cisco Proximity",
        vendor="Cisco Systems, Inc.",
        installer_type="MSI",
        silent_install_switch=(
            "MsiExec.exe /i Proximity.msi ALLUSERS=1 LAUNCHPROXIMITY=0 ACCEPTEULA=1 /qn"
        ),
        silent_uninstall_switch="MsiExec.exe /x Proximity.msi /qn",
    )

    assert "function Install-ADTDeployment" in script
    assert "function Uninstall-ADTDeployment" in script
    assert "Start-ADTMsiProcess -Action Install" in script
    assert "AppName = 'Cisco Proximity'" in script
    assert "Open-ADTSession" in script


def test_rank_guide_for_psadt_prefers_v4():
    guides = parse_guide_summaries(
        """
        <article>
          <h2 class="entry-title">
            <a href="https://silentinstallhq.com/foo-silent-install-how-to-guide/">How-To</a>
          </h2>
        </article>
        <article>
          <h2 class="entry-title">
            <a href="https://silentinstallhq.com/foo-install-and-uninstall-psadt-v4/">PSADT v4</a>
          </h2>
        </article>
        """,
        BASE_URL,
    )
    best = rank_guide_for_psadt(guides, "Foo")
    assert best is not None
    assert best.guide_type == "psadt_v4"