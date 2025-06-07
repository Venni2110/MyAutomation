import logging
from colored_print import print_step
import time
from utils.ssh_utils import associate_connection

logger = logging.getLogger("tests.join")

def run_test(dut: str, test_params: dict, remote_list: list, global_flags: dict, barrier):
    logger = logging.getLogger(__name__)
    print_step("Running test...")
    logger.info("Starting run_test...")
    ssid = test_params["ap_wifi_ssid"]
    pwd  = test_params["ap_wifi_pwd"]
    user = test_params.get("User", "root")

    # Barrier to sync all DUTs before association
    barrier.wait()

    start_t = time.time()
    rc, out, err = associate_connection(dut, user, ssid, pwd, test_params.get("dut_wifi_interface", "wlan0"))
    end_t = time.time()
    if rc != 0:
        logger.error(f"[JOIN] FAILED on {dut}: {err}")
    else:
        logger.info(f"[JOIN] SUCCEEDED on {dut} in {end_t - start_t:.2f}s")
