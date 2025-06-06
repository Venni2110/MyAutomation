import argparse
import sys
import threading
import logging
import os
import subprocess
import pandas as pd

from logger_config import setup_logging
from colored_print import print_info, print_error, print_step
from utils.excel_loader import (
    load_execution_config,
    load_sniffer_config,
    load_sniffer_parameters,
    load_test_config
)
from utils import common_utils, ssh_utils, sniffer_utils, tcpdump_utils, sysdiag_utils, attenuator_utils

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

    # 1) Prepare workspace directories
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

    logger.info(f"Workspace created at {dut_root}")

    # 1.1) Remote cleanup on DUT
    common_utils.erase_logs(dut, user)
    common_utils.clear_saved_networks(dut, user)
    common_utils.cleanup_scan_cache(dut, user)
    common_utils.wifi_off(dut, user)
    import time; time.sleep(1)
    common_utils.wifi_on(dut, user)
    logger.info("DUT cleanup done.")

    # -------------------------------------------------------------------------
    # 2) START “always-on” logging
    # -------------------------------------------------------------------------
    # 2.1) Attenuator
    try:
        if global_flags.get("enable_attenuator", False):
            start_attn = int(test_params.get("start_attn_1", 0))
            attenuator_utils.set_attenuation(start_attn)
            attn_was_set = True
            logger.info(f"Attenuator set to {start_attn} dB (start).")
        else:
            attn_was_set = False
            logger.info("Skipping attenuator (global flag).")
    except Exception as e:
        attn_was_set = False
        logger.error(f"Attenuator setup exception: {e}", exc_info=True)

    # 2.2) Sniffer(s)
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
                logger.info(f"Started sniffer '{sn_info['name']}' on channel {ch}")
            else:
                logger.error(f"No free sniffer device for channel {ch}")
    else:
        logger.info("Skipping sniffer (global flag or no channels).")

    # 2.3) TCPDUMP on DUT
    if global_flags.get("enable_tcpdump", False):
        iface = test_params.get("dut_wifi_interface", "wlan0")
        tcpdump_handle = tcpdump_utils.start_tcpdump(dut, user, iface, dut_tcpdump_dir)
        logger.info("Started tcpdump on DUT.")
    else:
        tcpdump_handle = None
        logger.info("Skipping tcpdump (global flag).")

    # 2.4) Initial sysdiag/logarchive
    sys_mode = str(global_flags.get("get_sysdiagnose", "")).lower()
    if sys_mode == "sysdiagnose":
        try:
            sysdiag_utils.run_sysdiagnose(dut, user, dut_sysdiag_dir)
            logger.info("Ran initial sysdiagnose.")
        except Exception as e:
            logger.error(f"Initial sysdiagnose exception: {e}", exc_info=True)
    elif sys_mode == "logarchive":
        try:
            sysdiag_utils.run_logarchive(dut, user, dut_sysdiag_dir)
            logger.info("Ran initial logarchive.")
        except Exception as e:
            logger.error(f"Initial logarchive exception: {e}", exc_info=True)
    else:
        logger.info("Skipping initial sysdiag/logarchive (global flag).")

    # 2.5) Remote servers (e.g. iperf3)
    remote_handles = []
    if traffic_type.upper() == "TCP" and remote_list:
        rc, out, err = ssh_utils.ssh_execute(
            remote_list[0], user, "iperf3 -s -D", remote_dirs[remote_list[0]]
        )
        if rc == 0:
            remote_handles.append(("iperf3", remote_list[0]))
            logger.info(f"Started iperf3 server on remote {remote_list[0]}")
        else:
            logger.error(f"Failed to start iperf3 on remote {remote_list[0]}: {err}")

    # --------------------------------------------------------------
    # 3) TEST LOGIC (try/except so finally always runs)
    # --------------------------------------------------------------
    test_exception = None
    try:
        # A) JOIN
        if traffic_type.upper() == "JOIN":
            from tests.join import run_test as run_join
            run_join(dut, test_params, remote_list, global_flags, barrier)
        # B) AUTOJOIN
        elif traffic_type.upper() == "AUTOJOIN":
            from tests.autojoin import run_test as run_autojoin
            run_autojoin(dut, test_params, remote_list, global_flags, barrier)
        # C) IDLE
        elif traffic_type.upper() == "IDLE":
            from tests.idle import run_test as run_idle
            run_idle(dut, test_params, remote_list, global_flags, barrier)
        # D) TCP
        elif traffic_type.upper() == "TCP":
            from tests.tcp import run_test as run_tcp
            run_tcp(dut, test_params, remote_list, global_flags, barrier)
        # E) UDP
        elif traffic_type.upper() == "UDP":
            from tests.udp import run_test as run_udp
            run_udp(dut, test_params, remote_list, global_flags, barrier)
        # F) FACETIME
        elif traffic_type.upper() == "FACETIME":
            from tests.facetime import run_test as run_ft
            run_ft(dut, test_params, remote_list, global_flags, barrier)
        # G) RVR
        elif traffic_type.upper() == "RVR":
            from tests.rvr import run_test as run_rvr
            run_rvr(dut, test_params, remote_list, global_flags, barrier)
        else:
            logger.error(f"Unsupported TrafficType '{traffic_type}' → skipping logic.")
    except Exception as e:
        test_exception = e
        logger.error(f"Exception in test logic: {e}", exc_info=True)

    # --------------------------------------------------------------
    # 4) FINALLY → STOP & COLLECT LOGS, RESET HARDWARE
    # --------------------------------------------------------------
    # 4.1) Stop tcpdump on DUT
    if tcpdump_handle:
        try:
            tcpdump_utils.stop_tcpdump(dut, user, tcpdump_handle)
            logger.info("Stopped tcpdump.")
        except Exception as e:
            logger.error(f"Exception stopping tcpdump: {e}", exc_info=True)

    # 4.2) Stop sniffer(s)
    for sn_info, pid in sniffer_processes:
        try:
            sniffer_utils.stop_sniffer(sn_info["ip"], sn_info["user"], pid)
            logger.info(f"Stopped sniffer '{sn_info['name']}'.")
        except Exception as e:
            logger.error(f"Exception stopping sniffer '{sn_info['name']}': {e}", exc_info=True)

    # 4.3) Final sysdiag/logarchive
    if sys_mode == "sysdiagnose":
        try:
            sysdiag_utils.run_sysdiagnose(dut, user, dut_sysdiag_dir)
            logger.info("Ran final sysdiagnose.")
        except Exception as e:
            logger.error(f"Exception final sysdiagnose: {e}", exc_info=True)
    elif sys_mode == "logarchive":
        try:
            sysdiag_utils.run_logarchive(dut, user, dut_sysdiag_dir)
            logger.info("Ran final logarchive.")
        except Exception as e:
            logger.error(f"Exception final logarchive: {e}", exc_info=True)

    # 4.4) Reset attenuator if we set it earlier
    if attn_was_set and global_flags.get("enable_attenuator", False):
        try:
            attenuator_utils.set_attenuation(0)
            logger.info("Reset attenuator to 0 dB.")
        except Exception as e:
            logger.error(f"Exception resetting attenuator: {e}", exc_info=True)

    # 4.5) Stop remote servers we started
    for handle, remote in remote_handles:
        if handle == "iperf3":
            try:
                ssh_utils.ssh_execute(remote, user, "pkill iperf3", remote_dirs[remote])
                logger.info(f"Stopped iperf3 server on remote {remote}.")
            except Exception as e:
                logger.error(f"Exception stopping iperf3 on remote {remote}: {e}", exc_info=True)

    # 4.6) Archive the entire dut_root folder as a .tar.gz
    try:
        tar_path = f"{dut_root}.tar.gz"
        subprocess.call(f"tar czf {tar_path} -C {base_log_folder} {test_name}/{dut.replace('.', '_')}", shell=True)
        logger.info(f"Archived logs to {tar_path}")
    except Exception as e:
        logger.error(f"Exception archiving logs: {e}", exc_info=True)

    if test_exception:
        logger.error(f"Test FAILED with exception: {test_exception}")
    else:
        logger.info("Test completed SUCCESSFULLY.")

def main():
    # 1) Parse CLI
    print_step("Parsing command-line arguments...")
    logger = setup_logging(log_file="testExecOutput.log", level=logging.INFO)
    logger.info("Started InfraFramework CLI parsing")
    parser = argparse.ArgumentParser()
    parser.add_argument("--excel_path", "-e", required=True, help="Path to Configurations_updated.xlsx")
    parser.add_argument("--tests_to_run", "-t", nargs="*", default=None,
                        help="Optional list of Test_Type names to run")
    args = parser.parse_args()

    # 2) Initialize logging
    print_info("InfraFramework starting...")
    logger.info("Logger initialized and output redirected to testExecOutput.log")

    # 3) Load all Excel sheets
    print_step("Loading execution configuration and test definitions from Excel...")
    logger.info("Loading Execution_Config, Sniffer_Config, Sniffer_Paramters, and Test_Config from %s", args.excel_path)
    global_flags     = load_execution_config(args.excel_path)
    sniffer_devs     = load_sniffer_config(args.excel_path)
    sniffer_params   = load_sniffer_parameters(args.excel_path)
    test_df          = load_test_config(args.excel_path)
    logger.info("Excel configuration loaded successfully")

    # 4) Filter out Skipped_Execution == Skip
    print_step("Filtering out tests marked as 'Skip'...")
    to_run_df = test_df[test_df["Skipped_Execution"].str.strip().str.lower() != "skip"]
    if args.tests_to_run:
        to_run_df = to_run_df[to_run_df["Test_Type"].isin(args.tests_to_run)]
        logger.info("Filtered test list based on command-line --tests_to_run argument")
    else:
        logger.info("Running all unskipped tests from Excel")

    if to_run_df.empty:
        print_error("No tests to run.")
        logger.error("Test plan is empty after filtering – exiting.")
        sys.exit(1)

    # 5) Spawn a thread per DUT
    print_step("Starting DUT threads for each test...")
    all_threads = []
    for _, row in to_run_df.iterrows():
        raw_dut_str = row["dut"]
        dut_list = [d.strip() for d in str(raw_dut_str).split(",") if d.strip()]
        logger.info("Starting test: %s on DUT(s): %s", row["Test_Type"], ", ".join(dut_list))

        remote_list = []
        if "controller_ip" in row and pd.notna(row["controller_ip"]):
            remote_list = [r.strip() for r in str(row["controller_ip"]).split(",") if r.strip()]
            logger.info("Remote devices found for this test: %s", ", ".join(remote_list))

        # Barrier to synchronize parallel DUTs
        barrier = threading.Barrier(len(dut_list) if dut_list else 1)

        for dut in dut_list:
            t = threading.Thread(
                target=per_dut_worker,
                args=(dut, remote_list, row.to_dict(), global_flags, sniffer_devs, sniffer_params, barrier)
            )
            t.start()
            all_threads.append(t)
            logger.info("Launched thread for DUT %s", dut)

    # 6) Wait for all threads
    print_step("Waiting for all DUTs threads to complete...")
    for t in all_threads:
        t.join()

    print_info("All DUT threads completed. Check testExecOutput.log file.")
    logger.info("All test threads finished execution.")

if __name__ == "__main__":
    main()
