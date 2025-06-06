import pandas as pd
import logging

logger = logging.getLogger("utils.excel_loader")

def load_execution_config(excel_path: str) -> dict:
    """
    Reads the Execution_Config sheet and returns a dict:
      { Name.lower(): parsed(Value) }
    """
    df = pd.read_excel(excel_path, sheet_name="Execution_Config", engine="openpyxl")
    out = {}
    for _, row in df.iterrows():
        key = str(row["Name"]).strip().lower()
        raw = row["Value"]
        if isinstance(raw, str) and raw.lower() in ("true", "false"):
            out[key] = raw.lower() == "true"
        elif pd.isna(raw):
            out[key] = ""
        else:
            out[key] = raw
    return out

def load_sniffer_config(excel_path: str) -> list:
    """
    Reads Sniffer_Config sheet and returns list of dicts:
      [ {"name": suffix, "ip": ip, "user": user, "pass": pwd, "ifname": ifname}, ... ]
    """
    df = pd.read_excel(excel_path, sheet_name="Sniffer_Config", engine="openpyxl")
    out = []
    for col in df.columns:
        if str(col).strip().lower() in ("name",) or str(col).startswith("Unnamed"):
            continue
        ip = str(df.loc[df["Name"]=="ip", col].values[0]).strip()
        user = str(df.loc[df["Name"]=="username", col].values[0]).strip()
        pwd = str(df.loc[df["Name"]=="password", col].values[0]).strip()
        suffix = str(df.loc[df["Name"]=="suffix", col].values[0]).strip()
        ifname = str(df.loc[df["Name"]=="ifname", col].values[0]).strip()
        if ip and user and suffix and ifname:
            out.append({"name": suffix, "ip": ip, "user": user, "pass": pwd, "ifname": ifname})
    return out

def load_sniffer_parameters(excel_path: str) -> dict:
    """
    Reads Sniffer_Paramters sheet, returns dict keyed by channel name.
    """
    df = pd.read_excel(excel_path, sheet_name="Sniffer_Paramters", engine="openpyxl")
    out = {}
    for _, row in df.iterrows():
        ch_name = row["Name"]
        info = {
            "isFreq": row["isFreq"],
            "pFreq": row["pFreq"],
            "bw": row["bw"],
            "sFreq": row["sFreq"],
            "band": row["band"],
            "passive": row["passive"],
            "psc": row["psc"],
            "Ch_parameter": row["Ch_parameter"],
        }
        out[ch_name] = info
    return out

def load_test_config(excel_path: str):
    """
    Reads Test_Config sheet into a pandas DataFrame.
    """
    df = pd.read_excel(excel_path, sheet_name="Test_Config", engine="openpyxl")
    return df
