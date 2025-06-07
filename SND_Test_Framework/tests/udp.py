import logging
from colored_print import print_step
import time
from utils.ssh_utils import associate_connection, disable_lmac_throttling, ssh_execute

logger = logging.getLogger("tests.udp")

def run_test(dut: str, test_params: dict, remote_list: list, global_flags: dict, barrier):
    logger = logging.getLogger(__name__)
    print_step("Running test...")
    logger.info("Starting run_test...")
    ssid = test_params["ap_wifi_ssid"]
    pwd  = test_params["ap_wifi_pwd"]
    user = test_params.get("User", "root")
    duration = int(test_params.get("test_cycle_count", 30))
    direction = test_params.get("TrafficDirection", "DL").upper()
    udp_bw = test_params.get("UDPBW", "10M")

    # Barrier to sync association
    barrier.wait()

    rc, out, err = associate_connection(dut, user, ssid, pwd, test_params.get("dut_wifi_interface", "wlan0"))
    if rc != 0:
        logger.error(f"[UDP] Association FAILED on {dut}: {err}")
    print_step("Test execution complete.")
    logger.info("Test execution complete.")
        return
    disable_lmac_throttling(dut, user)

    # Start traffic based on direction
    if direction == "UL":
        # DUT is server
        ssh_execute(dut, user, "iperf3 -s -u -D", test_params.get("test_log_path", "logs"))
        for remote in remote_list:
            ssh_execute(remote, user, f"iperf3 -u -b {udp_bw} -c {dut} -t {duration}", test_params.get("test_log_path", "logs"))
    elif direction == "DL":
        # Remote is server
        for remote in remote_list:
            ssh_execute(remote, user, "iperf3 -s -u -D", test_params.get("test_log_path", "logs"))
        barrier.wait()  # sync traffic start
        for remote in remote_list:
            ssh_execute(dut, user, f"iperf3 -u -b {udp_bw} -c {remote} -t {duration}", test_params.get("test_log_path", "logs"))
    else:  # BIDIR
        # DUT client, remote server
        for remote in remote_list:
            ssh_execute(remote, user, "iperf3 -s -u -D", test_params.get("test_log_path", "logs"))
        barrier.wait()
        for remote in remote_list:
            ssh_execute(dut, user, f"iperf3 -u -b {udp_bw} -c {remote} -t {duration} --bidir", test_params.get("test_log_path", "logs"))

    time.sleep(duration + 5)
