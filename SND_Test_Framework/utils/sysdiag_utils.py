import logging
from .common_utils import ssh_execute, get_timestamp

logger = logging.getLogger("utils.sysdiag_utils")

def run_sysdiagnose(host: str, user: str, output_dir: str):
    """
    Triggers a remote sysdiagnose on the DUT.
    """
    cmd = "sudo sysdiagnose -f /tmp"
    return ssh_execute(host, user, cmd, output_dir)

def run_logarchive(host: str, user: str, output_dir: str):
    """
    Runs logarchive (e.g., tars up logs) on the DUT.
    """
    remote_archive = "/tmp/log_archive.tar.gz"
    tar_cmd = f"tar czf {remote_archive} /var/log /Library/Logs"
    rc, out, err = ssh_execute(host, user, tar_cmd, output_dir)
    if rc == 0:
        try:
            subprocess.call(f"scp {user}@{host}:{remote_archive} {output_dir}/{host.replace('.', '_')}_logs.tar.gz", shell=True)
            logger.info(f"Archived logs from {host} to {output_dir}/{host.replace('.', '_')}_logs.tar.gz")
        except Exception as e:
            logger.error(f"SCP failed: {e}", exc_info=True)
    else:
        logger.error(f"Failed to create remote archive on {host}: {err}")

def erase_logs(host: str, user: str):
    """
    Removes all logs on the DUT.
    """
    cmd = "sudo rm -rf /var/log/*"
    return ssh_execute(host, user, cmd, local_log_dir="logs")
