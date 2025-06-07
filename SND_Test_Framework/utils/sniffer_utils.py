import logging
import time
from .common_utils import ssh_execute, get_timestamp

logger = logging.getLogger("utils.sniffer_utils")

def start_sniffer(host: str, user: str, interface: str, freq_info: dict, output_folder: str):
    """
    Starts a sniffer on the remote sniffer device.
    """
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    remote_pcap = f"/tmp/sniffer_{timestamp}.pcap"
    channel_param = freq_info.get("Ch_parameter", "")
    start_cmd = f"nohup sniffer_tool --iface {interface} {channel_param} -o {remote_pcap} > /dev/null 2>&1 &"
    rc, out, err = ssh_execute(host, user, start_cmd, output_folder)
    if rc == 0:
        logger.info(f"Sniffer started on {host}:{interface}, saving {remote_pcap}")
        return remote_pcap
    else:
        logger.error(f"Failed to start sniffer on {host}: {err}")
        return None

def stop_sniffer(host: str, user: str, remote_pcap: str):
    """
    Stops the sniffer by signaling sniffer_tool processes.
    """
    stop_cmd = "pkill -SIGINT -f sniffer_tool"
    rc, out, err = ssh_execute(host, user, stop_cmd, local_log_dir="logs")
    if rc == 0:
        logger.info(f"Sniffer stopped on {host}")
    else:
        logger.error(f"Failed to stop sniffer on {host}: {err}")
