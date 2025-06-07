import logging
import time
from colored_print import print_step
from utils.common_utils import (
    start_iperf_server, stop_iperf_server, start_iperf_client
)
from utils.wlan_utils import initiate_assoc_connect, initiate_forgetNw

logger = logging.getLogger("tests.udp")

def run_test(dut: str, test_params: dict, remote_list: list, global_flags: dict, barrier):
    logger = logging.getLogger(__name__)
    print_step(f"[{dut}] Starting UDP test execution")
    logger.info(f"[{dut}] Starting UDP run_test")

    ssid     = test_params["ap_wifi_ssid"]
    pwd      = test_params["ap_wifi_pwd"]
    sec      = test_params["ap_wifi_sec"]
    user     = test_params.get("User", "root")
    duration = int(test_params.get("test_cycle_count", 30))
    udp_bw   = test_params.get("UDPBW", "10M")
    direction = test_params.get("TrafficDirection", "DL").upper()
    log_dir  = test_params.get("test_log_path", "logs")

    # Assign unique port for each DUT (UDP range)
    iperf_port = 5300 + int(dut.split('.')[-1]) % 100

    barrier.wait()
    # Step 1: Clear saved networks
    print_step(f"[{dut}] Forgetting network before association")
    initiate_forgetNw(dut, user)

    # Step 2: Attempt to Join network
    print_step(f"[{dut}] Attempting association to {ssid} (up to 3 retries)")
    join_success = False
    for attempt in range(1, 4):
        start_t = time.time()
        rc, out, err = initiate_assoc_connect(dut, user, ssid, sec, pwd, for_debug=True)
        end_t = time.time()

        if rc == 0:
            logger.info(f"[UDP] Attempt {attempt} SUCCEEDED on {dut} in {end_t - start_t:.2f}s")
            join_success = True
            break
        else:
            logger.warning(f"[UDP] Attempt {attempt} FAILED on {dut}: {err}")
            time.sleep(2)

    if not join_success:
        logger.error(f"[{dut}] UDP test aborted: association failed after 3 attempts")
        print_step(f"[{dut}] ❌ Join failed — traffic skipped.")
        return

    # Step 3: Run UDP iperf3 traffic
    if direction == "UL":
        print_step(f"[{dut}] UL: DUT is UDP server, remote is client")
        start_iperf_server(dut, user, iperf_port, log_dir, udp=True)
        for remote in remote_list:
            start_iperf_client(remote, user, dut, iperf_port, duration, log_dir, udp=True)
    elif direction == "DL":
        print_step(f"[{dut}] DL: Remote is UDP server, DUT is client")
        for remote in remote_list:
            start_iperf_server(remote, user, iperf_port, log_dir, udp=True)
        barrier.wait()
        for remote in remote_list:
            start_iperf_client(dut, user, remote, iperf_port, duration, log_dir, udp=True)
    elif direction == "BIDIR":
        print_step(f"[{dut}] BIDIR: Remote is UDP server, DUT uses --bidir")
        for remote in remote_list:
            start_iperf_server(remote, user, iperf_port, log_dir, udp=True)
        barrier.wait()
        for remote in remote_list:
            start_iperf_client(dut, user, remote, iperf_port, duration, log_dir, udp=True, bidir=True)

    time.sleep(duration + 5)

    print_step(f"[{dut}] Stopping iperf3 UDP server(s)")
    if direction in ["DL", "BIDIR"]:
        for remote in remote_list:
            stop_iperf_server(remote, user, log_dir)
    elif direction == "UL":
        stop_iperf_server(dut, user, log_dir)

    print_step(f"[{dut}] ✅ UDP test complete")
    logger.info(f"[{dut}] UDP test completed successfully")
