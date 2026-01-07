# NixOS Dotfiles

個人 NixOS 聲明式環境配置 - 系統狀態即代碼，可重現、可回滾、可追蹤。

**技術棧**: Nix Flakes, NixOS, home-manager, Disko, nixos-wsl

## 為什麼做這個專案

每次換電腦或重裝系統都要花大量時間配置環境，而且「在我電腦上可以跑」的問題一直存在。用 NixOS 後，整個系統配置變成一份可以 Git 管理的代碼，在任何機器上執行同一份配置，結果完全一致。

## 核心功能

### 多環境支援

同一份 Flake 配置支援多種部署環境：

```nix
nixosConfigurations = {
  nazuna = mkNixOSConfig { user = nazuna; };  # 雲端伺服器
  akira = mkNixOSConfig { user = akira; };    # WSL
  mayuri = mkNixOSConfig { user = mayuri; };  # 桌面
};

homeConfigurations = {
  kurisu = mkHomeConfig { user = kurisu; };   # 純 home-manager
};
```

### 模組化架構

系統配置和使用者配置分層管理：

```text
home/           # 使用者級配置
├── core.nix    # 基礎工具（shell、編輯器）
├── dev.nix     # 開發環境（Node.js、Python）
├── gui.nix     # 桌面應用
└── cli/        # CLI 工具配置
    ├── helix.nix
    ├── git.nix
    └── tmux.nix

nixos/          # 系統級配置
├── boot.nix
├── network.nix
├── security.nix
└── gui.nix
```

### Disko 聲明式磁碟分區

不用手動 `fdisk` + `mkfs`，用 Nix 定義分區結構：

```nix
disko.devices.disk.main = {
  device = "/dev/sda";
  content.partitions = {
    ESP = {
      size = "500M";
      content = { type = "filesystem"; format = "vfat"; mountpoint = "/boot"; };
    };
    root = {
      size = "100%";
      content = {
        type = "btrfs";
        subvolumes = {
          "root" = { mountpoint = "/"; mountOptions = ["compress=zstd" "noatime"]; };
          "home" = { mountpoint = "/home"; };
          "nix"  = { mountpoint = "/nix"; };
        };
      };
    };
  };
};
```

配合 nixos-anywhere 可以遠端一鍵部署。

## 技術亮點

### 安全加固

基於 kernel-hardening-checker 建議的安全設定：

```nix
boot.kernel.sysctl = {
  "kernel.kptr_restrict" = 2;
  "kernel.dmesg_restrict" = 1;
  "net.ipv4.conf.all.rp_filter" = 1;
};

boot.blacklistedKernelModules = [
  "dccp" "sctp" "rds" "tipc"  # 不常用的網路協議
  "cramfs" "freevxfs" "hfs"   # 不常用的檔案系統
];
```

### 加密 DNS

使用 dnscrypt-proxy 確保 DNS 查詢加密：

```nix
services.dnscrypt-proxy = {
  enable = true;
  settings = {
    require_dnssec = true;
    require_nolog = true;
    require_nofilter = true;
  };
};

networking.nameservers = [ "127.0.0.1" "::1" ];
```

### 開發環境自動載入

進入專案目錄自動載入對應的開發環境：

```nix
programs.direnv = {
  enable = true;
  nix-direnv.enable = true;  # 快取 nix shell，避免每次重新 eval
  silent = true;
};
```

搭配專案的 `flake.nix`，進入目錄就自動有該專案需要的工具。

### Comma 指令

臨時使用任何套件，不污染系統：

```bash
, cowsay "Hello"  # 自動下載執行，用完不留痕跡
```

```nix
programs.nix-index-database.comma.enable = true;
```

## 專案連結

- **原始碼**: [github.com/uigleki/dotfiles](https://github.com/uigleki/dotfiles)
