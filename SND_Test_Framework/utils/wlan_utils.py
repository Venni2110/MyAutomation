import logging
import subprocess
import time

from .common_utils import ssh_execute, get_timestamp

logger = logging.getLogger("utils.wlan_utils")

def wifi_off(dut: str, user: str = "root", for_debug: bool = False):
    """
    Turns Wi-Fi off on the DUT.
    """
    logger.info(f"[{dut}] Turning Wi-Fi OFF")
    cmd = "mobilewifitool manager power 0"
    rc, out, err = ssh_execute(dut, user, cmd)
    if rc != 0:
        logger.error(f"[{dut}] Wi-Fi OFF failed: {err}")
    else:
        logger.info(f"[{dut}] Wi-Fi is now OFF")

def wifi_on(dut: str, user: str = "root", for_debug: bool = False):
    """
    Turns Wi-Fi on on the DUT.
    """
    logger.info(f"[{dut}] Turning Wi-Fi ON")
    cmd = "mobilewifitool manager power 1"
    rc, out, err = ssh_execute(dut, user, cmd)
    if rc != 0:
        logger.error(f"[{dut}] Wi-Fi ON failed: {err}")
    else:
        logger.info(f"[{dut}] Wi-Fi is now ON")

def suppress_scan(dut: str, user: str = "root", for_debug: bool = False):
    """
    Tells the DUT to suppress any active scans:
      apple80211 -dbg=scansuppress=1
    """
    cmd = "apple80211 -dbg=scansuppress=1"
    if for_debug:
        print(f"[DEBUG] suppress_scan cmd on {dut}: {cmd}")
    return ssh_execute(dut, user, cmd, local_log_dir="logs")


def initiate_scan(dut: str, user: str = "root", for_debug: bool = False):
    """
    Instructs the DUT to perform an on-demand Wi-Fi scan via `wifiutil`.
    Sleeps 1 second afterward to let results populate.
    """
    cmd = "wifiutil scan; sleep 1"
    if for_debug:
        print(f"[DEBUG] initiate_scan cmd on {dut}: {cmd}")
    return ssh_execute(dut, user, cmd, local_log_dir="logs")


def initiate_connect(
    dut: str,
    user: str = "root",
    dut_wifi_interface: str,
    ap_wifi_ssid: str = "",
    ap_wifi_pwd: str = "",
    for_debug: bool = False
):
    """
    Uses 'mobilewifitool -- join' on macOS to connect the DUT to the specified SSID.
    If ap_wifi_pwd == "", it does an open join; otherwise, it passes the password.
    Sleeps 1 second after attempting to join.
    """
    if ap_wifi_pwd.strip() == "":
        cmd = f"mobilewifitool -- join -i {dut_wifi_interface} --ssid {ap_wifi_ssid}; sleep 1"
    else:
        cmd = (
            f"mobilewifitool -- join -i {dut_wifi_interface} "
            f"--ssid {ap_wifi_ssid} --password {ap_wifi_pwd}; sleep 1"
        )
    if for_debug:
        print(f"[DEBUG] initiate_connect cmd on {dut}: {cmd}")
    return ssh_execute(dut, user, cmd, local_log_dir="logs")


def initiate_assoc_connect(
    dut: str,
    user: str = "root",
    ap_wifi_ssid: str,
    ap_wifi_sec: str,
    ap_wifi_pwd: str = "",
    for_debug: bool = False
):
    """
    Uses 'wifiutil assoc' on macOS to connect the DUT to the specified SSID,
    supporting both open/OWE and secured (WPA2/WPA3) networks.
    Sleeps 5 seconds afterward to allow association to complete.
    """
    if ap_wifi_sec.lower() in ("open", "owe", "owe-transition"):
        cmd = f"wifiutil assoc -ssid {ap_wifi_ssid} -remember"
    else:
        cmd = (
            f"wifiutil assoc -ssid {ap_wifi_ssid} "
            f"-security {ap_wifi_sec} -password {ap_wifi_pwd} -remember"
        )
    if for_debug:
        print(f"[DEBUG] initiate_assoc_connect cmd on {dut}: {cmd}")
    return ssh_execute(dut, user, cmd, local_log_dir="logs")


def initiate_forgetNw(dut: str, user: str = "root", for_debug: bool = False):
    """
    Uses 'wifiutil remove_all_known_networks' to clear every stored SSID
    from the DUT’s memory. Sleeps 1 second afterward.
    """
    cmd = "wifiutil remove_all_known_networks; sleep 1"
    if for_debug:
        print(f"[DEBUG] initiate_forgetNw cmd on {dut}: {cmd}")
    return ssh_execute(dut, user, cmd, local_log_dir="logs")


def scan(dut: str, user: str = "root", interface: str = "wlan0"):
    """
    Alternate Linux-based scan.
    """
    cmd = f"sudo iw {interface} scan > /dev/null 2>&1"
    return ssh_execute(dut, user, cmd, local_log_dir="logs")


def associate(
    dut: str,
    user: str = "root",
    ssid: str,
    password: str,
    interface: str = "wlan0"
):
    """
    Linux-based association via nmcli.
    """
    cmd = f"nmcli dev wifi connect '{ssid}' password '{password}' ifname {interface}"
    return ssh_execute(dut, user, cmd, local_log_dir="logs")


def roam_profile(
    dut: str,
    user: str = "root",
    ssid_from: str,
    pwd_from: str,
    ssid_to: str,
    pwd_to: str,
    interface: str = "wlan0"
):
    """
    Example roaming logic: disassociate then associate.
    """
    ssh_execute(dut, user, f"nmcli con down id '{ssid_from}'", local_log_dir="logs")
    time.sleep(1)
    cmd = f"nmcli dev wifi connect '{ssid_to}' password '{pwd_to}' ifname {interface}"
    return ssh_execute(dut, user, cmd, local_log_dir="logs")


def get_country_code(dut: str, user: str = "root", interface: str = "wlan0") -> str:
    """
    Returns current regulatory domain.
    """
    cmd = "iw reg get | grep country | awk '{print $2}'"
    rc, out, err = ssh_execute(dut, user, cmd, local_log_dir="logs")
    if rc == 0:
        return out.strip()
    else:
        logger.error(f"Failed to get country code on {dut}: {err}")
        return ""


def get_mlo_status(dut: str, user: str = "root", interface: str = "wlan0") -> str:
    """
    Returns MLO-related status via apple80211.
    """
    cmd = "apple80211 -cca -ssid -rssi --noise -channel -bssid -dbg='mlo_status'"
    rc, out, err = ssh_execute(dut, user, cmd, local_log_dir="logs")
    if rc == 0:
        return out.strip()
    else:
        logger.error(f"Failed to get MLO status on {dut}: {err}")
        return ""


def start_wlan_status_loop(
    dut: str,
    user: str = "root",
    iteration_log_path: str,
    duration_s: int = 30,
    for_debug: bool = False
) -> int:
    """
    Starts a background SSH loop on the DUT that collects wlan_status and returns the remote PID.
    """

    loop_count = duration_s + 2

    # This is the full remote shell command to run via SSH
    remote_cmd = (
        f'for i in {{0..{loop_count}}}; '
        f'do /System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport '
        f'-I; echo; sleep 0.92; done > {iteration_log_path}/wlan_status.txt & echo $!'
    )

    # Construct SSH command
    ssh_cmd = f"ssh {user}@{dut} '{remote_cmd}'"

    if for_debug:
        print(f"[DEBUG] start_wlan_status_loop on {dut}: {ssh_cmd}")

    try:
        proc = subprocess.Popen(ssh_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)
        out, err = proc.communicate(timeout=10)

        if proc.returncode == 0:
            pid = int(out.strip().splitlines()[-1])
            logger.info(f"Started wlan_status loop on {dut} (PID={pid})")
            return pid
        else:
            logger.error(f"[{dut}] Failed to start wlan_status loop: {err}")
            return 0
    except Exception as e:
        logger.error(f"[{dut}] Exception in start_wlan_status_loop: {e}", exc_info=True)
        return 0


def stop_wlan_status_loop(dut: str, user: str = "root", pid: int):
    """
    Stops background wlan_status loop.
    """
    if not pid:
        return
    cmd = f"kill {pid}"
    ssh_execute(dut, user, cmd, local_log_dir="logs")


def start_background_command(
    dut: str,
    user: str = "root",
    cmd: str,
    remote_output_path: str,
    for_debug: bool = False
) -> int:
    """
    Launches any command in background on DUT.
    """
    bg_cmd = f"{cmd} > {remote_output_path} 2>&1 & echo $!"
    ssh_cmd = f"ssh {user}@{dut} '{bg_cmd}'"
    if for_debug:
        print(f"[DEBUG] start_background_command on {dut}: {ssh_cmd}")
    proc = subprocess.Popen(ssh_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)
    out, err = proc.communicate(timeout=10)
    if proc.returncode == 0:
        pid = int(out.strip().splitlines()[-1])
        return pid
    else:
        logger.error(f"Failed to start background command on {dut}: {err}")
        return 0


def fetch_background_output(
    dut: str,
    user: str = "root",
    remote_output_path: str,
    local_output_path: str,
    for_debug: bool = False
) -> bool:
    """
    Retrieves output of background command via SCP.
    """
    scp_cmd = f"scp {user}@{dut}:{remote_output_path} {local_output_path}"
    if for_debug:
        print(f"[DEBUG] fetch_background_output on {dut}: {scp_cmd}")
    ret = subprocess.call(scp_cmd, shell=True)
    return ret == 0
