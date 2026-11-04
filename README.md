# Mulita Network Tool

Mulita Network Tool is a touchscreen network diagnostics application designed for Raspberry Pi OS Lite. It provides packet capture, connectivity tests, network discovery, switch-port identification, and configurable test servers through a Qt Quick interface.

The project also includes a Windows environment for interface development and selected simulations. English and Spanish interface languages are available.

## Contents

- [Compatibility and requirements](#compatibility-and-requirements)
- [Available functionality](#available-functionality)
- [Installation on Raspberry Pi](#installation-on-raspberry-pi)
- [Installation paths and user identity](#installation-paths-and-user-identity)
- [Starting and updating the application](#starting-and-updating-the-application)
- [Application settings](#application-settings)
- [Files and exported results](#files-and-exported-results)
- [Localization and export compatibility](#localization-and-export-compatibility)
- [Windows development environment](#windows-development-environment)
- [Verification and troubleshooting](#verification-and-troubleshooting)
- [Project structure](#project-structure)
- [License](#license)

## Compatibility and Requirements

### Primary platform

The primary deployment target is Raspberry Pi 4 running Raspberry Pi OS Lite with:

- Python 3.10 or later.
- APT and systemd.
- NetworkManager for Ethernet, Wi-Fi, and VLAN configuration.
- Qt 5, PyQt5, and Qt Quick Controls 2.
- Internet access during installation to retrieve system and Python dependencies.
- Administrator privileges for installation and privileged network operations.

The generated systemd service runs with root privileges. Manual execution without those privileges may not provide packet capture, network configuration, temporary SFTP users, or services on privileged ports.

### Supported display profiles

The unified installer requires one display parameter:

- **`5`: BTT-PITFT50 V1.0, 5-inch DSI panel.** Uses `vc4-kms-v3d`, `vc4-kms-dsi-7inch,disable_touch`, and `rpi-ft5406`.
- **`7`: Waveshare `7_0_inchH`, 7-inch panel connected to DSI1.** Uses `vc4-kms-v3d` and `vc4-kms-dsi-waveshare-panel,7_0_inchH`.

The `7inch` name in the BTT profile identifies the driver overlay; the installer parameter for that panel remains `5`. A DSI0 alternative is included as a commented line in the Waveshare boot configuration. The `7` profile selects DSI1.

The required overlay files must already be available in the operating system's boot partition. The installer checks their presence and does not download or build a replacement kernel.

Other displays and Raspberry Pi models are not covered by these predefined profiles. Raspberry Pi 5 is not established as a fully validated deployment target; the legacy DHT11 driver is explicitly skipped on that model.

### Windows

Windows is supported for development of the Qt Quick interface and selected simulations. Native Linux network management, raw Ethernet capture, GPIO access, and systemd service management require the Raspberry Pi environment.

Qt Quick is the only supported application interface.

## Available Functionality

### Packet capture and traffic diagnostics

- **Packet capture:** captures traffic from a selected interface to a PCAP file using `tcpdump`.
- **Ping and route diagnostics:** provides ICMP connectivity tests and route/latency information using the installed Linux tools.
- **TAP:** configures a software bridge and traffic mirroring between selected interfaces, with capture output and process controls. This is a software function rather than a dedicated hardware TAP.
- **Port scanning and host discovery:** provides Nmap port scanning and local-network discovery through `netdiscover`.

### Advanced Nmap analysis

The dedicated Nmap screen supports discovery, local ARP, TCP and UDP scans, service/version detection, operating-system detection, TLS, SMB, SSH, and HTTP checks.

Users can select a predefined profile or provide Nmap arguments. Commands execute as argument lists rather than shell scripts. Custom profiles can be saved, duplicated, and removed.

The interface supports stopping a scan, reviewing output, reopening scan history, reusing settings, and comparing two reports. Interrupted or incomplete results are identified as partial. A detected service version is not presented as proof of a vulnerability.

### Switch-port identification

The switch-port tool passively listens for LLDP and CDP announcements on an Ethernet interface. It reports available neighbor information, including device identity, port identifiers, descriptions, management addresses, and advertised VLAN information.

- Listening duration is configurable from 15 to 180 seconds, with a 60-second default.
- LLDP and CDP are retained as separate evidence sources.
- Expired or withdrawn announcements are removed.
- Local link status, speed, duplex, and error counters are displayed when available.
- Advertised native/voice VLANs are distinguished from VLAN tags observed in received traffic.
- Reports can be exported as JSON.

Live operation requires Linux and raw packet privileges. It does not require an IP address or modify the switch configuration. Windows and test mode display a marked demonstration.

A lack of announcements does not establish that no switch is present. Observed VLAN tags do not enumerate every permitted VLAN. EDP, PoE electrical measurements, cable wire mapping, and cable certification are not implemented.

### TLS assessment

The TLS screen integrates `testssl.sh` and provides certificate, protocol/cipher, vulnerability, and complete assessment profiles. Results are organized into certificate, protocol, cipher, vulnerability, and miscellaneous findings, with live output and CSV export.

Targets may be supplied as hostnames, IP addresses, URLs, or host/port combinations. The default port is 443. Results depend on network reachability; the tool does not validate every address behind a multi-address hostname.

`testssl.sh` is optional. If it cannot be installed, other application functions remain available and TLS assessment reports the missing dependency.

### Test servers

Multiple server types can operate concurrently, with one instance per type. Each server provides configuration and a log retaining the latest 500 entries, with CSV export.

- **iPerf3 — port 5201:** throughput testing with an external iPerf client.
- **TFTP — port 69:** file transfer from the configured TFTP directory. Uploads may replace existing files.
- **SFTP — port 2222:** a temporary account restricted to capture storage, with uploads directed to `respaldos`. The account is removed when the server stops.
- **HTTP/HTTPS — ports 80 and 443:** connection information, test downloads, and file access. HTTPS uses a locally generated certificate.
- **DNS — port 53:** responses for a configured test name, with optional forwarding. The default test name is `mulita.test`.
- **DHCP — port 67:** configurable address allocation and lease reporting. Startup is rejected on the interface carrying the default route.
- **NTP — port 123:** serves the device's system time with a configurable stratum.

Interface selection is available where applicable. DNS and DHCP require an interface with an IPv4 address. Certificates, keys, and internal server state are stored separately from shared capture files.

### Additional tools

The Tools section includes Wake-on-LAN, DHT11 temperature/humidity readings, download/upload speed testing, public IP information, Wi-Fi link details, MAC vendor lookup, and a file manager for capture storage and removable media.

Temperature and humidity readings require compatible hardware and the optional DHT11 driver. Public IP, vendor lookup, and Internet speed measurements require access to their external services.

### Features in preparation

The Vulnerabilities, Wi-Fi Audit, and ARP cybersecurity screens currently use placeholder interfaces. Their presence in the menu does not indicate an implemented assessment capability. Nmap, TLS assessment, test servers, and switch-port identification have dedicated implementations.

## Installation on Raspberry Pi

### Select and install a display profile

Run the installer from the repository directory containing `main.py` and `install-lite.sh`, preferably as the repository owner. Administrative operations request `sudo` as needed.

For the 5-inch BTT panel:

```bash
bash install-lite.sh 5
sudo reboot
```

For the 7-inch Waveshare panel on DSI1:

```bash
bash install-lite.sh 7
sudo reboot
```

The display parameter is mandatory. Missing, duplicate, or unsupported selections are rejected before installation begins. The former `install-lite_7.sh` has been replaced by the unified installer.

To view supported options:

```bash
bash install-lite.sh --help
```

### Installation behavior

The installer:

1. Validates arguments, repository files, and required system commands.
2. Installs Qt/QML, NetworkManager, diagnostic utilities, and server dependencies.
3. Checks required executable locations and Python compatibility.
4. Creates `.venv` with access to system-installed PyQt5 packages.
5. Installs Python requirements and checks dependency consistency.
6. Attempts optional TLS and DHT11 installation where applicable.
7. Verifies Python imports and QML compilation without launching network services.
8. Generates the installation configuration and systemd unit, then validates the unit.
9. Checks the selected display overlays and applies boot configuration.
10. Enables automatic application startup and preserves tty3 as a recovery console.

The integrated keyboard is implemented in QML and does not require Qt Virtual Keyboard packages. The installer neither reboots the device nor launches the application in the current session.

### Boot configuration and display changes

The installer uses `/boot/firmware` or `/boot`, depending on the operating system. It preserves the initial `config.txt` and `cmdline.txt` backups with the `.mulita-bak` suffix when those files are modified.

Managed display configuration is repeatable without duplicating active settings. To change panels, run the installer with the new display parameter and reboot. The previous managed display block is replaced to avoid simultaneous incompatible overlays.

## Installation Paths and User Identity

The installer detects the repository location and installation user. When invoked through `sudo`, it uses `SUDO_USER` to identify the original user.

Paths are stored in `/etc/mulita/config.json`:

- **New capture storage:** `<user-home>/capturas`.
- **New private state storage:** `<user-home>/.config/mulita`.
- **Application preferences:** `settings.json` within private state storage.
- **Server state:** the `servers` subdirectory within private state storage.

Reinstallation preserves configured storage paths. If legacy storage is found under root's home directory, it remains in use to retain access to existing data. Files are not moved or deleted automatically.

Custom storage locations can be selected during installation:

```bash
bash install-lite.sh 7 --capture-dir /srv/mulita/captures --state-dir /var/lib/mulita
```

Both paths must be absolute and separate; private state must not be nested inside shared capture storage. Selecting a new location does not copy existing data.

Inspect the installed configuration with:

```bash
cat /etc/mulita/config.json
```

For an alternative runtime configuration:

```bash
MULITA_CONFIG=/absolute/path/config.json bash run.sh
```

The service uses the installed path configuration rather than relying on root's `HOME`. Repository updates run as the installation user when the application runs as root. If the repository is relocated, rerun the installer to regenerate the service paths.

## Starting and Updating the Application

### Automatic startup

After installation and reboot, systemd starts `mulita.service` automatically.

```bash
sudo systemctl status mulita --no-pager -l
sudo systemctl restart mulita
sudo systemctl stop mulita
sudo systemctl start mulita
```

### Manual startup

`run.sh` only starts the application using its existing virtual environment. It does not install packages or change display, storage, or service configuration.

Stop the service before starting a manual instance:

```bash
sudo systemctl stop mulita
sudo bash run.sh
```

After closing the manual instance, restore the service with `sudo systemctl start mulita`.

Additional launch options:

```bash
bash run.sh --test
bash run.sh --no-keyboard
```

`--test` enables supported test/simulation behavior and disables hardware-dependent settings such as fullscreen operation and the physical climate sensor. It is not a complete emulator for every network function.

### Updates

For application-only changes, run these commands as the repository owner:

```bash
git switch v3.1
git pull origin v3.1
sudo systemctl restart mulita
```

If an update changes installation dependencies, service generation, or display configuration, rerun `bash install-lite.sh 5` or `bash install-lite.sh 7`, then reboot.

## Application Settings

### General

Provides application information and a language drop-down for English or Spanish.

### Display

Provides interface scale, brightness where supported, touchscreen diagnostics, and software orientation at **0°, 90°, 180°, or 270°**. Orientation is saved and applies to application content, touch controls, dialogs, and the integrated keyboard. It does not rotate the operating system's boot console.

The touchscreen test includes nine target zones, drawing trails, event counters, a test button, a normal/unfiltered input comparison, Clear, and Stop. Stop ends the test and returns to Display settings. The test retains up to 200 recent events.

Green traces represent Qt touch events; blue traces represent mouse or synthesized events. Some systems expose touchscreen activity as mouse events only. The test observes Qt input, not raw kernel events.

### Interface

Provides light/dark theme selection, tile ordering, and automatic tile resizing.

Home screens contain one to six tiles. Tiles can be assigned across numbered screens. When resizing is enabled, tiles expand to use available space; when disabled, they retain the size used in a six-tile layout.

### Wi-Fi

Provides network discovery, connection, disconnection, and IPv4 configuration through DHCP or a static address. Static configuration includes address, netmask, gateway, and DNS and is stored in the connected network's profile.

Saved profiles are used for reconnection before requesting a password. The password dialog appears if no matching profile is available or reconnection fails. Disconnect preserves the saved profile.

The Advanced submenu lists saved Wi-Fi profiles, including out-of-range networks. Each profile has a delete action with confirmation. Forgetting a profile removes its saved credentials and disconnects it if active.

### Ethernet and VLAN

Provides DHCP/static IPv4 selection through a switch, with address, netmask, gateway, and DNS fields for static configuration.

A separate VLAN switch enables a tag from **1 to 4094**. Settings are applied after confirmation. Disabling the tag and applying removes the managed VLAN profile and tagged VLAN interfaces associated with that Ethernet port, then configures the untagged interface.

### Maintenance

Provides application update, application restart, and device shutdown controls.

## Files and Exported Results

In this document, `<captures>` denotes `capture_dir` from `/etc/mulita/config.json`; it is not a literal directory name. On-screen storage names may remain in Spanish regardless of the selected interface language.

- **Packet capture:** PCAP files in capture storage; TAP captures use `tap`.
- **Connectivity and discovery:** dedicated `ping`, `trazas`, `escaneo`, and `descubrimiento` directories.
- **Wi-Fi and public IP:** exported information under `wifi` and `internet`.
- **Switch-port reports:** JSON files under `puerto-switch`.
- **TLS results:** CSV files under `tls`.
- **Nmap history:** dated directories under `nmap`, containing XML, output, progress, errors, CSV, and metadata files.
- **Test servers:** `servidores/tftp`, `servidores/web`, and `servidores/registros`; SFTP uploads use `respaldos`.

The file manager provides access to supported result directories. Press and hold text or a table cell to open the copy menu. Right-click and text selection also support copying. Editable fields offer Paste when clipboard content is available.

## Localization and Export Compatibility

Starting with version 3.1, domain models, validation errors, and service results
do not depend on a process-wide interface language. Each interface controller
uses an explicit translator associated with its own settings. Preferences are
saved before language-change notifications are published; a failed write leaves
the previous language active.

New CSV exports use stable technical field identifiers and status codes rather
than translated headings. Examples include `ssid`, `address`, `gateway`,
`severity`, and `open|filtered`. Existing export files are not rewritten.
Integrations that previously matched Spanish or English CSV headings must be
updated for the version 3.1 schema. File names and storage locations are unchanged.

On-screen labels remain translated. Wi-Fi facts and TLS labels are formatted in
the presentation layer, while exported domain values remain independent of the
selected language. Output originating from external tools retains its original
content and may use the language of the external tool.

Domain errors expose a stable `code` and structured `parameters`. Their string
representation is intended for diagnostics; user interfaces render them through
their own translator. New domain and service modules must not import UI or
presentation modules. Automated checks in `tests/test_localization.py` enforce
this dependency direction and verify instance isolation and persistence failures.

## Windows Development Environment

From a Windows checkout, run:

```bat
run_windows_test.bat
```

The launcher prepares a virtual environment under `%LOCALAPPDATA%\Mulita\venv-win`, installs requirements and PyQt5, runs the test suite, and opens the Qt Quick interface with `MULITA_TEST=1` and the integrated keyboard disabled.

Common options:

```bat
run_windows_test.bat -NoUi -SkipTests
run_windows_test.bat -SkipTests
run_windows_test.bat -RecreateVenv
```

`-NoUi -SkipTests` prepares the environment only. `-SkipTests` starts the interface without running tests. `-RecreateVenv` rebuilds the development environment.

If PowerShell policy prevents the launcher from running:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_windows_test.ps1
```

## Verification and Troubleshooting

### Installation and runtime checks

From an installed Raspberry Pi environment:

```bash
bash -n install-lite.sh
.venv/bin/python scripts/verify_qt_runtime.py
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
sudo systemd-analyze verify /etc/systemd/system/mulita.service
```

The runtime verifier checks Python imports and QML compilation. These checks do not replace validation of the physical display, touch controller, GPU backend, or connected network.

### Application not visible

Inspect the service before repeating installation:

```bash
sudo systemctl status mulita --no-pager -l
sudo journalctl -u mulita -b -n 100 --no-pager
sudo systemctl cat mulita
```

Confirm that the selected panel matches the installed hardware and that the device was rebooted after display configuration changes. Missing overlay errors require an operating-system/kernel installation containing the requested driver.

For a live log:

```bash
sudo journalctl -u mulita -f
```

The installer reserves tty1 for the application and retains tty3 for local recovery, accessible with **Ctrl+Alt+F3** when a keyboard is connected.

### Optional functions unavailable

- TLS assessment requires a working `testssl.sh` executable.
- DHT11 readings require compatible GPIO hardware and the optional driver.
- Wi-Fi and Ethernet configuration require NetworkManager and a corresponding network interface.
- External lookups and Internet speed tests require network access to their services.

## Project Structure

- **`main.py`:** application entry point.
- **`mulita/core`:** models, parsing, validation, and command construction.
- **`mulita/services`:** diagnostic operations, network configuration, and service lifecycle management.
- **`mulita/adapters`:** subprocess, storage, sensor, and hardware integrations.
- **`mulita/ui/qt`:** Qt controllers, QML pages, reusable controls, and input handling.
- **`scripts`:** installation configuration and runtime verification helpers.
- **`tests`:** automated verification.
- **`install-lite.sh`:** unified Raspberry Pi installer.
- **`run.sh`:** application launcher for an existing installation.

## License

The original code in this repository is licensed under the **GNU General Public License, version 3 only** (`GPL-3.0-only`), unless a file explicitly states otherwise. The complete license text is provided in [LICENSE](LICENSE).

Commercial use, modification, and redistribution are permitted under the terms of GPLv3. When distributing covered software, recipients must receive the applicable license notices and access to the corresponding source code as required by the license. This software is provided without warranty, to the extent permitted by law.

Third-party libraries, system packages, and external tools retain their respective licenses. The project license does not replace or modify the license terms of those components.
