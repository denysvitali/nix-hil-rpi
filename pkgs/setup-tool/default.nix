{
  lib,
  python3Packages,
  makeWrapper,
  iw,
  nixos-rebuild,
  nix,
  git,
  coreutils,
  systemd,
}:

python3Packages.buildPythonApplication rec {
  pname = "nixos-rpi-setup-tool";
  version = "1.0.0";

  src = ./.;

  format = "other";

  nativeBuildInputs = [
    makeWrapper
  ];

  propagatedBuildInputs = with python3Packages; [
    textual
    textual-autocomplete
  ];

  dontUnpack = true;
  dontBuild = true;
  dontCheck = true;

  installPhase = ''
    runHook preInstall

    # Create directory structure
    mkdir -p $out/bin
    mkdir -p $out/share/${pname}

    # Copy the main script
    cp ${src}/setup-tool.py $out/share/${pname}/

    # Create wrapper script
    makeWrapper ${python3Packages.python}/bin/python $out/bin/setup-tool \
      --add-flags "$out/share/${pname}/setup-tool.py" \
      --prefix PATH : "${lib.makeBinPath [
        iw
        nixos-rebuild
        nix
        git
        coreutils
        systemd
      ]}"

    runHook postInstall
  '';

  meta = with lib; {
    description = "TUI-based post-boot configuration tool for NixOS Raspberry Pi";
    longDescription = ''
      A terminal user interface tool that guides users through post-boot
      configuration of NixOS on Raspberry Pi 4. Configures SSH keys,
      GitHub Actions runner, hostname, timezone, and WiFi credentials.
    '';
    license = licenses.mit;
    platforms = platforms.linux;
    mainProgram = "setup-tool";
  };
}
