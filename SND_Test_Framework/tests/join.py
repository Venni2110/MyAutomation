import logging
import time
from colored_print import print_step
from utils.wlan_utils import initiate_assoc_connect, initiate_forgetNw

logger = logging.getLogger("tests.join")

def run_test(dut: str, test_params: dict, remote_list: list, global_flags: dict, barrier):
    logger = logging.getLogger(__name__)
    print_step(f"[{dut}] Starting Join test...")
    logger.info(f"[{dut}] Starting Join run_test")

    ssid     = test_params["ap_wifi_ssid"]
    pwd      = test_params["ap_wifi_pwd"]
    sec      = test_params["ap_wifi_sec"]
    user     = test_params.get("User", "root")
    rounds   = int(test_params.get("join_attempts", 5))
    interval = int(test_params.get("join_on_off_interval", 2))  # in seconds

    # Barrier to sync all DUTs before beginning test
    barrier.wait()

    for i in range(rounds):
        print_step(f"[{dut}] --- Round {i+1} ---")

        # Step 1: Forget the network to ensure a clean join
        print_step(f"[{dut}] Forgetting network before join")
        initiate_forgetNw(dut, user, for_debug=True)
        time.sleep(1)

        # Step 2: Attempt to associate
        print_step(f"[{dut}] Initiating association to {ssid}")
        start_t = time.time()
        rc, out, err = initiate_assoc_connect(dut, user, ssid, sec, pwd, for_debug=True)
        end_t = time.time()

        # Step 3: Log result
        if rc != 0:
            logger.error(f"[JOIN] Round {i+1} FAILED on {dut}: {err}")
        else:
            logger.info(f"[JOIN] Round {i+1} SUCCEEDED on {dut} in {end_t - start_t:.2f}s")

        # Step 4: Wait interval before next round
        time.sleep(interval)

    print_step(f"[{dut}] Join test complete.")
    logger.info(f"[{dut}] Join test completed successfully.")
