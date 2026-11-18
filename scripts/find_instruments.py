"""
find_instruments.py

Scans for all VISA instruments connected to this computer, tries to talk to
each one with the standard SCPI identify command (*IDN?), and prints a summary.

Usage:
    python find_instruments.py            # uses the default VISA (e.g. Keysight IO Libraries)
    python find_instruments.py --py       # uses the pure-Python pyvisa-py backend
    python find_instruments.py --serial   # also probe serial (COM/ASRL) ports

Requires:  pip install pyvisa      (and pyvisa-py if you use --py)
"""

import argparse
import sys

try:
    import pyvisa
except ImportError:
    sys.exit("PyVISA is not installed. Run:  pip install pyvisa")


# Read terminations to try, in order. Most Keysight instruments use '\n'.
TERMINATIONS = ["\n", "\r\n", "\r"]
TIMEOUT_MS = 3000


def open_resource_manager(use_py_backend: bool):
    """Create the ResourceManager, with a helpful message if VISA is missing."""
    try:
        if use_py_backend:
            return pyvisa.ResourceManager("@py")
        return pyvisa.ResourceManager()
    except (OSError, ValueError) as e:
        sys.exit(
            f"Could not load a VISA library: {e}\n"
            "-> Install Keysight IO Libraries Suite, or run with --py "
            "after 'pip install pyvisa-py'.\n"
            "-> Run 'pyvisa-info' for details."
        )


def try_identify(rm, address: str):
    """
    Open one instrument and try *IDN? with several termination settings.
    Returns (success: bool, message: str).
    """
    try:
        inst = rm.open_resource(address)
    except pyvisa.errors.VisaIOError as e:
        return False, f"could not open ({e.abbreviation})"
    except Exception as e:  # noqa: BLE001 - want to report anything
        return False, f"could not open ({e})"

    inst.timeout = TIMEOUT_MS
    last_error = "no response"

    try:
        for term in TERMINATIONS:
            inst.read_termination = term
            inst.write_termination = "\n"
            try:
                # Clear any stale data/errors left over from earlier sessions
                try:
                    inst.clear()
                except Exception:  # noqa: BLE001 - not all interfaces support clear
                    pass
                reply = inst.query("*IDN?").strip()
                if reply:
                    return True, reply
            except pyvisa.errors.VisaIOError as e:
                last_error = e.abbreviation  # e.g. VI_ERROR_TMO = timeout
            except Exception as e:  # noqa: BLE001
                last_error = str(e)
        return False, f"opened, but no reply to *IDN? ({last_error})"
    finally:
        try:
            inst.close()
        except Exception:  # noqa: BLE001
            pass


def main():
    parser = argparse.ArgumentParser(description="Find and identify VISA instruments.")
    parser.add_argument("--py", action="store_true", help="use the pyvisa-py backend")
    parser.add_argument("--serial", action="store_true",
                        help="also probe serial/COM ports (ASRL); can be slow")
    args = parser.parse_args()

    rm = open_resource_manager(args.py)
    print(f"VISA library: {rm.visalib}\n")

    # '?*::INSTR' finds instruments; '?*' alone would also list SOCKET/other resources
    try:
        resources = rm.list_resources("?*")
    except pyvisa.errors.VisaIOError:
        resources = ()

    if not args.serial:
        skipped = [r for r in resources if r.upper().startswith("ASRL")]
        resources = [r for r in resources if not r.upper().startswith("ASRL")]
        if skipped:
            print(f"(Skipping {len(skipped)} serial port(s); use --serial to probe them.)\n")

    if not resources:
        print("No instruments found.")
        print("Checklist:")
        print("  - Is the instrument powered on and the cable connected?")
        print("  - Does Keysight Connection Expert see it? If not, PyVISA won't either.")
        print("  - LAN instruments: the computer must be on the same subnet. LAN devices")
        print("    often must be added manually in Connection Expert to be listed.")
        rm.close()
        return

    print(f"Found {len(resources)} resource(s). Probing each one...\n")
    results = []
    for addr in resources:
        print(f"  {addr}")
        ok, msg = try_identify(rm, addr)
        print(f"     -> {'OK: ' if ok else 'FAILED: '}{msg}\n")
        results.append((addr, ok, msg))

    # Summary table
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for addr, ok, msg in results:
        if ok:
            parts = [p.strip() for p in msg.split(",")]
            maker = parts[0] if len(parts) > 0 else "?"
            model = parts[1] if len(parts) > 1 else "?"
            print(f"[OK]   {maker} {model}")
            print(f"       address: {addr}")
        else:
            print(f"[FAIL] {addr}")
            print(f"       {msg}")
    print()
    print("Use an OK address in your own scripts, e.g.:")
    print('    inst = rm.open_resource("<address>")')

    rm.close()


if __name__ == "__main__":
    main()
