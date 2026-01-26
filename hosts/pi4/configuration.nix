{ config, pkgs, lib, ... }:

{
  # ============== File Systems ==============
  # fileSystems."/" = {
  #   device = "/dev/disk/by-label/NIXOS_SD";
  #   fsType = "ext4";
  # };

  # ============== SSH Configuration ==============
  services.openssh = {
    enable = true;
    settings = {
      PermitRootLogin = "prohibit-password";
      PasswordAuthentication = false;
    };
  };

  # SSH authorized keys for the pi user (fetches from GitHub)
  users.users.pi = {
    isNormalUser = true;
    description = "Pi User";
    extraGroups = [ "wheel" "networkmanager" ];
    openssh.authorizedKeys.keys = [
      # Fetched from https://github.com/denysvitali.keys
      # Add additional keys here as needed
    ];
  };

  # ============== Package Installation ==============
  environment.systemPackages = with pkgs; [
    # CI/Debugging tools
    probe-rs-tools
    espflash

    # Rust toolchain (cargo, rustc, etc.)
    cargo
    rustc
    rustfmt
    clippy

    # Build tools
    git
    nano
    htop
    curl
    wget
  ];

  # ============== Nix Daemon for Parallel Builds ==============
  nix.settings.max-jobs = lib.mkDefault 4;
  nix.settings.auto-optimise-store = true;

  # ============== GitHub Actions Self-Hosted Runner ==============
  services.github-runners.pi4-smoke-test = {
    enable = true;
    name = "pi4-smoke-test";
    extraLabels = [
      "self-hosted"
      "pi4-smoke-test"
      "aarch64"
      "nixos"
    ];

    # Runner URL and token are provided via filesystem after first boot
    # User should create these files via SSH after first boot
    urlFile = "/var/lib/github-runner/.runner_url";
    tokenFile = "/var/lib/github-runner/.runner_token";
  };

  # Ensure persistent directory exists for GitHub runner
  systemd.tmpfiles.rules = [
    "d /var/lib/github-runner 0755 github-runner github-runner -"
    "f /var/lib/github-runner/.runner_url 0600 github-runner github-runner -"
    "f /var/lib/github-runner/.runner_token 0600 github-runner github-runner -"
  ];

  # ============== Networking ==============
  networking = {
    hostName = "pi4-smoke-test";
    networkmanager.enable = true;
    firewall.allowedTCPPorts = [ 22 ];  # SSH
  };

  # ============== System ==============
  time.timeZone = "UTC";
  i18n.defaultLocale = "en_US.UTF-8";

  # Enable automatic garbage collection
  nix.gc.automatic = true;

  # System state version
  system.stateVersion = "24.11";

  # Generate a machine-id for DHCP/DNS
  systemd.services.systemd-machine-id-commit.wantedBy = [ "multi-user.target" ];
}
