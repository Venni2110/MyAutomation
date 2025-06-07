
import subprocess
import logging
from .common_utils import ssh_execute, get_timestamp

logger = logging.getLogger("utils.wlan_firmware_utils")

def clean_firmware_logs(dut, user):
    logger.info(f"Cleaning Atlas logs on {dut}")
    cmd = "rm -rf /var/internal/Logs/Atlas/*"
    return ssh_execute(dut, user, cmd, local_log_dir="logs")

def start_firmware_log(dut, user):
    logger.info(f"Starting Atlas logging on {dut}")
    cmd = "log collect --start --output /var/internal/Logs/Atlas/test_log_start.logarchive"
    return ssh_execute(dut, user, cmd, local_log_dir="logs")

def stop_and_pull_firmware_log(dut, user, local_log_dir):
    logger.info(f"Stopping and fetching Atlas logs from {dut}")
    stop_cmd = "log collect --stop --output /var/internal/Logs/Atlas/test_log_stop.logarchive"
    ssh_execute(dut, user, stop_cmd, local_log_dir)
    scp_cmd = f"scp {user}@{dut}:/var/internal/Logs/Atlas/*.logarchive {local_log_dir}/"
    subprocess.call(scp_cmd, shell=True)
