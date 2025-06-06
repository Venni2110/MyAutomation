import logging
import time
from utils.ssh_utils import associate_connection
from utils.ssh_utils import disable_lmac_throttling

logger = logging.getLogger("tests.idle")

def run_test(dut: str, test_params: dict, remote_list: list, global_flags: dict, barrier):
    ssid = test_params["ap_wifi_ssid"]
    pwd  = test_params["ap_wifi_pwd"]
    user = test_params.get("User", "root")
    duration = int(test_params.get("test_cycle_count", 30))

    # Barrier to sync association
    barrier.wait()

    rc, out, err = associate_connection(dut, user, ssid, pwd, test_params.get("dut_wifi_interface", "wlan0"))
    if rc != 0:
        logger.error(f"[IDLE] Association FAILED on {dut}: {err}")
        return

    disable_lmac_throttling(dut, user)
    logger.info(f"[IDLE] DUT {dut} is idle for {duration}s")
    time.sleep(duration)
