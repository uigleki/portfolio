# Arch Linux Auto Installer

全自動化 Arch Linux 安裝腳本 - 從磁碟分割到系統加固一鍵完成。

**技術棧**: Bash, Btrfs, TPM 2.0, LUKS, AppArmor, systemd

## 學習歷程紀錄

這個腳本寫於 2020-2021 年，現已升級至 NixOS 聲明式配置。保留它是為了展示從「命令式管理」到「聲明式配置」的思維轉變歷程。

## 為什麼做這個專案

Arch Linux 安裝複雜且耗時，需要手動執行很多步驟：

- 磁碟分割、格式化
- 安裝套件、配置系統
- 設定網路、防火牆、加密
- 加固安全（AppArmor、內核參數）

我做了一個 720 行的 Bash 腳本，一鍵完成所有步驟。

## 主要功能

### 1. 智能硬體檢測

自動識別 CPU、GPU、UEFI/BIOS：

```bash
# CPU microcode
if grep -q "GenuineIntel" /proc/cpuinfo; then
    packages+=" intel-ucode"
elif grep -q "AuthenticAMD" /proc/cpuinfo; then
    packages+=" amd-ucode"
fi
```

### 2. TPM 2.0 全盤加密

UEFI 系統自動啟用 TPM 2.0 解鎖（綁定 PCR 0/7）：

```bash
# LUKS 加密
cryptsetup luksFormat $crypt_part

# 註冊 TPM 2.0
systemd-cryptenroll --tpm2-device=auto \
    --tpm2-pcrs=0+7 $crypt_part
```

如果韌體或 Secure Boot 被修改，TPM 會拒絕解鎖。

### 3. Btrfs 子卷架構

設計 Btrfs 快照回滾機制：

```bash
# 防止快照回滾時 pacman 資料庫不同步
mount --bind /usr/lib/pacman/local /var/lib/pacman/local
```

**為什麼需要這個**：Btrfs 快照回滾後，如果 `/var/lib/pacman/local`（套件資料庫）沒有回滾，會導致系統實際安裝的套件（/usr/bin）與 pacman 記錄不一致。因為 `/var` 和 root 是不同子卷，需要用 bind mount 讓它們保持同步。

### 4. 安全加固

整合 Whonix security-misc 和 GrapheneOS 的最佳實踐：

- CPU 漏洞緩解（Spectre/Meltdown）
- 內核參數加固（禁用 ptrace、eBPF）
- AppArmor 強制存取控制
- 加密 DNS（dnscrypt-proxy）
- 防火牆自動配置

## 為什麼被取代

Arch 安裝腳本的根本問題：**只能在全新安裝時執行**。

系統更新後無法保證環境一致性：

- 手動修改配置檔案，沒有版本控制
- 安裝新套件，無法追蹤依賴關係
- 系統更新可能破壞配置，難以回滾

這讓我意識到「命令式管理」的局限性，最終升級到 NixOS 的「聲明式配置」。

## 技術成長：命令式 → 聲明式

**Arch 腳本（命令式）**：

```bash
# 安裝套件
pacman -S firefox neovim

# 修改配置
echo "LANG=en_US.UTF-8" > /etc/locale.conf

# 啟用服務
systemctl enable sshd
```

問題：

- ❌ 執行一次後，系統狀態分散在各處
- ❌ 無法追蹤「系統現在是什麼狀態」
- ❌ 無法在其他機器上重現

**NixOS（聲明式）**：

```nix
# configuration.nix
{
  environment.systemPackages = [ pkgs.firefox pkgs.neovim ];
  i18n.defaultLocale = "en_US.UTF-8";
  services.openssh.enable = true;
}
```

優勢：

- ✅ 系統狀態即代碼，用 Git 追蹤
- ✅ 原子更新，失敗可即時回滾
- ✅ 完全可重現，在任何機器上結果一致

## 這個專案展示了什麼

### 系統架構理解

- **完整的系統安裝流程**：從磁碟分割 → 套件安裝 → 系統配置 → 自動啟動，每個步驟都清楚可控
- **模組化設計**：51 個函數，職責明確（硬體檢測、分割、加密、配置各自獨立）
- **對比 Windows/Ubuntu**：它們的安裝過程是黑盒子，你不知道背後發生什麼。Arch 這套流程讓你完全掌握系統的每個環節

### Shell 腳本能力

- 720 行複雜的狀態管理
- 斷點續傳機制（`/user_var` 持久化狀態）
- 輸入驗證（regex）
- 錯誤處理與恢復

### 整合能力

當時 Arch 沒有官方的一鍵安裝工具，大家都是寫腳本或用別人的腳本。我的腳本整合了：

- 安全專案的配置檔案（Whonix security-misc、GrapheneOS）
- 不同硬體的自動檢測和適配
- Btrfs 快照系統的正確設定

### 思維轉變

- 從「能用的自動化腳本」→「可維護的聲明式系統」
- 認識到命令式管理的局限性
- 學會追求「可重現性」而非「一次性解決」

## 反思

這個腳本很實用，但不夠優雅。它解決了「重複安裝」的問題，但沒解決「長期維護」的問題。

**升級到 NixOS 後**：

- 系統配置變成一份程式碼，可以用 Git 管理
- 不用擔心更新破壞配置，隨時可以回滾
- 可以在多台機器間快速同步環境

這是從「工具思維」到「系統思維」的轉變。

## 代碼文件

- [arch.sh](./arch.sh) - 主安裝腳本（720 行，51 函數）

**注意**：不建議直接使用這個腳本，它已經過時。如果你需要可重現的 Linux 環境，建議直接使用 NixOS。
