{
  description = "NixOS Raspberry Pi 4 Smoke Test Image";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f {
        inherit system;
        pkgs = nixpkgs.legacyPackages.${system};
      });
    in
    {
      nixosConfigurations.pi4 = nixpkgs.lib.nixosSystem {
        # The host system where the image is built. 
        # We use x86_64-linux as the primary host, but it can be overridden.
        system = "x86_64-linux";
        modules = [
          {
            nixpkgs.crossSystem = {
              system = "aarch64-linux";
            };
          }
          "${nixpkgs}/nixos/modules/installer/sd-card/sd-image-aarch64.nix"
          ./hosts/pi4/configuration.nix
          ./hosts/pi4/hardware.nix
        ];
      };

      packages = forAllSystems ({ system, pkgs }: {
        # On x86_64, we can build the cross-compiled image.
        # On aarch64, we might want to build it natively.
        # For simplicity, we just provide the same config.
        pi4-sd-image = self.nixosConfigurations.pi4.config.system.build.sdImage;
      });

      defaultPackage = forAllSystems ({ system, pkgs }: self.packages.${system}.pi4-sd-image);
    };
}
