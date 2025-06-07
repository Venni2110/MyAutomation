import logging
import time
from colored_print import print_step
from utils.wlan_utils import initiate_assoc_connect, initiate_forgetNw
from utils.common_utils import (
    start_iperf_server, stop_iperf_server, start_iperf_client
)
from utils.attenuator_utils import set_attenuation

logger = logging.getLogger("tests.rvr")

def run_test(dut: str, test_params: dict, remote_list: list, global_flags: dict, barrier):
    logger = logging.getLogger(__name__)
    print_step(f"[{dut}] Starting RvR test...")
    logger.info(f"[{dut}] Starting RvR test")

    ssid      = test_params["ap_wifi_ssid"]
    pwd       = test_params["ap_wifi_pwd"]
    sec       = test_params["ap_wifi_sec"]
    user      = test_params.get("User", "root")
    duration  = int(test_params.get("test_cycle_count", 30))
    direction = test_params.get("TrafficDirection", "DL").upper()
    log_dir   = test_params.get("test_log_path", "logs")

    # Support TCP or UDP
    protocol   = test_params.get("TrafficType", "TCP").upper()
    is_udp     = protocol == "UDP"
    udp_bw     = test_params.get("UDPBW", "10M") if is_udp else None

    # Attenuation sweep
    start_attn = int(test_params.get("start_attn_1", 0))
    stop_attn  = int(test_params.get("stop_attn_1", 0))
    step_attn  = int(test_params.get("attn_step_dB", 1))
    attn_points = list(range(start_attn, stop_attn + 1, step_attn))

    # Assign iperf port range for RvR
    iperf_port = 5400 + int(dut.split('.')[-1]) % 100

    # Sync before association
    barrier.wait()
    # Step 1: Clear saved networks
    print_step(f"[{dut}] Forgetting and associating to {ssid}")
    initiate_forgetNw(dut, user)

    # Step 2: Attempt to Join network
    print_step(f"[{dut}] Attempting association to {ssid} (with up to 3 retries)")
    join_success = False
    for attempt in range(1, 4):
        rc, out, err = initiate_assoc_connect(dut, user, ssid, sec, pwd, for_debug=True)
        if rc == 0:
            logger.info(f"[{dut}] Association attempt {attempt} SUCCEEDED")
            join_success = True
            break
        else:
            logger.warning(f"[{dut}] Association attempt {attempt} FAILED: {err}")
            time.sleep(2)

    if not join_success:
        logger.error(f"[{dut}] Association failed after 3 attempts. Skipping RvR test.")
        return
    
    # Step 3: Setting Attenuation
    for attn in attn_points:
        print_step(f"[{dut}] Setting attenuation to {attn} dB")
        if global_flags.get("enable_attenuator", False):
            set_attenuation(attn)

        barrier.wait()
        # Step 4: Run iperf traffic if join was successful
        print_step(f"[{dut}] Running {protocol} traffic at {attn} dB")
        if direction == "UL":
            start_iperf_server(dut, user, iperf_port, log_dir, udp=is_udp)
            for remote in remote_list:
                start_iperf_client(remote, user, dut, iperf_port, duration, log_dir, udp=is_udp, bandwidth=udp_bw)
        elif direction == "DL":
            for remote in remote_list:
                start_iperf_server(remote, user, iperf_port, log_dir, udp=is_udp)
            barrier.wait()
            for remote in remote_list:
                start_iperf_client(dut, user, remote, iperf_port, duration, log_dir, udp=is_udp, bandwidth=udp_bw)
        elif direction == "BIDIR":
            for remote in remote_list:
                start_iperf_server(remote, user, iperf_port, log_dir, udp=is_udp)
            barrier.wait()
            for remote in remote_list:
                start_iperf_client(dut, user, remote, iperf_port, duration, log_dir, udp=is_udp, bidir=True, bandwidth=udp_bw)

        time.sleep(duration + 5)

        print_step(f"[{dut}] Cleaning up iperf3 servers after attn {attn}")
        if direction in ["DL", "BIDIR"]:
            for remote in remote_list:
                stop_iperf_server(remote, user, log_dir)
        elif direction == "UL":
            stop_iperf_server(dut, user, log_dir)

    if global_flags.get("enable_attenuator", False):
        set_attenuation(0)
        print_step(f"[{dut}] Reset attenuator to 0 dB")

    print_step(f"[{dut}] ✅ RvR - {protocol} test complete")
    logger.info(f"[{dut}] ✅ RvR - {protocol} test completed successfully")
