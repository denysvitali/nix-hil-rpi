#!/usr/bin/env python3
"""
NixOS Raspberry Pi Post-Boot Configuration Tool
A TUI-based setup wizard for configuring SSH keys, GitHub Actions runner,
hostname, timezone, and WiFi credentials.
"""

import asyncio
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.request import urlopen
from urllib.error import URLError

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    Header,
    Footer,
    Input,
    Label,
    Static,
    Select,
    RadioSet,
    RadioButton,
    Checkbox,
    TextArea,
    Markdown,
    ProgressBar,
)
from textual.reactive import reactive
from textual.binding import Binding

# Output file paths
SSH_DIR = Path("/home/pi/.ssh")
AUTH_KEYS_FILE = SSH_DIR / "authorized_keys"
RUNNER_DIR = Path("/var/lib/github-runner")
RUNNER_TOKEN_FILE = RUNNER_DIR / ".runner_token"
RUNNER_URL_FILE = RUNNER_DIR / ".runner_url"
NIXOS_CONFIG_DIR = Path("/etc/nixos")

# Defaults
DEFAULT_HOSTNAME = "pi4-smoke-test"
DEFAULT_TIMEZONE = "UTC"
DEFAULT_RUNNER_URL = "https://github.com/denysvitali/nix-hil-rpi"


class SetupState:
    """Holds the configuration state throughout the setup process."""

    def __init__(self):
        self.ssh_method: Optional[str] = None
        self.ssh_github_username: str = ""
        self.ssh_public_key: str = ""
        self.ssh_file_path: str = ""
        self.validated_ssh_key: str = ""

        self.runner_token: str = ""
        self.runner_url: str = DEFAULT_RUNNER_URL

        self.hostname: str = DEFAULT_HOSTNAME
        self.timezone: str = DEFAULT_TIMEZONE
        self.configure_wifi: bool = False
        self.wifi_ssid: str = ""
        self.wifi_password: str = ""

        self.errors: list[str] = []


# Global state
state = SetupState()


def validate_ssh_key(key: str) -> tuple[bool, str]:
    """Validate SSH public key format."""
    key = key.strip()
    if not key:
        return False, "SSH key is empty"

    # Common SSH key types
    valid_types = [
        "ssh-rsa",
        "ssh-ed25519",
        "ssh-dss",
        "ecdsa-sha2-nistp256",
        "ecdsa-sha2-nistp384",
        "ecdsa-sha2-nistp521",
        "sk-ssh-ed25519",
        "sk-ecdsa-sha2-nistp256",
    ]

    parts = key.split()
    if len(parts) < 2:
        return False, "Invalid SSH key format: must have at least type and key data"

    key_type = parts[0]
    if key_type not in valid_types:
        return False, f"Unsupported SSH key type: {key_type}"

    # Basic base64 validation (key data should be base64)
    key_data = parts[1]
    if not re.match(r'^[A-Za-z0-9+/]+={0,2}$', key_data):
        return False, "Invalid SSH key data (not valid base64)"

    return True, "Valid SSH key"


def fetch_github_keys(username: str) -> tuple[bool, str]:
    """Fetch SSH keys from GitHub."""
    if not username or not re.match(r'^[a-zA-Z0-9-]+$', username):
        return False, "Invalid GitHub username"

    try:
        url = f"https://github.com/{username}.keys"
        with urlopen(url, timeout=10) as response:
            keys = response.read().decode('utf-8').strip()
            if not keys:
                return False, f"No SSH keys found for GitHub user: {username}"
            return True, keys
    except URLError as e:
        return False, f"Failed to fetch keys from GitHub: {e}"
    except Exception as e:
        return False, f"Error fetching keys: {e}"


def read_key_from_file(path: str) -> tuple[bool, str]:
    """Read SSH key from file."""
    try:
        file_path = Path(path).expanduser()
        if not file_path.exists():
            return False, f"File not found: {path}"

        with open(file_path, 'r') as f:
            content = f.read().strip()
            if not content:
                return False, "File is empty"
            return True, content
    except Exception as e:
        return False, f"Error reading file: {e}"


def detect_wifi_interface() -> Optional[str]:
    """Detect if there's a WiFi interface."""
    try:
        result = subprocess.run(
            ["iw", "dev"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and "Interface" in result.stdout:
            # Extract interface name
            match = re.search(r'Interface\s+(\w+)', result.stdout)
            if match:
                return match.group(1)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def get_timezones() -> list[str]:
    """Get list of available timezones."""
    try:
        result = subprocess.run(
            ["timedatectl", "list-timezones"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip().split('\n')
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Fallback to common timezones
    return [
        "UTC",
        "Europe/London",
        "Europe/Paris",
        "Europe/Berlin",
        "Europe/Zurich",
        "Europe/Rome",
        "America/New_York",
        "America/Los_Angeles",
        "America/Chicago",
        "Asia/Tokyo",
        "Asia/Shanghai",
        "Australia/Sydney",
    ]


def backup_file(path: Path) -> None:
    """Create a backup of a file if it exists."""
    if path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = Path(f"{path}.backup.{timestamp}")
        shutil.copy2(path, backup_path)


class WelcomeScreen(Screen):
    """Welcome screen with introduction."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Static("""
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│     🍓 NixOS Raspberry Pi 4 Post-Boot Configuration Tool 🍓     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
            """, classes="banner"),
            Static("""
Welcome! This tool will help you configure your NixOS Raspberry Pi after the first boot.

[bold cyan]Required Configuration:[/bold cyan]
  • SSH Authorized Keys (enables SSH access)
  • GitHub Actions Runner Token
  • GitHub Actions Runner URL

[bold cyan]Optional Configuration:[/bold cyan]
  • Hostname (default: pi4-smoke-test)
  • Timezone (default: UTC)
  • WiFi Credentials (if WiFi interface detected)

[bold yellow]Note:[/bold yellow] SSH is currently configured without any authorized keys,
which means you cannot log in via SSH until you complete this setup.

Press [bold green]Start[/bold green] to begin the configuration process.
            """, classes="welcome-text"),
            Horizontal(
                Button("▶ Start Configuration", variant="success", id="start"),
                Button("✕ Quit", variant="error", id="quit"),
                classes="buttons",
            ),
            classes="centered",
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start":
            self.app.push_screen(SSHMethodScreen())
        elif event.button.id == "quit":
            self.app.exit()


class SSHMethodScreen(Screen):
    """Screen to select SSH key input method."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("b", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Static("Step 1/6: SSH Key Configuration", classes="step-title"),
            Static("Select how you want to provide your SSH public key:", classes="step-desc"),
            RadioSet(
                RadioButton("Fetch from GitHub username", id="github", value=True),
                RadioButton("Paste public key directly", id="paste"),
                RadioButton("Load from USB/SD card file", id="file"),
                id="ssh_method",
            ),
            Static("", id="error_msg", classes="error"),
            Horizontal(
                Button("← Back", id="back"),
                Button("Continue →", variant="primary", id="continue"),
                Button("✕ Cancel", variant="error", id="cancel"),
                classes="buttons",
            ),
            classes="centered",
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.app.exit()
        elif event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "continue":
            radio_set = self.query_one("#ssh_method", RadioSet)
            selected = radio_set.pressed_button
            if selected:
                state.ssh_method = selected.id
                if state.ssh_method == "github":
                    self.app.push_screen(SSHGithubScreen())
                elif state.ssh_method == "paste":
                    self.app.push_screen(SSHPasteScreen())
                elif state.ssh_method == "file":
                    self.app.push_screen(SSHFileScreen())


class SSHGithubScreen(Screen):
    """Screen to input GitHub username."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("b", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Static("Step 1/6: SSH Key from GitHub", classes="step-title"),
            Static("Enter your GitHub username to fetch your public SSH keys:", classes="step-desc"),
            Input(placeholder="GitHub username (e.g., denysvitali)", id="username"),
            Static("", id="status_msg"),
            Horizontal(
                Button("← Back", id="back"),
                Button("Fetch & Continue →", variant="primary", id="continue"),
                Button("✕ Cancel", variant="error", id="cancel"),
                classes="buttons",
            ),
            classes="centered",
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.app.exit()
        elif event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "continue":
            username = self.query_one("#username", Input).value.strip()
            if not username:
                self.query_one("#status_msg", Static).update(
                    "[red]✗ Please enter a GitHub username[/red]"
                )
                return

            self.query_one("#status_msg", Static).update(
                "[yellow]⟳ Fetching keys from GitHub...[/yellow]"
            )

            success, result = fetch_github_keys(username)
            if success:
                # Validate the keys
                keys = result.split('\n')
                valid_keys = []
                for key in keys:
                    key = key.strip()
                    if key:
                        is_valid, _ = validate_ssh_key(key)
                        if is_valid:
                            valid_keys.append(key)

                if valid_keys:
                    state.ssh_github_username = username
                    state.validated_ssh_key = '\n'.join(valid_keys)
                    self.app.push_screen(GitHubRunnerScreen())
                else:
                    self.query_one("#status_msg", Static).update(
                        "[red]✗ No valid SSH keys found in GitHub response[/red]"
                    )
            else:
                self.query_one("#status_msg", Static).update(f"[red]✗ {result}[/red]")


class SSHPasteScreen(Screen):
    """Screen to paste SSH public key directly."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("b", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Static("Step 1/6: Paste SSH Public Key", classes="step-title"),
            Static("Paste your SSH public key (e.g., ssh-ed25519 AAAAC3NzaC...):", classes="step-desc"),
            TextArea(id="ssh_key", language=None, show_line_numbers=False),
            Static("", id="status_msg"),
            Horizontal(
                Button("← Back", id="back"),
                Button("Validate & Continue →", variant="primary", id="continue"),
                Button("✕ Cancel", variant="error", id="cancel"),
                classes="buttons",
            ),
            classes="centered",
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.app.exit()
        elif event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "continue":
            key = self.query_one("#ssh_key", TextArea).text.strip()
            is_valid, message = validate_ssh_key(key)

            if is_valid:
                state.ssh_public_key = key
                state.validated_ssh_key = key
                self.app.push_screen(GitHubRunnerScreen())
            else:
                self.query_one("#status_msg", Static).update(f"[red]✗ {message}[/red]")


class SSHFileScreen(Screen):
    """Screen to load SSH key from file."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("b", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Static("Step 1/6: Load SSH Key from File", classes="step-title"),
            Static("Enter the path to your SSH public key file:", classes="step-desc"),
            Static("[dim]Common locations: /mnt/usb/id_rsa.pub, /boot/ssh_key.pub[/dim]", classes="hint"),
            Input(placeholder="/path/to/your/key.pub", id="file_path"),
            Static("", id="status_msg"),
            Horizontal(
                Button("← Back", id="back"),
                Button("Load & Continue →", variant="primary", id="continue"),
                Button("✕ Cancel", variant="error", id="cancel"),
                classes="buttons",
            ),
            classes="centered",
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.app.exit()
        elif event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "continue":
            file_path = self.query_one("#file_path", Input).value.strip()
            if not file_path:
                self.query_one("#status_msg", Static).update(
                    "[red]✗ Please enter a file path[/red]"
                )
                return

            success, result = read_key_from_file(file_path)
            if success:
                is_valid, message = validate_ssh_key(result)
                if is_valid:
                    state.ssh_file_path = file_path
                    state.validated_ssh_key = result
                    self.app.push_screen(GitHubRunnerScreen())
                else:
                    self.query_one("#status_msg", Static).update(f"[red]✗ {message}[/red]")
            else:
                self.query_one("#status_msg", Static).update(f"[red]✗ {result}[/red]")


class GitHubRunnerScreen(Screen):
    """Screen to configure GitHub Actions runner."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("b", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Static("Step 2/6: GitHub Actions Runner", classes="step-title"),
            Static("Configure the GitHub Actions self-hosted runner:", classes="step-desc"),
            Label("Runner Token (Personal Access Token):"),
            Input(
                placeholder="ghp_xxxxxxxxxxxxxxxxxxxx",
                id="runner_token",
                password=True,
            ),
            Label("Runner URL:"),
            Input(
                value=DEFAULT_RUNNER_URL,
                placeholder="https://github.com/OWNER/REPO",
                id="runner_url",
            ),
            Static(
                "[dim]The token should have 'repo' scope for private repos or 'public_repo' for public repos[/dim]",
                classes="hint"
            ),
            Static("", id="status_msg"),
            Horizontal(
                Button("← Back", id="back"),
                Button("Continue →", variant="primary", id="continue"),
                Button("✕ Cancel", variant="error", id="cancel"),
                classes="buttons",
            ),
            classes="centered",
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.app.exit()
        elif event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "continue":
            token = self.query_one("#runner_token", Input).value.strip()
            url = self.query_one("#runner_url", Input).value.strip()

            if not token:
                self.query_one("#status_msg", Static).update(
                    "[red]✗ Runner token is required[/red]"
                )
                return

            if not url:
                self.query_one("#status_msg", Static).update(
                    "[red]✗ Runner URL is required[/red]"
                )
                return

            # Basic token format validation
            if not re.match(r'^(ghp_|ghs_)[a-zA-Z0-9]{36,}$', token):
                self.query_one("#status_msg", Static).update(
                    "[yellow]⚠ Token format looks unusual. Make sure it's a valid PAT[/yellow]"
                )
                # Don't block, just warn

            state.runner_token = token
            state.runner_url = url
            self.app.push_screen(HostNameScreen())


class HostNameScreen(Screen):
    """Screen to configure hostname."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("b", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Static("Step 3/6: Hostname (Optional)", classes="step-title"),
            Static("Set the hostname for this Raspberry Pi:", classes="step-desc"),
            Input(
                value=DEFAULT_HOSTNAME,
                placeholder="pi4-smoke-test",
                id="hostname",
            ),
            Static(
                "[dim]Hostname must contain only letters, numbers, and hyphens[/dim]",
                classes="hint"
            ),
            Static("", id="status_msg"),
            Horizontal(
                Button("← Back", id="back"),
                Button("Continue →", variant="primary", id="continue"),
                Button("Skip →", id="skip"),
                Button("✕ Cancel", variant="error", id="cancel"),
                classes="buttons",
            ),
            classes="centered",
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.app.exit()
        elif event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "skip":
            self.app.push_screen(TimezoneScreen())
        elif event.button.id == "continue":
            hostname = self.query_one("#hostname", Input).value.strip()

            if not hostname:
                self.query_one("#status_msg", Static).update(
                    "[red]✗ Hostname cannot be empty[/red]"
                )
                return

            # Validate hostname format
            if not re.match(r'^[a-zA-Z0-9-]+$', hostname):
                self.query_one("#status_msg", Static).update(
                    "[red]✗ Hostname contains invalid characters[/red]"
                )
                return

            if len(hostname) > 63:
                self.query_one("#status_msg", Static).update(
                    "[red]✗ Hostname too long (max 63 characters)[/red]"
                )
                return

            state.hostname = hostname
            self.app.push_screen(TimezoneScreen())


class TimezoneScreen(Screen):
    """Screen to select timezone."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("b", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        timezones = get_timezones()
        default_index = timezones.index(DEFAULT_TIMEZONE) if DEFAULT_TIMEZONE in timezones else 0

        yield Header(show_clock=True)
        yield Container(
            Static("Step 4/6: Timezone (Optional)", classes="step-title"),
            Static("Select your timezone:", classes="step-desc"),
            Select(
                [(tz, tz) for tz in timezones],
                value=timezones[default_index] if timezones else None,
                id="timezone",
            ),
            Static("", id="status_msg"),
            Horizontal(
                Button("← Back", id="back"),
                Button("Continue →", variant="primary", id="continue"),
                Button("Skip →", id="skip"),
                Button("✕ Cancel", variant="error", id="cancel"),
                classes="buttons",
            ),
            classes="centered",
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.app.exit()
        elif event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id in ("continue", "skip"):
            if event.button.id == "continue":
                timezone_select = self.query_one("#timezone", Select)
                if timezone_select.value:
                    state.timezone = str(timezone_select.value)

            # Check for WiFi interface
            wifi_iface = detect_wifi_interface()
            if wifi_iface:
                self.app.push_screen(WiFiScreen())
            else:
                # Skip WiFi if no interface detected
                self.app.push_screen(SummaryScreen())


class WiFiScreen(Screen):
    """Screen to configure WiFi credentials."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("b", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Static("Step 5/6: WiFi Configuration (Optional)", classes="step-title"),
            Static(f"WiFi interface detected. Configure WiFi credentials?", classes="step-desc"),
            Checkbox("Configure WiFi", id="configure_wifi"),
            Label("SSID (Network Name):"),
            Input(placeholder="MyWiFiNetwork", id="wifi_ssid"),
            Label("Password:"),
            Input(placeholder="WiFi password", id="wifi_password", password=True),
            Static("", id="status_msg"),
            Horizontal(
                Button("← Back", id="back"),
                Button("Continue →", variant="primary", id="continue"),
                Button("Skip WiFi →", id="skip"),
                Button("✕ Cancel", variant="error", id="cancel"),
                classes="buttons",
            ),
            classes="centered",
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.app.exit()
        elif event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "skip":
            state.configure_wifi = False
            self.app.push_screen(SummaryScreen())
        elif event.button.id == "continue":
            configure = self.query_one("#configure_wifi", Checkbox).value

            if configure:
                ssid = self.query_one("#wifi_ssid", Input).value.strip()
                password = self.query_one("#wifi_password", Input).value.strip()

                if not ssid:
                    self.query_one("#status_msg", Static).update(
                        "[red]✗ SSID cannot be empty[/red]"
                    )
                    return

                if len(password) < 8:
                    self.query_one("#status_msg", Static).update(
                        "[red]✗ WiFi password must be at least 8 characters[/red]"
                    )
                    return

                state.configure_wifi = True
                state.wifi_ssid = ssid
                state.wifi_password = password
            else:
                state.configure_wifi = False

            self.app.push_screen(SummaryScreen())


class SummaryScreen(Screen):
    """Screen showing summary of all configuration."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("b", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        # Build summary text
        ssh_summary = f"""
[bold cyan]SSH Configuration:[/bold cyan]
  Method: {state.ssh_method or 'Unknown'}
  Key count: {len(state.validated_ssh_key.split(chr(10))) if state.validated_ssh_key else 0} key(s)
"""

        runner_summary = f"""
[bold cyan]GitHub Runner:[/bold cyan]
  URL: {state.runner_url}
  Token: {'*' * min(len(state.runner_token), 8) if state.runner_token else 'Not set'}
"""

        system_summary = f"""
[bold cyan]System Configuration:[/bold cyan]
  Hostname: {state.hostname}
  Timezone: {state.timezone}
"""

        wifi_summary = ""
        if state.configure_wifi:
            wifi_summary = f"""
[bold cyan]WiFi Configuration:[/bold cyan]
  SSID: {state.wifi_ssid}
  Password: {'*' * len(state.wifi_password)}
"""
        else:
            wifi_summary = """
[bold cyan]WiFi Configuration:[/bold cyan]
  Skipped (or no WiFi interface detected)
"""

        summary_text = f"""
[bold]Step 6/6: Configuration Summary[/bold]

Please review your configuration before applying:

{ssh_summary}
{runner_summary}
{system_summary}
{wifi_summary}

[bold yellow]⚠ Warning:[/bold yellow] This will:
  • Create backups of existing configuration files
  • Write new configuration files
  • Run 'nixos-rebuild switch' to apply changes

The system may restart services during this process.
"""

        yield Header(show_clock=True)
        yield Container(
            Markdown(summary_text, id="summary"),
            Static("", id="status_msg"),
            Horizontal(
                Button("← Back", id="back"),
                Button("✓ Apply Configuration", variant="success", id="apply"),
                Button("✕ Cancel", variant="error", id="cancel"),
                classes="buttons",
            ),
            classes="centered",
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.app.exit()
        elif event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "apply":
            self.app.push_screen(ApplyScreen())


class ApplyScreen(Screen):
    """Screen for applying configuration."""

    BINDINGS = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Static("Applying Configuration", classes="step-title"),
            Static("Please wait while the configuration is being applied...", classes="step-desc"),
            ProgressBar(total=6, id="progress"),
            Static("", id="status_log"),
            Static("", id="error_log", classes="error"),
            Button("Exit", id="exit", disabled=True, classes="hidden"),
            classes="centered",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Start applying configuration when screen mounts."""
        self.apply_task = asyncio.create_task(self.apply_configuration())

    async def apply_configuration(self) -> None:
        """Apply all configuration changes."""
        progress = self.query_one("#progress", ProgressBar)
        status = self.query_one("#status_log", Static)
        error_log = self.query_one("#error_log", Static)

        step = 0

        # Step 1: Create SSH directory and write authorized_keys
        step += 1
        progress.update(progress=step)
        status.update(f"[{step}/6] Setting up SSH authorized keys...")
        await asyncio.sleep(0.5)

        try:
            # Create .ssh directory
            SSH_DIR.mkdir(parents=True, exist_ok=True)
            os.chmod(SSH_DIR, 0o700)

            # Backup existing authorized_keys
            backup_file(AUTH_KEYS_FILE)

            # Write new authorized_keys
            with open(AUTH_KEYS_FILE, 'w') as f:
                f.write(state.validated_ssh_key + '\n')
            os.chmod(AUTH_KEYS_FILE, 0o600)

            # Set ownership to pi user
            shutil.chown(SSH_DIR, "pi", "pi")
            shutil.chown(AUTH_KEYS_FILE, "pi", "pi")

        except Exception as e:
            error_log.update(f"[red]Failed to configure SSH: {e}[/red]")
            self.show_exit_button()
            return

        # Step 2: Write GitHub runner token
        step += 1
        progress.update(progress=step)
        status.update(f"[{step}/6] Writing GitHub runner token...")
        await asyncio.sleep(0.5)

        try:
            # Ensure runner directory exists with correct permissions
            RUNNER_DIR.mkdir(parents=True, exist_ok=True)
            shutil.chown(RUNNER_DIR, "github-runner", "github-runner")

            # Backup existing files
            backup_file(RUNNER_TOKEN_FILE)
            backup_file(RUNNER_URL_FILE)

            # Write token
            with open(RUNNER_TOKEN_FILE, 'w') as f:
                f.write(state.runner_token + '\n')
            os.chmod(RUNNER_TOKEN_FILE, 0o600)
            shutil.chown(RUNNER_TOKEN_FILE, "github-runner", "github-runner")

            # Write URL
            with open(RUNNER_URL_FILE, 'w') as f:
                f.write(state.runner_url + '\n')
            os.chmod(RUNNER_URL_FILE, 0o600)
            shutil.chown(RUNNER_URL_FILE, "github-runner", "github-runner")

        except Exception as e:
            error_log.update(f"[red]Failed to configure GitHub runner: {e}[/red]")
            self.show_exit_button()
            return

        # Step 3: Generate hostname.nix
        step += 1
        progress.update(progress=step)
        status.update(f"[{step}/6] Generating hostname configuration...")
        await asyncio.sleep(0.5)

        try:
            NIXOS_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

            hostname_nix = f'''# Generated by NixOS Raspberry Pi setup tool
{{ config, pkgs, lib, ... }}:
{{
  networking.hostName = "{state.hostname}";
}}
'''
            backup_file(NIXOS_CONFIG_DIR / "hostname.nix")
            with open(NIXOS_CONFIG_DIR / "hostname.nix", 'w') as f:
                f.write(hostname_nix)

        except Exception as e:
            error_log.update(f"[red]Failed to configure hostname: {e}[/red]")
            self.show_exit_button()
            return

        # Step 4: Generate timezone.nix
        step += 1
        progress.update(progress=step)
        status.update(f"[{step}/6] Generating timezone configuration...")
        await asyncio.sleep(0.5)

        try:
            timezone_nix = f'''# Generated by NixOS Raspberry Pi setup tool
{{ config, pkgs, lib, ... }}:
{{
  time.timeZone = "{state.timezone}";
}}
'''
            backup_file(NIXOS_CONFIG_DIR / "timezone.nix")
            with open(NIXOS_CONFIG_DIR / "timezone.nix", 'w') as f:
                f.write(timezone_nix)

        except Exception as e:
            error_log.update(f"[red]Failed to configure timezone: {e}[/red]")
            self.show_exit_button()
            return

        # Step 5: Generate wifi.nix (if configured)
        step += 1
        progress.update(progress=step)
        status.update(f"[{step}/6] Generating WiFi configuration...")
        await asyncio.sleep(0.5)

        try:
            if state.configure_wifi:
                wifi_nix = f'''# Generated by NixOS Raspberry Pi setup tool
{{ config, pkgs, lib, ... }}:
{{
  networking.wireless = {{
    enable = true;
    networks = {{
      "{state.wifi_ssid}" = {{
        psk = "{state.wifi_password}";
      }};
    }};
  }};
}}
'''
                backup_file(NIXOS_CONFIG_DIR / "wifi.nix")
                with open(NIXOS_CONFIG_DIR / "wifi.nix", 'w') as f:
                    f.write(wifi_nix)
            else:
                # Remove wifi.nix if it exists and we're not configuring WiFi
                wifi_nix_path = NIXOS_CONFIG_DIR / "wifi.nix"
                if wifi_nix_path.exists():
                    backup_file(wifi_nix_path)
                    wifi_nix_path.unlink()

        except Exception as e:
            error_log.update(f"[red]Failed to configure WiFi: {e}[/red]")
            self.show_exit_button()
            return

        # Step 6: Run nixos-rebuild switch
        step += 1
        progress.update(progress=step)
        status.update(f"[{step}/6] Running nixos-rebuild switch...")
        await asyncio.sleep(0.5)

        try:
            # Run nixos-rebuild switch
            result = await asyncio.create_subprocess_exec(
                "nixos-rebuild", "switch",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()

            if result.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                error_log.update(
                    f"[red]nixos-rebuild failed:[/red]\\n{error_msg[:500]}"
                )
                self.show_exit_button()
                return

        except Exception as e:
            error_log.update(f"[red]Failed to run nixos-rebuild: {e}[/red]")
            self.show_exit_button()
            return

        # Success!
        progress.update(progress=6)
        status.update(
            """
[bold green]✓ Configuration applied successfully![/bold green]

[bold]Summary of changes:[/bold]
  • SSH authorized keys configured
  • GitHub Actions runner configured
  • Hostname set to: {hostname}
  • Timezone set to: {timezone}
  {wifi_status}

You can now:
  • SSH into the system using your configured key
  • The GitHub Actions runner should start automatically

Backups of original files were created with .backup.<timestamp> suffix.
""".format(
                hostname=state.hostname,
                timezone=state.timezone,
                wifi_status="  • WiFi configured" if state.configure_wifi else "  • WiFi not configured"
            )
        )
        self.show_exit_button()

    def show_exit_button(self) -> None:
        """Show the exit button."""
        button = self.query_one("#exit", Button)
        button.disabled = False
        button.remove_class("hidden")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "exit":
            self.app.exit()


class SetupApp(App):
    """Main TUI application for NixOS Raspberry Pi setup."""

    CSS = """
    Screen {
        align: center middle;
    }

    .banner {
        text-align: center;
        color: $primary;
    }

    .welcome-text {
        width: 80;
        height: auto;
        content-align: center middle;
        text-align: left;
        padding: 1 2;
    }

    .centered {
        width: 80;
        height: auto;
        border: solid $primary;
        padding: 1 2;
    }

    .step-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        height: auto;
    }

    .step-desc {
        text-align: center;
        height: auto;
        margin: 1 0;
    }

    .buttons {
        height: auto;
        margin-top: 2;
        align: center middle;
    }

    Button {
        margin: 0 1;
    }

    Input, TextArea, Select {
        margin: 1 0;
    }

    TextArea {
        height: 5;
    }

    .error {
        color: $error;
        text-align: center;
    }

    .hint {
        color: $text-disabled;
        text-align: center;
        height: auto;
    }

    RadioSet {
        margin: 1 0;
    }

    Checkbox {
        margin: 1 0;
    }

    ProgressBar {
        margin: 1 0;
    }

    .hidden {
        display: none;
    }

    #summary {
        height: auto;
        max-height: 25;
    }
    """

    SCREENS = {
        "welcome": WelcomeScreen,
    }

    def on_mount(self) -> None:
        self.push_screen(WelcomeScreen())


def main():
    """Entry point for the setup tool."""
    # Check if running as root (required for nixos-rebuild)
    if os.geteuid() != 0:
        print("Error: This tool must be run as root (sudo)")
        print("Usage: sudo setup-tool")
        return 1

    app = SetupApp()
    app.run()
    return 0


if __name__ == "__main__":
    exit(main())
