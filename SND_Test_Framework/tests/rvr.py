import logging
import time
from utils.ssh_utils import associate_connection, disable_lmac_throttling, ssh_execute
from utils.attenuator_utils import set_attenuation

logger = logging.getLogger("tests.rvr")

def run_test(dut: str, test_params: dict, remote_list: list, global_flags: dict, barrier):
    ssid = test_params["ap_wifi_ssid"]
    pwd  = test_params["ap_wifi_pwd"]
    user = test_params.get("User", "root")
    start_attn = int(test_params.get("start_attn_1", 0))
    stop_attn = int(test_params.get("stop_attn_1", 0))
    step_attn = int(test_params.get("attn_step_dB", 1))
    duration = int(test_params.get("test_cycle_count", 30))
    direction = test_params.get("TrafficDirection", "DL").upper()

    # Barrier to sync association
    barrier.wait()

    rc, out, err = associate_connection(dut, user, ssid, pwd, test_params.get("dut_wifi_interface", "wlan0"))
    if rc != 0:
        logger.error(f"[RVR] Association FAILED on {dut}: {err}")
        return
    disable_lmac_throttling(dut, user)

    attn_points = list(range(start_attn, stop_attn + step_attn, step_attn))
    for attn in attn_points:
        if global_flags.get("enable_attenuator", False):
            set_attenuation(attn)
        # Barrier to sync after attenuation is set
        barrier.wait()

        if direction == "UL":
            ssh_execute(dut, user, "iperf3 -s -D", test_params.get("test_log_path", "logs"))
            for remote in remote_list:
                ssh_execute(remote, user, f"iperf3 -c {dut} -t {duration}", test_params.get("test_log_path", "logs"))
        elif direction == "DL":
            for remote in remote_list:
                ssh_execute(remote, user, "iperf3 -s -D", test_params.get("test_log_path", "logs"))
            barrier.wait()
            for remote in remote_list:
                ssh_execute(dut, user, f"iperf3 -c {remote} -t {duration}", test_params.get("test_log_path", "logs"))
        else:  # BIDIR
            for remote in remote_list:
                ssh_execute(remote, user, "iperf3 -s -D", test_params.get("test_log_path", "logs"))
            barrier.wait()
            for remote in remote_list:
                ssh_execute(dut, user, f"iperf3 -c {remote} -t {duration} --bidir", test_params.get("test_log_path", "logs"))

        time.sleep(duration + 5)
        # Kill iperf servers
        ssh_execute(dut, user, "pkill iperf3", test_params.get("test_log_path", "logs"))
        for remote in remote_list:
            ssh_execute(remote, user, "pkill iperf3", test_params.get("test_log_path", "logs"))

    # Reset attenuator
    if global_flags.get("enable_attenuator", False):
        set_attenuation(0)
