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
    # Create a dedicated logger for each DUT/test type
    logger = logging.getLogger(f"Worker.{test_params['Test_Type']}.{dut}")

    # Extract necessary info from input
    test_name     = test_params["Test_Type"]
    traffic_type  = test_params["TrafficType"]
    user          = test_params.get("User", "root")
    base_log_folder = global_flags.get("test_log_folder", "logs")

    # Create log directories for this DUT
    print_step(f"📁 [{dut}] Creating log folders")
    dut_root        = os.path.join(base_log_folder, test_name, dut.replace(".", "_"))
    dut_sniffer_dir = os.path.join(dut_root, "sniffer")
    dut_tcpdump_dir = os.path.join(dut_root, "tcpdump")
    dut_sysdiag_dir = os.path.join(dut_root, "sysdiag")
    dut_atten_dir   = os.path.join(dut_root, "attenuator")
    dut_common_dir  = os.path.join(dut_root, "common")
    for d in [dut_sniffer_dir, dut_tcpdump_dir, dut_sysdiag_dir, dut_atten_dir, dut_common_dir]:
        os.makedirs(d, exist_ok=True)

    # Prepare folders for remote devices
    remote_dirs = {}
    for remote in remote_list:
        rd = os.path.join(dut_root, "remote", remote.replace(".", "_"))
        os.makedirs(rd, exist_ok=True)
        remote_dirs[remote] = rd

    # DUT cleanup step
    print_step(f"🧼 [{dut}] Cleaning DUT logs and saved networks")
    logger.info(f"[{dut}] Performing log erase and Wi-Fi reset")
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

    # Clean Atlas firmware logs but DO NOT start logging yet
    wlan_firmware_utils.clean_firmware_logs(dut, user)

    # Start logging utilities (attenuator, sniffer, tcpdump, sysdiag)
    print_step(f"📡 [{dut}] Starting always-on logs (Attenuator, Sniffer, WlanFW, sysdiag, tcpdump)")

    # 🚨 Now start Attenuator setup
    try:
        if global_flags.get("enable_attenuator", False):
            start_attn = int(test_params.get("start_attn_1", 0))
            attenuator_utils.set_attenuation(start_attn)
            attn_was_set = True
            logger.info(f"[{dut}] Attenuator set to {start_attn} dB")
        else:
            attn_was_set = False
            logger.info(f"[{dut}] Attenuator disabled in global config")
    except Exception as e:
        attn_was_set = False
        logger.error(f"[{dut}] Attenuator setup failed: {e}", exc_info=True)

    # 🚨 Now start Sniffer setup
    sniffer_processes = []
    raw_ch_str = test_params.get("sniffer_channels", "")
    requested_channels = [ch.strip() for ch in raw_ch_str.split(",") if ch.strip()]
    if global_flags.get("enable_sniffer", False) and requested_channels:
        for i, ch in enumerate(requested_channels):
            if i < len(sniffer_devs):
                sn_info = sniffer_devs[i]
                freq_info = sniffer_params.get(ch, {})
                pid_file = sniffer_utils.start_sniffer(
                    sn_info["ip"], sn_info["user"], sn_info["ifname"], freq_info, dut_sniffer_dir
                )
                sniffer_processes.append((sn_info, pid_file))
                logger.info(f"[{dut}] Sniffer '{sn_info['name']}' started on channel {ch}")
            else:
                logger.error(f"[{dut}] No available sniffer for channel {ch}")
    else:
        logger.info(f"[{dut}] Sniffer disabled or no channels requested")

    # 🚨 Now start Sysdiagnose/logarchive setup
    print_step(f"📝 [{dut}] Starting Sysdiagnose log collection")
    sys_mode = str(global_flags.get("get_sysdiagnose", "")).lower()
    if sys_mode == "sysdiagnose":
        try:
            sysdiag_utils.run_sysdiagnose(dut, user, dut_sysdiag_dir)
            logger.info(f"[{dut}] Initial sysdiagnose complete")
        except Exception as e:
            logger.error(f"[{dut}] Initial sysdiagnose failed: {e}", exc_info=True)
    elif sys_mode == "logarchive":
        try:
            sysdiag_utils.run_logarchive(dut, user, dut_sysdiag_dir)
            logger.info(f"[{dut}] Initial logarchive complete")
        except Exception as e:
            logger.error(f"[{dut}] Initial logarchive failed: {e}", exc_info=True)

    # 🚨 Now start ATLAS WLAN firmware setup
    print_step(f"📝 [{dut}] Starting Atlas firmware log collection")
    wlan_firmware_utils.start_firmware_log(dut, user)
    logger.info(f"[{dut}] Firmware logging started")

    # 🚨 Now start TCPDump setup
    iface = test_params.get("dut_wifi_interface", "wlan0")
    if global_flags.get("enable_tcpdump", False):
        tcpdump_handle = tcpdump_utils.start_tcpdump(dut, user, iface, dut_tcpdump_dir)
        logger.info(f"[{dut}] TCPDump started")
    else:
        tcpdump_handle = None
        logger.info(f"[{dut}] TCPDump disabled in config")
    
    # Begin test execution
    print_step(f"🚀 [{dut}] Running test logic for traffic type: {traffic_type}")
    test_exception = None
    try:
        mod_name = traffic_type.lower()
        test_module = __import__(f"tests.{mod_name}", fromlist=["run_test"])
        test_module.run_test(dut, test_params, remote_list, global_flags, barrier)
    except Exception as e:
        test_exception = e
        logger.error(f"[{dut}] Exception during test: {e}", exc_info=True)

    # Cleanup logging processes
    print_step(f"🧹 [{dut}] Stopping logs and collecting results")

    # Stop tcpdump
    if tcpdump_handle:
        try:
            tcpdump_utils.stop_tcpdump(dut, user, tcpdump_handle)
            logger.info(f"[{dut}] TCPDump stopped")
        except Exception as e:
            logger.error(f"[{dut}] TCPDump stop error: {e}", exc_info=True)

    # Stop sniffers
    for sn_info, pid in sniffer_processes:
        try:
            sniffer_utils.stop_sniffer(sn_info["ip"], sn_info["user"], pid)
            logger.info(f"[{dut}] Sniffer '{sn_info['name']}' stopped")
        except Exception as e:
            logger.error(f"[{dut}] Sniffer stop error: {e}", exc_info=True)

    # Final sysdiagnose/logarchive
    if sys_mode == "sysdiagnose":
        try:
            sysdiag_utils.run_sysdiagnose(dut, user, dut_sysdiag_dir)
            logger.info(f"[{dut}] Final sysdiagnose complete")
        except Exception as e:
            logger.error(f"[{dut}] Final sysdiagnose failed: {e}", exc_info=True)
    elif sys_mode == "logarchive":
        try:
            sysdiag_utils.run_logarchive(dut, user, dut_sysdiag_dir)
            logger.info(f"[{dut}] Final logarchive complete")
        except Exception as e:
            logger.error(f"[{dut}] Final logarchive failed: {e}", exc_info=True)

    # Stop firmware logging and download logs
    wlan_firmware_utils.stop_and_pull_firmware_log(dut, user, dut_common_dir)
    logger.info(f"[{dut}] Firmware logs downloaded")

    # Reset attenuator
    if attn_was_set and global_flags.get("enable_attenuator", False):
        try:
            attenuator_utils.set_attenuation(0)
            logger.info(f"[{dut}] Attenuator reset to 0 dB")
        except Exception as e:
            logger.error(f"[{dut}] Attenuator reset error: {e}", exc_info=True)

    # Archive test logs
    try:
        tar_path = f"{dut_root}.tar.gz"
        subprocess.call(f"tar czf {tar_path} -C {base_log_folder} {test_name}/{dut.replace('.', '_')}", shell=True)
        logger.info(f"[{dut}] Logs archived to {tar_path}")
    except Exception as e:
        logger.error(f"[{dut}] Archive failed: {e}", exc_info=True)

    # Final result
    if test_exception:
        logger.error(f"[{dut}] ❌ Test FAILED")
        print_step(f"[{dut}] ❌ Test FAILED")
    else:
        logger.info(f"[{dut}] ✅ Test SUCCESSFUL")
        print_step(f"[{dut}] ✅ Test SUCCESSFUL")


# Main function that launches CLI → reads Excel → starts threads
def main():
    print_step("Parsing CLI arguments")
    logger = setup_logging(log_file="testExecOutput.log", level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument("--excel_path", "-e", required=True, help="Path to Configurations_updated.xlsx")
    parser.add_argument("--tests_to_run", "-t", nargs="*", default=None,
                        help="Optional list of Test_Type names to run")
    args = parser.parse_args()

    print_info("InfraFramework starting...")
    logger.info("Logger setup complete")

    print_step("Reading Excel configuration")
    global_flags     = load_execution_config(args.excel_path)
    sniffer_devs     = load_sniffer_config(args.excel_path)
    sniffer_params   = load_sniffer_parameters(args.excel_path)
    test_df          = load_test_config(args.excel_path)

    print_step("Filtering valid tests to run...")
    to_run_df = test_df[test_df["Skipped_Execution"].str.strip().str.lower() != "skip"]
    if args.tests_to_run:
        to_run_df = to_run_df[to_run_df["Test_Type"].isin(args.tests_to_run)]
        logger.info("User-specified test types: %s", args.tests_to_run)

    if to_run_df.empty:
        print_error("No tests to run.")
        logger.error("Nothing to execute after filtering.")
        sys.exit(1)

    # Threading for each DUT/test combo
    print_step("Launching DUT threads...")
    all_threads = []
    for _, row in to_run_df.iterrows():
        dut_list = [d.strip() for d in str(row["dut"]).split(",") if d.strip()]
        remote_list = [r.strip() for r in str(row.get("controller_ip", "")).split(",") if r.strip()]

        barrier = threading.Barrier(len(dut_list))
        for dut in dut_list:
            t = threading.Thread(
                target=per_dut_worker,
                args=(dut, remote_list, row.to_dict(), global_flags, sniffer_devs, sniffer_params, barrier)
            )
            t.start()
            all_threads.append(t)

    # Wait for all DUT threads to finish
    print_step("Waiting for all DUT threads to complete...")
    for t in all_threads:
        t.join()

    print_info("✅ All test threads complete. See logs for details.")

if __name__ == "__main__":
    main()
