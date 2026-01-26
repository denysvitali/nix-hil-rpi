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
  # The runner is disabled by default in the SD image.
  # To enable after first boot:
  # 1. Set the URL to your GitHub repo/org (e.g., "https://github.com/owner/repo")
  # 2. Set tokenFile to a file containing your runner token
  # 3. Set enable = true
  services.github-runners.pi4-smoke-test = {
    enable = false;
    name = "pi4-smoke-test";
    extraLabels = [
      "self-hosted"
      "pi4-smoke-test"
      "aarch64"
      "nixos"
    ];

    # TODO: Configure these after first boot
    # url = "https://github.com/your-org/your-repo";
    # tokenFile = "/var/lib/github-runner/.runner_token";
  };

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
