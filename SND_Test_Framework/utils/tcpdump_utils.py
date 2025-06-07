import logging
import subprocess
import time
import os
from .common_utils import ssh_execute, get_timestamp

logger = logging.getLogger("utils.tcpdump_utils")

def start_tcpdump(host: str, user: str, interface: str, output_dir: str):
    """
    Starts tcpdump on the DUT via SSH.
    Returns the remote pcap file path.
    """
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    remote_pcap = f"/tmp/tcpdump_{timestamp}.pcap"
    cmd = f"nohup tcpdump -i {interface} -w {remote_pcap} > /dev/null 2>&1 &"
    rc, out, err = ssh_execute(host, user, cmd, output_dir)
    if rc == 0:
        logger.info(f"tcpdump started on {host}:{interface}, saving {remote_pcap}")
        return remote_pcap
    else:
        logger.error(f"Failed to start tcpdump on {host}: {err}")
        return None

def stop_tcpdump(host: str, user: str, remote_pcap: str):
    """
    Stops tcpdump on the DUT.
    """
    cmd = "pkill -SIGINT -f tcpdump"
    rc, out, err = ssh_execute(host, user, cmd, local_log_dir="logs")
    if rc == 0:
        logger.info(f"tcpdump stopped on {host}")
    else:
        logger.error(f"Failed to stop tcpdump on {host}: {err}")
