# Installing runpodctl

```bash
# Any platform (official installer)
curl -sSL https://cli.runpod.net | bash

# macOS (Homebrew)
brew install runpod/runpodctl/runpodctl

# macOS (manual — universal binary)
mkdir -p ~/.local/bin && curl -sL https://github.com/runpod/runpodctl/releases/latest/download/runpodctl-darwin-all.tar.gz | tar xz -C ~/.local/bin

# Linux
mkdir -p ~/.local/bin && curl -sL https://github.com/runpod/runpodctl/releases/latest/download/runpodctl-linux-amd64.tar.gz | tar xz -C ~/.local/bin

# Windows (PowerShell)
Invoke-WebRequest -Uri https://github.com/runpod/runpodctl/releases/latest/download/runpodctl-windows-amd64.zip -OutFile runpodctl.zip; Expand-Archive runpodctl.zip -DestinationPath $env:LOCALAPPDATA\runpodctl; [Environment]::SetEnvironmentVariable('Path', $env:Path + ";$env:LOCALAPPDATA\runpodctl", 'User')
```

Ensure `~/.local/bin` is on your `PATH` (add `export PATH="$HOME/.local/bin:$PATH"` to `~/.bashrc` or `~/.zshrc`).

> Some features need a recent CLI (e.g. `--model-reference` and multi-volume attach require **v2.4.0+**). The Homebrew tap can lag; prefer the [GitHub releases](https://github.com/runpod/runpodctl/releases) binary and check `runpodctl version`.
