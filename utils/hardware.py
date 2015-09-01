import subprocess


def lsblk(columns=None):
    """
    lsblk wrapper.
    Args:
        columns (list):
            List of dictionaries with keys from `columns` for every device.

    """
    columns = columns or ["NAME", "UUID", "LABEL", "SIZE", "TYPE"]

    def map_columns(line):
        device_info = {}
        for entry in line.split():
            key, value = entry.split('=')
            value = value.strip('"')
            device_info[key] = value or None
        return device_info

    output = subprocess.check_output([
        "lsblk",
        "--pairs",  # Produce output in the form of key="value" pairs.
        "--noheadings",  # Do not print a header line.
        "--output", ",".join(columns)]  # Columns to print. See 'lsblk --help'.
    ).decode("utf-8")
    lines = map(map_columns, output.split('\n'))
    # filter out empty lines
    lines = filter(lambda x: bool(x), lines)
    return list(lines)
print(lsblk())
