import logging
import time
from utils.ssh_utils import associate_connection, clear_saved_networks

logger = logging.getLogger("tests.autojoin")

def run_test(dut: str, test_params: dict, remote_list: list, global_flags: dict, barrier):
    ssid = test_params["ap_wifi_ssid"]
    pwd  = test_params["ap_wifi_pwd"]
    user = test_params.get("User", "root")
    rounds = int(test_params.get("join_attempts", 5))
    interval = int(test_params.get("join_on_off_interval", 1))

    # Barrier to sync first attempt
    barrier.wait()

    for i in range(rounds):
        clear_saved_networks(dut, user)
        time.sleep(1)
        start_t = time.time()
        rc, out, err = associate_connection(dut, user, ssid, pwd, test_params.get("dut_wifi_interface", "wlan0"))
        end_t = time.time()
        if rc != 0:
            logger.error(f"[AUTOJOIN] Round {i+1} FAILED on {dut}: {err}")
        else:
            logger.info(f"[AUTOJOIN] Round {i+1} SUCCEEDED on {dut} in {end_t - start_t:.2f}s")
        time.sleep(interval)
