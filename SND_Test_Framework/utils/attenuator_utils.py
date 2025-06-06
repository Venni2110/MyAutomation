import logging
import subprocess
import time

logger = logging.getLogger("utils.attenuator_utils")

def set_attenuation(level_db: int):
    """
    Sets the attenuator to the specified dB level.
    """
    cmd = f"attenuator_cli set {level_db}"
    try:
        ret = subprocess.call(cmd, shell=True)
        if ret == 0:
            logger.info(f"Attenuator set to {level_db} dB")
        else:
            logger.error(f"Attenuator CLI returned {ret} for level {level_db}")
    except Exception as e:
        logger.error(f"Exception in set_attenuation: {e}", exc_info=True)

def ramp_attenuation(start_db: int, end_db: int, step_db: int, delay_s: int):
    """
    Gradually ramps attenuator from start_db to end_db in steps of step_db.
    """
    current = start_db
    if step_db == 0:
        set_attenuation(current)
        return

    ascending = step_db > 0
    while (ascending and current <= end_db) or (not ascending and current >= end_db):
        set_attenuation(current)
        time.sleep(delay_s)
        current += step_db
    logger.info(f"Attenuation ramp completed: {start_db} → {end_db} dB")
