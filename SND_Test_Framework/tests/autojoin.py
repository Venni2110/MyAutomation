import logging
import time
from colored_print import print_step
from utils.wlan_utils import initiate_assoc_connect, initiate_forgetNw, wifi_on, wifi_off
from utils.common_utils import countdown

logger = logging.getLogger("tests.autojoin")

def run_test(dut: str, test_params: dict, remote_list: list, global_flags: dict, barrier):
    logger = logging.getLogger(__name__)
    print_step(f"[{dut}] Starting AutoJoin test...")
    logger.info(f"[{dut}] Starting AutoJoin run_test")

    ssid     = test_params["ap_wifi_ssid"]
    pwd      = test_params["ap_wifi_pwd"]
    sec      = test_params["ap_wifi_sec"]
    user     = test_params.get("User", "root")
    rounds   = int(test_params.get("join_attempts", 5))
    interval = int(test_params.get("join_on_off_interval", 2))  # interval between off/on
    log_dir = test_params.get("test_log_path", "logs")

    # Sync with other DUTs before beginning
    barrier.wait()

    # Initial association
    print_step(f"[{dut}] Initial association to {ssid}")
    rc, out, err = initiate_assoc_connect(dut, user, ssid, sec, pwd, for_debug=True)
    if rc != 0:
        logger.error(f"[{dut}] Initial association FAILED: {err}")
        return
    else:
        logger.info(f"[{dut}] Initial association SUCCEEDED")

    for i in range(rounds):
        print_step(f"[{dut}] --- Round {i+1} ---")

        # Turn Wi-Fi OFF
        print_step(f"[{dut}] Turning Wi-Fi OFF")
        wifi_off(dut, user)
        countdown(interval))

        # Turn Wi-Fi ON
        print_step(f"[{dut}] Turning Wi-Fi ON")
        wifi_on(dut, user)
        countdown(interval))

        # Start timing for rejoin
        start_t = time.time()

        # (Optional: re-check status or wait longer here if needed)
        # You can insert a loop to poll `get_wlan_status()` until connected

        end_t = time.time()
        logger.info(f"[{dut}] Rejoin attempt {i+1} completed in {end_t - start_t:.2f}s")

    print_step(f"[{dut}] AutoJoin test complete.")
    logger.info(f"[{dut}] AutoJoin test completed successfully.")
