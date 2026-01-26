# NixOS Raspberry Pi 4 Smoke Test Image

Reproducible, updatable NixOS SD image for Raspberry Pi 4 with GitHub Actions self-hosted runner.

## Features

- **NixOS unstable** (rolling release)
- **Immutable rootfs** via NixOS generation system
- **Atomic remote upgrades** via SSH with native rollback
- **CI Tools**: probe-rs, cargo, espflash
- **GitHub Actions** self-hosted runner (`pi4-smoke-test`)
- **Aarch64 emulation** support for x86_64 build machines

## Architecture

No A/B partitioning needed - NixOS provides "A/B-like" behavior through its **generation system**:
- Each `nixos-rebuild` creates a new generation
- Rollbacks are native - select an older generation at boot
- See: https://nixos.org/manual/nixos/stable/#sec-rollback

## Directory Structure

```
nix-hil-rpi/
├── flake.nix                 # Flake inputs and outputs
├── hosts/
│   └── pi4/
│       ├── configuration.nix  # Main system config
│       └── hardware.nix       # Pi 4 specific hardware
└── README.md                 # This file
```

## Prerequisites

- **Build machine**: x86_64 Linux with aarch64 emulation, or native ARM machine
- **Target**: Raspberry Pi 4 with >= 16GB SD card
- **GitHub token**: Personal Access Token with `repo` scope

## Setup

### 1. Add SSH Keys

Edit `hosts/pi4/configuration.nix` and add your SSH public key(s):

```nix
users.users.pi.openssh.authorizedKeys.keys = [
  "ssh-ed25519 AAAAC3... your@email"
  # Or fetch from GitHub:
  # "https://github.com/denysvitali.keys"
];
```

### 2. GitHub Runner Setup (After First Boot)

The GitHub Actions runner is **disabled by default** in the SD image. To enable it after first boot:

#### Step 1: Get your GitHub token

1. Go to your repo/org settings on GitHub
2. Settings → Actions → Runners → New runner
3. Copy the token (or better: create a fine-grained Personal Access Token with "Read and Write access to self-hosted runners")

#### Step 2: SSH to the Pi

```bash
ssh pi@pi4-smoke-test.local
# or: ssh pi@<PI_IP>
```

#### Step 3: Configure and enable the runner

```bash
# Edit the NixOS configuration
sudo nano /etc/nixos/configuration.nix
```

Find the `github-runners` section and modify it:

```nix
services.github-runners.pi4-smoke-test = {
  enable = true;  # ← Change from false to true
  name = "pi4-smoke-test";
  # Set your GitHub repository or organization URL
  url = "https://github.com/your-org/your-repo";  # ← Add this
  # Keep tokenFile as is
  tokenFile = "/var/lib/github-runner/.runner_token";
  # ... keep other settings (labels, etc)
};
```

#### Step 4: Create the token file

```bash
# Create directory
sudo mkdir -p /var/lib/github-runner

# Save your token (no newline!)
echo -n 'YOUR_PAT_OR_RUNNER_TOKEN' | sudo tee /var/lib/github-runner/.runner_token

# Set permissions
sudo chmod 0600 /var/lib/github-runner/.runner_token
```

#### Step 5: Rebuild

```bash
sudo nixos-rebuild switch
```

The runner will start automatically after rebuild. Check status:

```bash
sudo systemctl status github-runner-pi4-smoke-test.service
```

## Building

### On x86_64 Linux (with emulation)

```bash
# Build the SD image
nix build .#nixosConfigurations.pi4.config.system.build.sdImage

# Result is in result/sd-image/nixos.img
```

### On Native ARM

```bash
nix build .#sdImage
```

## Flashing

```bash
# Identify your SD card device (BE CAREFUL!)
lsblk

# Flash to SD card (replace /dev/sdX with your device)
sudo dd if=result/sd-image/nixos.img of=/dev/sdX bs=1M status=progress conv=fsync

# Or use bmaptool (faster)
sudo bmaptool copy result/sd-image/nixos.img /dev/sdX
```

## Initial Boot Setup

1. Insert SD card and power on the Pi
2. Wait for boot (LED pattern: rapid blinking → solid)
3. Find the Pi's IP address:
   ```bash
   # Using mDNS
   avahi-resolve -n pi4-smoke-test.local

   # Or check your router's DHCP lease table
   ```
4. SSH in:
   ```bash
   ssh pi@<IP>
   ```

## Remote Upgrades

From your workstation (requires SSH access):

```bash
nixos-rebuild switch --flake .#pi4 \
  --target-host pi@<PI_IP> \
  --use-remote-sudo
```

This will:
1. Build on your workstation (with aarch64 emulation)
2. Transfer closure to the Pi
3. Atomically activate new generation
4. Keep old generation for rollback

## Rollback

If something breaks, rollback via SSH:

```bash
# SSH and run
sudo nixos-rebuild switch --rollback

# Or boot to previous generation via serial console:
# At boot menu, select "NixOS - Boot options" → previous generation
```

## Persistence

These paths survive `nixos-rebuild`:

- `/var/lib/github-runner/` - Runner data + token
- `/etc/nixos/` - Symlink to your git repo (optional)
- `/home/pi/` - User files
- `/root/` - Root files

## Installed Packages

| Package | Description |
|---------|-------------|
| `probe-rs` | JTAG/SWD debugger |
| `espflash` | Espressif chip flasher |
| `cargo` | Rust package manager |
| `rustc` | Rust compiler |
| `git` | Version control |
| `nano` | Simple editor |

## Troubleshooting

### Runner not starting

```bash
# Check runner status
sudo systemctl status github-runner-pi4-smoke-test.service

# View logs
sudo journalctl -u github-runner-pi4-smoke-test.service -f
```

### Build fails with "unsupported platform"

Ensure you're not cross-compiling without emulation:

```bash
# On x86_64, ensure binfmt is registered
sudo systemctl start binfmt-support
```

### Pi won't boot

1. Verify SD card is formatted as MBR (not GPT)
2. Check LED status:
   - No light: Power issue
   - 3 flashes: SD card not found
   - 4 flashes: Kernel not found

## References

- [NixOS on Raspberry Pi](https://nixos.org/manual/nixos/stable/#sec-raspberry-pi)
- [GitHub Self-Hosted Runners](https://docs.github.com/en/actions/hosting-your-own-runners)
- [probe-rs](https://probe.rs/)
- [espflash](https://github.com/esp-rs/espflash)
