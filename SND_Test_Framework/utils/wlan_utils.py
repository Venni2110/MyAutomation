import logging
from .ssh_utils import ssh_execute

logger = logging.getLogger("utils.wlan_utils")

def cleanup_scan_cache(host: str, user: str, interface: str = "wlan0"):
    cmd = f"sudo rm -rf /var/lib/wpa_supplicant/{interface}/*"
    return ssh_execute(host, user, cmd, local_log_dir="logs")

def wifi_on(host: str, user: str):
    cmd = "nmcli radio wifi on"
    return ssh_execute(host, user, cmd, local_log_dir="logs")

def wifi_off(host: str, user: str):
    cmd = "nmcli radio wifi off"
    return ssh_execute(host, user, cmd, local_log_dir="logs")

def get_country_code(host: str, user: str, interface: str = "wlan0") -> str:
    cmd = "iw reg get | grep country | awk '{print $2}'"
    rc, out, err = ssh_execute(host, user, cmd, local_log_dir="logs")
    if rc == 0:
        return out.strip()
    else:
        return ""

def get_wlan_status(host: str, user: str, interface: str = "wlan0") -> str:
    cmd = "iw dev wlan0 link"
    rc, out, err = ssh_execute(host, user, cmd, local_log_dir="logs")
    if rc == 0:
        return out.strip()
    else:
        return ""
