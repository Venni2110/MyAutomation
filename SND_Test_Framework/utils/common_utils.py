import os
import time
import logging
from .wlan_utils import cleanup_scan_cache, wifi_on, wifi_off
from .ssh_utils import clear_saved_networks
from .sysdiag_utils import erase_logs

logger = logging.getLogger("utils.common_utils")

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
