# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NixOS Raspberry Pi 4 Smoke Test Image - a reproducible, updatable NixOS SD image for Raspberry Pi 4 with GitHub Actions self-hosted runner support.

## Build Commands

```bash
# Build SD image for flashing
nix build .#packages.aarch64-linux.pi4-sd-image

# Build system toplevel (for remote deployment)
nix build .#nixosConfigurations.pi4.config.system.build.toplevel

# Validate flake configuration
nix flake check

# Show available flake outputs
nix flake show
```

## Remote Deployment

```bash
# Atomic remote upgrade via SSH
nixos-rebuild switch --flake .#pi4 \
  --target-host pi@<PI_IP> \
  --use-remote-sudo

# Rollback via SSH
nixos-rebuild switch --rollback
```

## Architecture

- **Flake-based**: Uses `flake.nix` with nixpkgs/nixos-unstable
- **Target**: `aarch64-linux` (Raspberry Pi 4)
- **No A/B partitioning**: Relies on NixOS generation system for rollbacks
- **Module structure**: `hosts/pi4/configuration.nix` (main config) + `hosts/pi4/hardware.nix` (Pi-specific)

## Key Configuration Points

- **SSH keys**: Add in `users.users.pi.openssh.authorizedKeys.keys`
- **GitHub runner token**: Set via `services.github-runners.pi4-smoke-test.tokenFile`
  - Token file: `/var/lib/github-runner/.runner_token` (create manually after first boot)
- **CI tools**: `probe-rs-tools`, `espflash`, `cargo`, `rustc`

## Persistent Paths

- `/var/lib/github-runner/` - Runner data + token
- `/home/pi/` - User files
- `/root/` - Root files
