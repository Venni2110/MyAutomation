import logging
import time
from colored_print import print_step
from utils.wlan_utils import initiate_assoc_connect, initiate_forgetNw
from utils.common_utils import countdown

logger = logging.getLogger("tests.idle")

def run_test(dut: str, test_params: dict, remote_list: list, global_flags: dict, barrier):
    logger = logging.getLogger(__name__)
    print_step(f"[{dut}] Starting Idle test...")
    logger.info(f"[{dut}] Starting Idle run_test")

    ssid     = test_params["ap_wifi_ssid"]
    pwd      = test_params["ap_wifi_pwd"]
    sec      = test_params["ap_wifi_sec"]
    user     = test_params.get("User", "root")
    duration = int(test_params.get("test_cycle_count", 30))
    log_dir = test_params.get("test_log_path", "logs")
    
    # Sync all DUTs
    barrier.wait()
    # Step 1: Forget the network to ensure a clean join
    print_step(f"[{dut}] Forgetting and associating to {ssid}")
    initiate_forgetNw(dut, user)

    # Step 2: Attempt to associate
    join_success = False
    for attempt in range(1, 4):
        rc, out, err = initiate_assoc_connect(dut, user, ssid, sec, pwd, for_debug=True, log_dir=log_dir)
        if rc == 0:
            logger.info(f"[IDLE] Association attempt {attempt} SUCCEEDED on {dut}")
            join_success = True
            break
        else:
            logger.warning(f"[IDLE] Association attempt {attempt} FAILED on {dut}: {err}")
            time.sleep(2)

    if not join_success:
        logger.error(f"[{dut}] Association failed after 3 attempts. Skipping idle wait.")
        print_step(f"[{dut}] ❌ Association failed — skipping idle hold.")
        return

    print_step(f"[{dut}] Holding idle state for {duration} seconds...")
    countdown(duration)

    print_step(f"[{dut}] ✅ Idle test complete")
    logger.info(f"[{dut}] Idle test completed successfully")
