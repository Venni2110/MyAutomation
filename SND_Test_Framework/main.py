
import argparse
import sys
import threading
import logging
import os
import subprocess
import time
import pandas as pd

from logger_config import setup_logging
from colored_print import print_info, print_error, print_step
from utils.excel_loader import (
    load_execution_config,
    load_sniffer_config,
    load_sniffer_parameters,
    load_test_config
)
from utils import (
    common_utils, attenuator_utils, sniffer_utils,
    tcpdump_utils, sysdiag_utils, wlan_utils, wlan_firmware_utils
)
from utils.common_utils import ssh_execute


def per_dut_worker(
    dut: str,
    remote_list: list,
    test_params: dict,
    global_flags: dict,
    sniffer_devs: list,
    sniffer_params: dict,
    barrier: threading.Barrier
):
    logger = logging.getLogger(f"Worker.{test_params['Test_Type']}.{dut}")
    test_name     = test_params["Test_Type"]
    traffic_type  = test_params["TrafficType"]
    user          = test_params.get("User", "root")
    base_log_folder = global_flags.get("test_log_folder", "logs")

    print_step(f"📁 [{dut}] Creating log folders")
    dut_root       = os.path.join(base_log_folder, test_name, dut.replace(".", "_"))
    dut_sniffer_dir = os.path.join(dut_root, "sniffer")
    dut_tcpdump_dir = os.path.join(dut_root, "tcpdump")
    dut_sysdiag_dir = os.path.join(dut_root, "sysdiag")
    dut_atten_dir   = os.path.join(dut_root, "attenuator")
    dut_common_dir  = os.path.join(dut_root, "common")
    for d in [dut_sniffer_dir, dut_tcpdump_dir, dut_sysdiag_dir, dut_atten_dir, dut_common_dir]:
        os.makedirs(d, exist_ok=True)

    remote_dirs = {}
    for remote in remote_list:
        rd = os.path.join(dut_root, "remote", remote.replace(".", "_"))
        os.makedirs(rd, exist_ok=True)
        remote_dirs[remote] = rd

    print_step(f"🧼 [{dut}] Cleaning DUT logs and firmware logs")
    logger.info(f"[{dut}] Cleaning logs and saved states")
    common_utils.erase_logs(dut, user)
    time.sleep(1)
    common_utils.clear_saved_networks(dut, user)
    time.sleep(1)
    common_utils.cleanup_scan_cache(dut, user)
    time.sleep(1)
    common_utils.wifi_off(dut, user)
    time.sleep(2)
    common_utils.wifi_on(dut, user)
    time.sleep(1)
    wlan_firmware_utils.clean_firmware_logs(dut, user)
    time.sleep(1)
    wlan_firmware_utils.start_firmware_log(dut, user)
    logger.info(f"[{dut}] DUT cleanup and firmware log started.")

    print_step(f"📡 [{dut}] Starting logs (Attenuator, Sniffer, tcpdump)")
    try:
        if global_flags.get("enable_attenuator", False):
            start_attn = int(test_params.get("start_attn_1", 0))
            attenuator_utils.set_attenuation(start_attn)
            attn_was_set = True
            logger.info(f"[{dut}] Attenuator set to {start_attn} dB.")
        else:
            attn_was_set = False
            logger.info(f"[{dut}] Skipping attenuator.")
    except Exception as e:
        attn_was_set = False
        logger.error(f"[{dut}] Attenuator exception: {e}", exc_info=True)

    raw_ch_str = test_params.get("sniffer_channels", "")
    requested_channels = [ch.strip() for ch in raw_ch_str.split(",") if ch.strip()]
    sniffer_processes = []
    if global_flags.get("enable_sniffer", False) and requested_channels:
        for i, ch in enumerate(requested_channels):
            if i < len(sniffer_devs):
                sn_info = sniffer_devs[i]
                freq_info = sniffer_params.get(ch, {})
                pid_file = sniffer_utils.start_sniffer(
                    sn_info["ip"], sn_info["user"], sn_info["ifname"], freq_info, dut_sniffer_dir
                )
                sniffer_processes.append((sn_info, pid_file))
                logger.info(f"[{dut}] Started sniffer '{sn_info['name']}' on channel {ch}")
            else:
                logger.error(f"[{dut}] No sniffer available for channel {ch}")
    else:
        logger.info(f"[{dut}] Skipping sniffer.")

    if global_flags.get("enable_tcpdump", False):
        iface = test_params.get("dut_wifi_interface", "wlan0")
        tcpdump_handle = tcpdump_utils.start_tcpdump(dut, user, iface, dut_tcpdump_dir)
        logger.info(f"[{dut}] Started tcpdump.")
    else:
        tcpdump_handle = None
        logger.info(f"[{dut}] Skipping tcpdump.")

    sys_mode = str(global_flags.get("get_sysdiagnose", "")).lower()
    if sys_mode == "sysdiagnose":
        try:
            sysdiag_utils.run_sysdiagnose(dut, user, dut_sysdiag_dir)
            logger.info(f"[{dut}] Ran initial sysdiagnose.")
        except Exception as e:
            logger.error(f"[{dut}] Initial sysdiagnose exception: {e}", exc_info=True)
    elif sys_mode == "logarchive":
        try:
            sysdiag_utils.run_logarchive(dut, user, dut_sysdiag_dir)
            logger.info(f"[{dut}] Ran initial logarchive.")
        except Exception as e:
            logger.error(f"[{dut}] Initial logarchive exception: {e}", exc_info=True)
    else:
        logger.info("Skipping initial sysdiag/logarchive (global flag).")

    remote_handles = []
    if traffic_type.upper() == "TCP" and remote_list:
        rc, out, err = ssh_execute(remote_list[0], user, "iperf3 -s -D", remote_dirs[remote_list[0]])
        if rc == 0:
            remote_handles.append(("iperf3", remote_list[0]))
            logger.info(f"[{dut}] Started iperf3 server on remote {remote_list[0]}")
        else:
            logger.error(f"[{dut}] Failed to start iperf3 on remote {remote_list[0]}: {err}")

    print_step(f"🚀 [{dut}] Running test logic: {traffic_type}")
    test_exception = None
    try:
        mod_name = traffic_type.lower()
        test_module = __import__(f"tests.{mod_name}", fromlist=["run_test"])
        test_module.run_test(dut, test_params, remote_list, global_flags, barrier)
    except Exception as e:
        test_exception = e
        logger.error(f"[{dut}] Exception in test logic: {e}", exc_info=True)

    print_step(f"🧹 [{dut}] Collecting logs and cleaning up")
    if tcpdump_handle:
        try:
            tcpdump_utils.stop_tcpdump(dut, user, tcpdump_handle)
            logger.info(f"[{dut}] Stopped tcpdump.")
        except Exception as e:
            logger.error(f"[{dut}] Exception stopping tcpdump: {e}", exc_info=True)

    for sn_info, pid in sniffer_processes:
        try:
            sniffer_utils.stop_sniffer(sn_info["ip"], sn_info["user"], pid)
            logger.info(f"[{dut}] Stopped sniffer '{sn_info['name']}'.")
        except Exception as e:
            logger.error(f"[{dut}] Exception stopping sniffer '{sn_info['name']}': {e}", exc_info=True)

    if sys_mode == "sysdiagnose":
        try:
            sysdiag_utils.run_sysdiagnose(dut, user, dut_sysdiag_dir)
            logger.info(f"[{dut}] Ran final sysdiagnose.")
        except Exception as e:
            logger.error(f"[{dut}] Exception final sysdiagnose: {e}", exc_info=True)
    elif sys_mode == "logarchive":
        try:
            sysdiag_utils.run_logarchive(dut, user, dut_sysdiag_dir)
            logger.info(f"[{dut}] Ran final logarchive.")
        except Exception as e:
            logger.error(f"[{dut}] Exception final logarchive: {e}", exc_info=True)

    wlan_firmware_utils.stop_and_pull_firmware_log(dut, user, dut_common_dir)
    logger.info(f"[{dut}] Pulled Atlas firmware logs.")

    if attn_was_set and global_flags.get("enable_attenuator", False):
        try:
            attenuator_utils.set_attenuation(0)
            logger.info(f"[{dut}] Reset attenuator to 0 dB.")
        except Exception as e:
            logger.error(f"[{dut}] Exception resetting attenuator: {e}", exc_info=True)

    for handle, remote in remote_handles:
        if handle == "iperf3":
            try:
                ssh_execute(remote, user, "pkill iperf3", remote_dirs[remote])
                logger.info(f"[{dut}] Stopped iperf3 server on remote {remote}.")
            except Exception as e:
                logger.error(f"[{dut}] Exception stopping iperf3 on remote {remote}: {e}", exc_info=True)

    try:
        tar_path = f"{dut_root}.tar.gz"
        subprocess.call(f"tar czf {tar_path} -C {base_log_folder} {test_name}/{dut.replace('.', '_')}", shell=True)
        logger.info(f"[{dut}] Archived logs to {tar_path}")
    except Exception as e:
        logger.error(f"[{dut}] Exception archiving logs: {e}", exc_info=True)

    if test_exception:
        logger.error(f"[{dut}] ❌ Test FAILED.")
        print_step(f"[{dut}] ❌ Test FAILED.")
    else:
        logger.info(f"[{dut}] ✅ Test SUCCESSFUL.")
        print_step(f"[{dut}] ✅ Test SUCCESSFUL.")


def main():
    print_step("Parsing command-line arguments...")
    logger = setup_logging(log_file="testExecOutput.log", level=logging.INFO)
    logger.info("Started InfraFramework CLI parsing")
    parser = argparse.ArgumentParser()
    parser.add_argument("--excel_path", "-e", required=True, help="Path to Configurations_updated.xlsx")
    parser.add_argument("--tests_to_run", "-t", nargs="*", default=None,
                        help="Optional list of Test_Type names to run")
    args = parser.parse_args()

    print_info("InfraFramework starting...")
    logger.info("Logger initialized and output redirected to testExecOutput.log")

    print_step("Loading execution configuration and test definitions from Excel...")
    logger.info("Loading Excel configuration from %s", args.excel_path)
    global_flags     = load_execution_config(args.excel_path)
    sniffer_devs     = load_sniffer_config(args.excel_path)
    sniffer_params   = load_sniffer_parameters(args.excel_path)
    test_df          = load_test_config(args.excel_path)
    logger.info("Excel sheets loaded successfully")

    print_step("Filtering out tests marked as 'Skip'...")
    to_run_df = test_df[test_df["Skipped_Execution"].str.strip().str.lower() != "skip"]
    if args.tests_to_run:
        to_run_df = to_run_df[to_run_df["Test_Type"].isin(args.tests_to_run)]
        logger.info("Filtered test list to: %s", args.tests_to_run)

    if to_run_df.empty:
        print_error("No tests to run.")
        logger.error("No runnable test rows after filtering.")
        sys.exit(1)

    print_step("Starting DUT threads for each test...")
    all_threads = []
    for _, row in to_run_df.iterrows():
        raw_dut_str = row["dut"]
        dut_list = [d.strip() for d in str(raw_dut_str).split(",") if d.strip()]
        logger.info("Launching test: %s on DUT(s): %s", row["Test_Type"], ", ".join(dut_list))

        remote_list = []
        if "controller_ip" in row and pd.notna(row["controller_ip"]):
            remote_list = [r.strip() for r in str(row["controller_ip"]).split(",") if r.strip()]
            logger.info("Detected remote devices: %s", ", ".join(remote_list))

        barrier = threading.Barrier(len(dut_list) if dut_list else 1)

        for dut in dut_list:
            t = threading.Thread(
                target=per_dut_worker,
                args=(dut, remote_list, row.to_dict(), global_flags, sniffer_devs, sniffer_params, barrier)
            )
            t.start()
            all_threads.append(t)
            logger.info("Started thread for DUT: %s", dut)

    print_step("Waiting for all DUTs threads to complete...")
    for t in all_threads:
        t.join()

    print_info("All DUT threads completed. Check testExecOutput.log file.")
    logger.info("All test threads completed.")

if __name__ == "__main__":
    main()
