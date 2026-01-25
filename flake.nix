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
        system = "aarch64-linux";
        modules = [
          ./hosts/pi4/configuration.nix
          ./hosts/pi4/hardware.nix
        ];
      };

      packages = forAllSystems ({ system, pkgs }: {
        pi4-sd-image = self.nixosConfigurations.pi4.config.system.build.sdImage;
      });

      defaultPackage = forAllSystems ({ system, pkgs }: self.packages.${system}.pi4-sd-image);
    };
}
