import logging
import time
from colored_print import print_step
from utils.common_utils import (
    start_iperf_server, stop_iperf_server, start_iperf_client
)
from utils.ssh_utils import associate_connection, disable_lmac_throttling

logger = logging.getLogger("tests.tcp")

def run_test(dut: str, test_params: dict, remote_list: list, global_flags: dict, barrier):
    logger = logging.getLogger(__name__)
    print_step(f"[{dut}] Starting TCP test execution")
    logger.info("Starting TCP run_test")

    ssid = test_params["ap_wifi_ssid"]
    pwd  = test_params["ap_wifi_pwd"]
    user = test_params.get("User", "root")
    duration = int(test_params.get("test_cycle_count", 30))
    direction = test_params.get("TrafficDirection", "DL").upper()
    log_dir = test_params.get("test_log_path", "logs")

    # Assign unique port per DUT for parallel safety
    iperf_port = 5200 + int(dut.split('.')[-1]) % 100  # ensures unique port below 5300

    barrier.wait()

    rc, out, err = associate_connection(dut, user, ssid, pwd, test_params.get("dut_wifi_interface", "wlan0"))
    if rc != 0:
        logger.error(f"[TCP] Association FAILED on {dut}: {err}")
        return

    disable_lmac_throttling(dut, user)
    logger.info(f"[{dut}] Association and LMAC disable complete")

    if direction == "UL":
        print_step(f"[{dut}] UL: DUT is iperf3 server, remote is client")
        start_iperf_server(dut, user, iperf_port, log_dir)
        for remote in remote_list:
            start_iperf_client(remote, user, dut, iperf_port, duration, log_dir)
    elif direction == "DL":
        print_step(f"[{dut}] DL: Remote is iperf3 server, DUT is client")
        for remote in remote_list:
            start_iperf_server(remote, user, iperf_port, log_dir)
        barrier.wait()
        for remote in remote_list:
            start_iperf_client(dut, user, remote, iperf_port, duration, log_dir)
    elif direction == "BIDIR":
        print_step(f"[{dut}] BIDIR: Remote is server, DUT does bidirectional")
        for remote in remote_list:
            start_iperf_server(remote, user, iperf_port, log_dir)
        barrier.wait()
        for remote in remote_list:
            start_iperf_client(dut, user, remote, iperf_port, duration, log_dir, bidir=True)

    time.sleep(duration + 5)
    print_step(f"[{dut}] Stopping iperf3 server(s)")
    if direction in ["DL", "BIDIR"]:
        for remote in remote_list:
            stop_iperf_server(remote, user, log_dir)
    elif direction == "UL":
        stop_iperf_server(dut, user, log_dir)

    print_step(f"[{dut}] TCP test complete")
    logger.info(f"[{dut}] TCP test completed")
