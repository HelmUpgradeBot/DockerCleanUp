import subprocess

def run_cmd(cmd):
    """Use Popen to run a subprocess command

    Parameters
    ----------
    cmd: List of strings.

    Returns
    -------
    result: Dictionary
    """
    result = {}

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    output = proc.communicate()

    result["returncode"] = proc.returncode
    result["output"] = output[0].decode(encoding="utf-8")
    result["err_msg"] = output[1].decode(encoding="utf-8")

    return result
