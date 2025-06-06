import subprocess
import time
import os
import logging

logger = logging.getLogger("utils.ssh_utils")

def ssh_execute(host: str, user: str, cmd: str, local_log_dir: str, timeout: int = 300):
    """
    Executes `ssh user@host '<cmd>'`, captures stdout/stderr, writes them into
    timestamped .txt in local_log_dir/<host>/.
    Returns (returncode, stdout, stderr).
    """
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    host_dir = os.path.join(local_log_dir, host.replace(".", "_"))
    os.makedirs(host_dir, exist_ok=True)
    stdout_file = os.path.join(host_dir, f"{timestamp}_stdout.txt")
    stderr_file = os.path.join(host_dir, f"{timestamp}_stderr.txt")

    full_cmd = f"ssh {user}@{host} \"{cmd}\""
    logger.info(f"Running SSH command on {host}: {cmd}")
    try:
        proc = subprocess.Popen(
            full_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True
        )
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            out, err = proc.communicate()
            logger.error(f"SSH command timed out after {timeout}s: {cmd}")
            return proc.returncode, out, err

        with open(stdout_file, "w") as f_out:
            f_out.write(out)
        with open(stderr_file, "w") as f_err:
            f_err.write(err)

        if proc.returncode != 0:
            logger.error(f"SSH command returned rc={proc.returncode}. See {stderr_file}")
        else:
            logger.info(f"SSH command succeeded on {host}. Output at {stdout_file}")

        return proc.returncode, out, err
    except Exception as e:
        logger.error(f"ssh_execute exception on {host}: {e}", exc_info=True)
        return -1, "", str(e)

def get_dut_ip(host: str, user: str) -> str:
    """
    Returns the IP of wlan0 on the DUT.
    """
    cmd = "ip addr show wlan0 | grep 'inet ' | awk '{print $2}' | cut -d'/' -f1"
    rc, out, err = ssh_execute(host, user, cmd, local_log_dir="logs")
    if rc == 0 and out.strip():
        return out.strip().split()[0]
    else:
        logger.error(f"Could not get IP from {host}: {err}")
        return ""

def initiate_scan(host: str, user: str, interface: str = "wlan0"):
    cmd = f"sudo iw {interface} scan > /dev/null 2>&1 &"
    return ssh_execute(host, user, cmd, local_log_dir="logs")

def associate_connection(host: str, user: str, ssid: str, password: str, interface: str = "wlan0"):
    cmd = f"nmcli dev wifi connect '{ssid}' password '{password}' ifname {interface}"
    return ssh_execute(host, user, cmd, local_log_dir="logs")

def disable_lmac_throttling(host: str, user: str):
    cmd = "sudo iwpriv wlan0 set LMAC_EN_CAP=0"
    return ssh_execute(host, user, cmd, local_log_dir="logs")

def clear_saved_networks(host: str, user: str):
    cmd = "nmcli connection delete id '*'"
    return ssh_execute(host, user, cmd, local_log_dir="logs")
