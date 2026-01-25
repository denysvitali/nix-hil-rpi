{ config, pkgs, lib, ... }:

{
  # Raspberry Pi 4 specific hardware configuration

  # Enable the 64-bit kernel with shared memory and GPU memory
  boot.kernelParams = [
    "cma=256M"
    "gpu_mem=128"
  ];

  # Required for Raspberry Pi 4
  hardware = {
    enableRedistributableFirmware = true;
  };

  # Bootloader configuration for Raspberry Pi 4
  boot.loader = {
    grub.enable = false;
    generic-extlinux-compatible = {
      enable = true;
    };
  };
}
