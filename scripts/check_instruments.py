r"""
check_instruments.py

Connects to the four bench instruments, confirms each one responds, and reads
one harmless value from each. It does NOT turn on the power supply output or
the electronic load input -- it only reads their current state.

Usage (from the repo folder):
    python scripts\check_instruments.py

If an instrument's address changes (e.g. plugged into a different USB port
on another PC), run find_instruments.py and update ADDRESSES below.
"""

import sys

try:
    import pyvisa
except ImportError:
    sys.exit("PyVISA is not installed. Run:  pip install pyvisa")


# Addresses found by find_instruments.py
ADDRESSES = {
    "scope":  "USB0::0x2A8D::0x17B6::MY65060131::INSTR",   # MSO-X 4024G oscilloscope
    "supply": "USB0::0x2A8D::0xCC04::CN65220167::INSTR",   # E36441A power supply
    "eload":  "USB0::0x2A8D::0x3802::MY61001504::INSTR",   # EL34143A electronic load
    "dmm":    "USB0::0x2A8D::0x1301::MY64026498::INSTR",   # 34461A multimeter
}

# What we expect to see in each *IDN? reply (to catch a wrong address)
EXPECTED_MODEL = {
    "scope":  "4024G",
    "supply": "E36441A",
    "eload":  "EL34143A",
    "dmm":    "34461A",
}

# Read-only checks for each instrument: (description, SCPI query).
# None of these change outputs. If a command isn't supported, the script
# reports it and moves on rather than crashing.
CHECKS = {
    "scope": [
        ("Timebase scale (s/div)", ":TIMebase:SCALe?"),
        ("Channel 1 V/div",        ":CHANnel1:SCALe?"),
    ],
    "supply": [
        ("Output state (0=off)",   "OUTPut?"),
        ("Voltage setpoint (V)",   "VOLTage?"),
        ("Current limit (A)",      "CURRent?"),
        ("Measured voltage (V)",   "MEASure:VOLTage?"),
    ],
    "eload": [
        ("Input state (0=off)",    "INPut?"),
        ("Measured voltage (V)",   "MEASure:VOLTage?"),
    ],
    "dmm": [
        ("DC voltage reading (V)", "MEASure:VOLTage:DC?"),
    ],
}

TIMEOUT_MS = 10000  # DMM auto-range measurements can take a moment


def check_one(rm, name, address):
    """Connect to one instrument and run its checks. Returns True if it responded."""
    print(f"\n--- {name.upper()}  ({address})")
    try:
        inst = rm.open_resource(address)
    except pyvisa.errors.VisaIOError as e:
        print(f"    FAILED to open: {e.abbreviation}")
        print("    -> Is it powered on, plugged in, and not in use by another program (e.g. BenchVue)?")
        return False

    inst.timeout = TIMEOUT_MS
    inst.read_termination = "\n"
    inst.write_termination = "\n"

    try:
        idn = inst.query("*IDN?").strip()
        print(f"    ID: {idn}")
        if EXPECTED_MODEL[name] not in idn:
            print(f"    WARNING: expected a {EXPECTED_MODEL[name]} at this address!")

        inst.write("*CLS")                 # clear old errors
        inst.query("*OPC?")                # wait until it's ready

        for label, cmd in CHECKS[name]:
            try:
                value = inst.query(cmd).strip()
                print(f"    {label:<24} {value}")
            except pyvisa.errors.VisaIOError as e:
                print(f"    {label:<24} (no reply to '{cmd}': {e.abbreviation})")
                inst.write("*CLS")

        # Report anything the instrument complained about
        err = inst.query("SYSTem:ERRor?").strip()
        if not err.startswith(("+0", "0")):
            print(f"    Instrument error queue: {err}")
        else:
            print("    No errors.")
        return True

    except pyvisa.errors.VisaIOError as e:
        print(f"    FAILED: opened but did not respond ({e.abbreviation})")
        return False
    finally:
        try:
            inst.write("SYSTem:LOCal")     # give the front panel back (ignored if unsupported)
        except Exception:                  # noqa: BLE001
            pass
        inst.close()


def main():
    rm = pyvisa.ResourceManager()
    results = {name: check_one(rm, name, addr) for name, addr in ADDRESSES.items()}
    rm.close()

    print("\n" + "=" * 50)
    for name, ok in results.items():
        print(f"  {name:<8} {'OK' if ok else 'NOT RESPONDING'}")
    print("=" * 50)

    if not all(results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
