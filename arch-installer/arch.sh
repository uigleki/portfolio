#!/usr/bin/env bash
set -eo pipefail

script_name=arch.sh
script_url=https://gitlab.com/uigleki/scripts/raw/main/shell/$script_name

scripts_name=scripts
scripts_repo=https://gitlab.com/uigleki/$scripts_name.git

user_var_file=/user_var
mapping_name=arch
city=Asia/Shanghai

pac_lib_src=/usr/lib/pacman/local
pac_lib_dest=/var/lib/pacman/local

main() {
    color
    check_root_permission

    case "$1" in
        '')
            do_continue_install=1
            ;;
        re | reinstall)
            rm -f $user_var_file
            do_reinstall=1
            ;;
        ss | ssh)
            open_ssh
            exit
            ;;
        wi | wifi)
            connect_wifi
            exit
            ;;
        -h | --help)
            usage 0
            ;;
        *)
            usage 1
            ;;
    esac

    check_efi
    install_proc
}

connect_wifi() {
    local iw_dev=$(iw dev | awk '$1=="Interface"{print $2}')

    iwctl station $iw_dev scan
    iwctl station $iw_dev get-networks
    echo -ne "${y}read:${e} wifi name you want to connect to: "
    read ssid
    iwctl station $iw_dev connect "$ssid"
}

open_ssh() {
    local interface=$(ip -o -4 route show to default | awk '{print $5}')
    local ip=$(ip -4 addr show $interface | grep -oP '(?<=inet\s)\d+(\.\d+){3}')

    read_only_format user_pass "enter your root passwd:" '^[-_,.a-zA-Z0-9]\+$'
    echo "${USER}:${user_pass}" | chpasswd
    systemctl start sshd

    echo -e "${g}# ssh ${USER}@${ip}${e}"
    echo -e "${g}passwd = ${user_pass}${e}"
}

install_proc() {
    check_chroot

    if [ "$do_reinstall" != 1 ] && [ "$in_chroot" != 1 ] && [ -f /mnt$user_var_file ]; then
        rsync -t /mnt$user_var_file $user_var_file
    else
        touch $user_var_file
    fi
    source $user_var_file

    if [ "$in_chroot" = 1 ]; then
        chroot_env_proc
    elif [ "$download_status" = 1 ]; then
        first_download
        after_first_download
    elif [ "$download_status" = 0 ]; then
        error 'already finished'
    else
        live_env_proc
    fi
}

live_env_proc() {
    before_first_download
    first_download
    after_first_download
}

before_first_download() {
    insure_mount_point
    check_network
    update_system_clock
    enter_user_var
    use_gui_or_not
    use_crypt_or_not
    set_partition
    set_crypt
    set_subvol
    set_pacman
}

after_first_download() {
    set_fstab
    set_mkinitcpio
    set_hostname
    change_root
}

chroot_env_proc() {
    set_time_zone
    set_locale
    set_network
    set_passwd
    set_pacman
    set_user_config
    system_config
    install_bootloader
    set_auto_start
}

insure_mount_point() {
    if [ -n "$(findmnt /mnt)" ]; then
        umount -fR /mnt
    fi

    if [ -b /dev/mapper/$mapping_name ]; then
        cryptsetup close /dev/mapper/$mapping_name
    fi
}

update_system_clock() {
    timedatectl set-ntp true
}

enter_user_var() {
    read_only_format host_name "enter your hostname:"    '^[a-zA-Z][-a-zA-Z0-9]*$'
    read_only_format user_name "enter your username:"    '^[a-z][-a-z0-9]*$'
    read_only_format user_pass "enter your user passwd:" '^[-_,.a-zA-Z0-9]\+$'
}

use_gui_or_not() {
    if [ -z "$use_gui" ]; then
        echo -ne "${y}sure:${e} use GUI or not? "
        read sure

        case "$sure" in
            y*)
                use_gui=1
                ;;
            n*)
                use_gui=0
                ;;
            *)
                if [ $(systemd-detect-virt) = none ]; then
                    use_gui=1
                else
                    use_gui=0
                fi
                ;;
        esac
        set_user_var use_gui
    fi
}

use_crypt_or_not() {
    if [ "$bios_type" = uefi ] && [ -n "$(cat /sys/class/tpm/tpm0/tpm_version_major)" ]; then
        use_crypt=1
    else
        use_crypt=0
    fi
    set_user_var use_crypt
}

set_partition() {
    select_a part_way "automatic partition or manual partition" automatic manual

    if [ "$part_way" = automatic ]; then
        select_partition main_part

        parted -s $main_part mklabel gpt
        if [ "$bios_type" = uefi ]; then
            parted -s $main_part \
                   mkpart esp 1m 513m \
                   set 1 esp on \
                   mkpart $mapping_name 513m 100%
        else
            parted -s $main_part \
                   mkpart grub 1m 3m \
                   set 1 bios_grub on \
                   mkpart $mapping_name 3m 100%
        fi

        if echo $main_part | grep -q 'nvme'; then
            boot_part="${main_part}p1"
            crypt_part="${main_part}p2"
        else
            boot_part="${main_part}1"
            crypt_part="${main_part}2"
        fi
        set_user_var boot_part
        set_user_var crypt_part

        if [ "$bios_type" = uefi ]; then
            mkfs.fat -F32 $boot_part
        fi
    else
        select_partition boot_part
        select_partition crypt_part
    fi
}

set_crypt() {
    if [ "$use_crypt" = 1 ]; then
        root_part=/dev/mapper/$mapping_name

        cryptsetup luksFormat $crypt_part
        systemd-cryptenroll --tpm2-device=auto --tpm2-pcrs=0+7 $crypt_part
        /usr/lib/systemd/systemd-cryptsetup attach $mapping_name $crypt_part
    else
        root_part=$crypt_part
    fi
    set_user_var root_part
}

set_subvol() {
    local subvol_list=(.snapshots home opt root srv 'usr/local' var)

    if [ "$bios_type" = bios ]; then
        subvol_list+=(boot)
    fi

    mkfs.btrfs -fL $mapping_name $root_part
    mount $root_part /mnt
    btrfs subvolume create /mnt/@

    for subvol in ${subvol_list[@]}; do
        mkdir -p /mnt/@/$(dirname $subvol)
        btrfs subvolume create /mnt/@/$subvol
    done

    # Disable COW for /var to improve database performance
    chattr +C /mnt/@/var
    mkdir /mnt/@/.snapshots/1
    btrfs subvolume create /mnt/@/.snapshots/1/snapshot
    # Set snapshot as default subvolume for rollback support
    local default_id=$(btrfs inspect-internal rootid /mnt/@/.snapshots/1/snapshot)
    btrfs subvolume set-default $default_id /mnt
    umount -R /mnt
    mount -o noatime,autodefrag,compress-force=zstd,discard=async $root_part /mnt

    for subvol in ${subvol_list[@]}; do
        mkdir -p /mnt/$subvol
        mount -o subvol=/@/$subvol $root_part /mnt/$subvol
    done

    if [ "$bios_type" = uefi ]; then
        mkdir /mnt/boot
        mount -o nodev,nosuid,noexec $boot_part /mnt/boot
    fi

    # Bind mount pacman DB to prevent desync during btrfs rollback
    mkdir -p     /mnt$pac_lib_src /mnt$pac_lib_dest
    mount --bind /mnt$pac_lib_src /mnt$pac_lib_dest
}

set_pacman() {
    sed -i '/^#Color$/s/#//' /etc/pacman.conf
    sed -i '/^#\[multilib\]/,+1s/^#//' /etc/pacman.conf

    cat << 'EOF' >> /etc/pacman.conf
[archlinuxcn]
Server = http://repo.archlinuxcn.org/$arch
EOF
}

first_download() {
    download_status=1
    set_user_var download_status

    local pkg_list=(base base-devel linux linux-firmware)
    pkg_list+=(apparmor arch-install-scripts archlinuxcn-keyring bash-language-server bat bottom btrfs-progs )
    pkg_list+=(chrony curl dnscrypt-proxy dosfstools dust eza fcron fd firewalld fish fuse-overlayfs fzf git )
    pkg_list+=(git-delta gocryptfs grub grub-btrfs helix iptables-nft lazygit man-pages-zh_cn mkinitcpio neovim )
    pkg_list+=(openssh p7zip pacman-contrib parted pkgstats podman-docker python-lsp-server qrencode ranger )
    pkg_list+=(reflector ripgrep rsync sd snap-pac snapper starship tealdeer tmux zoxide zram-generator zsh )

    if [ "$bios_type" = uefi ]; then
        pkg_list+=(efibootmgr)
    fi

    if [ "$use_gui" = 1 ]; then
        pkg_list+=(ark bridge-utils dnsmasq dolphin edk2-ovmf elisa fcitx5-chinese-addons fcitx5-im )
        pkg_list+=(fcitx5-pinyin-zhwiki ffmpegthumbs firefox-i18n-zh-cn flatpak foliate gwenview kio-gdrive konsole )
        pkg_list+=(kwalletmanager libvirt networkmanager nextcloud-client noto-fonts noto-fonts-cjk noto-fonts-emoji )
        pkg_list+=(noto-fonts-extra ntfs-3g okular openbsd-netcat os-prober partitionmanager phonon-qt5-vlc )
        pkg_list+=(pipewire-alsa pipewire-jack pipewire-pulse plasma-meta python-notify2 python-psutil )
        pkg_list+=(qbittorrent qemu-desktop sddm spectacle tesseract-data-eng ttf-liberation ttf-ubuntu-font-family )
        pkg_list+=(virt-manager vlc wireplumber wqy-zenhei xclip xdg-desktop-portal-kde xorg-xmodmap yakuake )
    else
        pkg_list+=(dhcpcd)
    fi

    local cpu_vendor=$(grep vendor_id /proc/cpuinfo)
    if echo "$cpu_vendor" | grep -q 'AuthenticAMD'; then
        pkg_list+=(amd-ucode)
    elif echo "$cpu_vendor" | grep -q 'GenuineIntel'; then
        pkg_list+=(intel-ucode)
    fi

    local lspci_VGA="$(lspci | grep '3D\|VGA')"
    if echo "$lspci_VGA" | grep -q 'AMD'; then
        pkg_list+=(xf86-video-amdgpu vulkan-radeon lib32-vulkan-radeon)
    fi
    if echo "$lspci_VGA" | grep -q 'Intel'; then
        pkg_list+=(vulkan-intel lib32-vulkan-intel)
    fi
    if echo "$lspci_VGA" | grep -q 'NVIDIA'; then
        pkg_list+=(nvidia lib32-nvidia-utils)
    fi

    find /mnt/boot -name '*ucode*' -delete
    pacstrap /mnt ${pkg_list[@]}

    del_user_var download_status
}

set_fstab() {
    # Temporarily unmount bind mount (genfstab can't detect them properly)
    umount /mnt$pac_lib_dest

    genfstab -L /mnt >> /mnt/etc/fstab

    mount --bind /mnt$pac_lib_src /mnt$pac_lib_dest

    # Manually add bind mount to fstab
    echo "${pac_lib_src} ${pac_lib_dest} none defaults,bind 0 0" >> /mnt/etc/fstab
}

set_mkinitcpio() {
    if [ "$use_crypt" = 1 ]; then
        cat << EOF > /mnt/etc/crypttab.initramfs
# Fields are: name, underlying device, passphrase, cryptsetup options.
${mapping_name} ${crypt_part} - tpm2-device=auto
EOF
        sed -i '/^HOOKS=/s/filesystems/systemd sd-encrypt &/' /mnt/etc/mkinitcpio.conf
    fi
}

set_hostname() {
    echo $host_name > /mnt/etc/hostname
}

change_root() {
    curl -fLo /mnt/$script_name $script_url
    chmod +x /mnt/$script_name

    rsync -t $user_var_file /mnt/$user_var_file

    arch-chroot /mnt /$script_name

    set_resolve
    rm /mnt/$script_name /mnt/$user_var_file

    umount -R /mnt

    set_user_var download_status 0
    echo -e "${y}please reboot.${e}"
}

set_resolve() {
    cat << EOF > /mnt/etc/resolv.conf
nameserver ::1
nameserver 127.0.0.1
options edns0 single-request-reopen
EOF
    chattr +i /mnt/etc/resolv.conf
}

set_time_zone() {
    ln -sf /usr/share/zoneinfo/$city /etc/localtime
    hwclock --systohc
}

set_locale() {
    sed -i '/#\(en_US\|zh_CN\).UTF-8/s/#//' /etc/locale.gen
    locale-gen
    echo 'LANG=en_US.UTF-8' > /etc/locale.conf
}

set_network() {
    cat << EOF >> /etc/hosts
127.0.0.1       localhost
::1             localhost
127.0.1.1       ${host_name}.localdomain ${host_name}
EOF
}

set_passwd() {
    find /etc/skel -name '.bash*' | xargs rm -rf
    echo "root:${user_pass}" | chpasswd
    useradd -mG wheel $user_name
    echo "${user_name}:${user_pass}" | chpasswd
    sed -i '/# %wheel .* NOPASSWD/s/# //' /etc/sudoers
}

set_user_config() {
    user_home=/home/$user_name
    set_user_var user_home

    local scripts_dir=$user_home/$scripts_name

    do_as_user git clone --depth=1 $scripts_repo $scripts_dir
    setup_sh

    if [ "$use_gui" = 1 ]; then
        setup_sh graphic
    else
        setup_sh server
    fi
}

setup_sh() {
    local setup_sh=$scripts_dir/shell/setup.sh

    do_as_user bash $setup_sh $1
}

system_config() {
    fix_mnt_point
    improve_security
    set_snapper
}

fix_mnt_point() {
    # Remove subvolid from fstab (it changes after snapshot restoration)
    local default_subvol="\/@\/.snapshots\/1\/snapshot"

    sed -i "s/,subvolid=[0-9]\+,subvol=${default_subvol}//" /etc/fstab
}

improve_security() {
    local security_misc_url=https://raw.githubusercontent.com/Whonix/security-misc/master/etc

    security_grub
    security_kernel
    apparmor_config

    # Network time protocol configuration
    curl https://raw.githubusercontent.com/GrapheneOS/infrastructure/main/chrony.conf > /etc/chrony.conf
    # Disable null passwords for users
    sed -i 's/ nullok//g' /etc/pam.d/system-auth
    # Disable coredump
    echo "* hard core 0" >> /etc/security/limits.conf
    # Disable su for regular users
    sed -i '/#auth *required/s/#//' /etc/pam.d/su
    # Network configuration access permissions
    chmod 600 /etc/NetworkManager/conf.d/*
}

security_grub() {
    curl $security_misc_url/default/grub.d/40_cpu_mitigations.cfg > /etc/grub.d/40_cpu_mitigations
    curl $security_misc_url/default/grub.d/40_distrust_cpu.cfg > /etc/grub.d/40_distrust_cpu
    curl $security_misc_url/default/grub.d/40_enable_iommu.cfg > /etc/grub.d/40_enable_iommu
    chmod 755 /etc/grub.d/*
}

security_kernel() {
    # Kernel module blacklist
    curl $security_misc_url/modprobe.d/30_security-misc.conf > /etc/modprobe.d/30_security-misc.conf
    # Enable bluetooth
    sed -i '/[Bb]luetooth/s/^/#/' /etc/modprobe.d/30_security-misc.conf
    chmod 600 /etc/modprobe.d/*

    # Secure kernel settings
    curl $security_misc_url/sysctl.d/30_security-misc.conf > /etc/sysctl.d/30_security-misc.conf
    sed -i '/kernel.yama.ptrace_scope=/s/2/3/' /etc/sysctl.d/30_security-misc.conf
    if [ "$use_gui" != 1 ]; then
        # Allow ICMP requests (ping)
        sed -i '/icmp.*ignore_all/s/^/#/' /etc/sysctl.d/30_security-misc.conf
    fi
    curl $security_misc_url/sysctl.d/30_silent-kernel-printk.conf > /etc/sysctl.d/30_silent-kernel-printk.conf
    chmod 600 /etc/sysctl.d/*
}

apparmor_config() {
    sed -i "s/quiet/& lsm=landlock,lockdown,yama,integrity,apparmor,bpf/" /etc/default/grub
    # Configure AppArmor parser cache
    sed -i '/#write-cache/s/#//' /etc/apparmor/parser.conf
    sed -i 's,#\(Include /etc/apparmor.d\)/,\1,' /etc/apparmor/parser.conf

    # AppArmor autostart
    chmod 600 /home/$user_name/.config/autostart/apparmor-notify.desktop
    # Audit log group
    echo 'log_group = wheel' >> /etc/audit/auditd.conf
}

set_snapper() {
    sed -i 's/SNAPPER_CONFIGS="/&root/' /etc/conf.d/snapper

    cat << EOF > /.snapshots/1/info.xml
<?xml version="1.0"?>
<snapshot>
  <type>single</type>
  <num>1</num>
  <date>$(date +'%F %T')</date>
  <cleanup>number</cleanup>
  <description>first root filesystem</description>
</snapshot>
EOF
    chmod 600 /.snapshots/1/info.xml
}

install_bootloader() {
    # Generate initramfs and restrict permissions
    chmod 600 /boot/initramfs-linux*
    mkinitcpio -P

    if [ "$bios_type" = uefi ]; then
        grub-install --target=x86_64-efi --efi-directory=/boot
    else
        # Extract disk from partition (/dev/nvme0n1p2 -> /dev/nvme0n1)
        if echo $root_part | grep -q 'nvme'; then
            local grub_part=$(echo $root_part | sed 's/p[0-9]$//')
        else
            local grub_part=$(echo $root_part | sed 's/[0-9]$//')
        fi
        grub-install --target=i386-pc $grub_part
    fi
    # Remove rootflags to fix grub's kernel search with btrfs snapshots
    sed -i 's/rootflags=subvol=${rootsubvol} //' /etc/grub.d/10_linux
    sed -i 's/rootflags=subvol=${rootsubvol} //' /etc/grub.d/20_linux_xen

    sed -i '/GRUB_TIMEOUT=/s/5/1/' /etc/default/grub

    if [ "$use_gui" = 1 ]; then
        # Multi-OS detection
        echo GRUB_DISABLE_OS_PROBER=false >> /etc/default/grub
    fi

    grub-mkconfig -o /boot/grub/grub.cfg
}

set_auto_start() {
    local mask_list=(systemd-resolved)
    local disable_list=(systemd-timesyncd)
    local enable_list=(auditd apparmor btrfs-scrub@-.timer chronyd dnscrypt-proxy fcron firewalld fstrim.timer paccache.timer pkgstats.timer systemd-oomd)

    if [ "$use_gui" = 1 ]; then
        enable_list+=(bluetooth libvirtd NetworkManager reflector.timer sddm)
    else
        enable_list+=(dhcpcd sshd)
    fi

    systemctl mask    ${mask_list[@]}
    systemctl disable ${disable_list[@]}
    systemctl enable  ${enable_list[@]}
}

do_as_user() {
    # Run command as user (not root) to avoid permission issues

    cd $user_home
    sudo -u $user_name "$@"
}

read_only_format() {
    local var_name="$1"
    local output_hint="$2"
    local matching_format="$3"

    if [ -z "${!var_name}" ]; then
        while true; do
            echo -ne "${y}read:${e} ${output_hint} "
            read reply
            if echo "$reply" | grep -q "$matching_format"; then
                break
            else
                echo -e "${r}wrong format.${e}"
            fi
        done
        set_user_var $var_name "$reply"
    fi
}

select_a() {
    local var_name="$1"
    local output_hint="$2"
    shift 2
    local option_list=($@)

    if [ -z "${!var_name}" ]; then
        echo -e "${y}sele:${e} ${output_hint}:"
        select option in ${option_list[@]}; do
            if [ "$option" != '' ] && [[ "${option_list[@]}" =~ "$option"  ]]; then
                break
            fi
        done
        set_user_var $var_name $option
    fi
}

select_partition() {
    local partition_name="$1"
    local partition_list=($(lsblk -lno NAME | grep '^\(nvme\|sd.\|vd.\)'))

    if [ -z "${!partition_name}" ]; then
        lsblk -o NAME,SIZE

        select_a part "select a partition as the ${y}${partition_name}${e} partition" ${partition_list[@]}
        set_user_var $partition_name /dev/$part
        del_user_var part
    fi
}

set_user_var() {
    local name="$1"
    local value="$2"
    if [ -z "$value" ]; then
        value="${!name}"
    fi

    del_user_var $name
    eval $name="$value"
    echo -e "${b}var${e} ${c}${name}${e} = ${g}${value}${e}"
    echo "${name}=${value}" >> $user_var_file
}

del_user_var() {
    local name="$1"

    unset $name
    touch $user_var_file
    sed -i "/^${name}=/d" $user_var_file
}

check_network() {
    if ping -c 1 -w 1 1.1.1.1 &> /dev/null; then
        echo -e "${g}network connection is successful.${e}"
    else
        error 'Network connection failed.'
    fi
}

check_efi() {
    if [ -d /sys/firmware/efi ]; then
        bios_type=uefi
    else
        bios_type=bios
    fi
}

check_chroot() {
    if systemd-detect-virt --chroot; then
        in_chroot=1
    else
        in_chroot=0
    fi
}

check_root_permission() {
    if [ "$USER" != root ]; then
        error 'no permission'
    fi
}

error() {
    local wrong_reason="$*"

    echo -e "${r}error:${e} ${wrong_reason}" >&2
    exit 1
}

color() {
    r='\033[31m' # red
    g='\033[32m' # green
    y='\033[33m' # yellow
    b='\033[34m' # blue
    p='\033[35m' # purple
    c='\033[36m' # cyan
    w='\033[37m' # white
    e='\033[0m'  # reset
}

usage() {
    local exit_code="$1"

    echo -e "${g}arch.sh${e} 0.1.0"
    echo -e "quick install arch"
    echo -e ""
    echo -e "${y}usage:${e}"
    echo -e "    arch.sh [options] [subcommand]"
    echo -e ""
    echo -e "${y}options:${e}"
    echo -e "    ${g}-h${e}, ${g}--help${e}"
    echo -e "        print this help message"
    echo -e ""
    echo -e "${y}subcommands:${e}"
    echo -e "    ${g}re${e}, ${g}reinstall${e}"
    echo -e "        reinstall arch"
    echo -e ""
    echo -e "    ${g}ss${e}, ${g}ssh${e}"
    echo -e "        open ssh service"
    echo -e ""
    echo -e "    ${g}wi${e}, ${g}wifi${e}"
    echo -e "        connect to a wifi"

    exit $exit_code
}

main "$@"
