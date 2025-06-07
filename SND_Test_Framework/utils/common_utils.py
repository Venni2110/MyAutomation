import os
import time
import logging
import subprocess

from colored_print import print_step
from .wlan_utils import cleanup_scan_cache, wifi_on, wifi_off
from .sysdiag_utils import erase_logs

logger = logging.getLogger("utils.common_utils")

def ssh_execute(host: str, user: str, command: str, log_dir: str = "logs"):
    """
    Executes an SSH command on the given host and writes stdout/stderr to log_dir.
    Returns (returncode, stdout, stderr)
    """
    log_file = os.path.join(log_dir, f"{host.replace('.', '_')}_ssh_output.txt")
    full_cmd = f"ssh {user}@{host} '{command}'"

    try:
        result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
        with open(log_file, "a") as f:
            f.write(f"$ {full_cmd}\n")
            f.write(result.stdout)
            f.write(result.stderr)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        logger.error(f"SSH execution failed: {e}", exc_info=True)
        return 1, "", str(e)

def get_timestamp():
    """Returns a formatted UTC timestamp string."""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

def prepare_workspace(dut: str, base_log_dir: str = "logs"):
    """
    Prepares local directories and performs remote cleanup on the DUT.
    """
    dut_dir = os.path.join(base_log_dir, dut.replace(".", "_"))
    for sub in ["sniffer", "tcpdump", "sysdiag", "attenuator", "common"]:
        os.makedirs(os.path.join(dut_dir, sub), exist_ok=True)
    logger.info(f"Created workspace at {dut_dir}")

    # Remote cleanup
    erase_logs(dut, user="root")
    clear_saved_networks(dut, user="root")
    cleanup_scan_cache(dut, user="root")

    # Restart Wi-Fi
    wifi_off(dut, user="root")
    time.sleep(1)
    wifi_on(dut, user="root")
    logger.info(f"Finished remote cleanup for {dut}")

def countdown(seconds: int):
    """Print a dark-orange countdown for long sleeps or traffic durations."""
    for rem in range(seconds, 0, -1):
        print_step(f"{rem} seconds remaining…")
        time.sleep(1)
    print_step("Done.")

def start_iperf_server(host, user, port=5201, log_dir="logs", udp=False):
    """
    Starts iperf3 server on specified host and port (TCP or UDP).
    """
    proto_flag = "-u" if udp else ""
    cmd = f"iperf3 {proto_flag} -s -p {port} -D"
    return ssh_execute(host, user, cmd, log_dir)

def stop_iperf_server(host, user, log_dir="logs"):
    """
    Stops iperf3 server via pkill.
    """
    cmd = "pkill iperf3"
    return ssh_execute(host, user, cmd, log_dir)

def start_iperf_client(host, user, server_ip, port, duration=10, log_dir="logs", udp=False, bidir=False):
    """
    Starts iperf3 client connecting to a remote iperf3 server.
    """
    proto_flag = "-u" if udp else ""
    bidi_flag = "--bidir" if bidir else ""
    cmd = f"iperf3 -c {server_ip} {proto_flag} {bidi_flag} -p {port} -t {duration} -i 1"
    return ssh_execute(host, user, cmd, log_dir)
