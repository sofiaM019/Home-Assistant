"""Tests for the APCUPSd component."""
from collections import OrderedDict
from typing import Final

MOCK_STATUS: Final = OrderedDict(
    [
        ("APC", "001,038,0985"),
        ("DATE", "1970-01-01 00:00:00 0000"),
        ("VERSION", "3.14.14 (31 May 2016) unknown"),
        ("CABLE", "USB Cable"),
        ("DRIVER", "USB UPS Driver"),
        ("UPSMODE", "Stand Alone"),
        ("MODEL", "Back-UPS ES 600"),
        ("STATUS", "ONLINE"),
        ("LINEV", "124.0 Volts"),
        ("LOADPCT", "14.0 Percent"),
        ("BCHARGE", "100.0 Percent"),
        ("TIMELEFT", "51.0 Minutes"),
        ("MBATTCHG", "5 Percent"),
        ("MINTIMEL", "3 Minutes"),
        ("MAXTIME", "0 Seconds"),
        ("SENSE", "Medium"),
        ("LOTRANS", "92.0 Volts"),
        ("HITRANS", "139.0 Volts"),
        ("ALARMDEL", "30 Seconds"),
        ("BATTV", "13.7 Volts"),
        ("LASTXFER", "Automatic or explicit self test"),
        ("NUMXFERS", "1"),
        ("XONBATT", "1970-01-01 00:00:00 0000"),
        ("TONBATT", "0 Seconds"),
        ("CUMONBATT", "8 Seconds"),
        ("XOFFBATT", "1970-01-01 00:00:00 0000"),
        ("LASTSTEST", "1970-01-01 00:00:00 0000"),
        ("SELFTEST", "NO"),
        ("STATFLAG", "0x05000008"),
        ("SERIALNO", "XXXXXXXXXXXX"),
        ("BATTDATE", "1970-01-01"),
        ("NOMINV", "120 Volts"),
        ("NOMBATTV", "12.0 Volts"),
        ("NOMPOWER", "330 Watts"),
        ("FIRMWARE", "928.a8 .D USB FW:a8"),
        ("END APC", "1970-01-01 00:00:00 0000"),
    ]
)

# Minimal status taken from http://www.apcupsd.org/manual/manual.html.
MOCK_MINIMAL_STATUS: Final = OrderedDict(
    [
        ("APC", "001,012,0319"),
        ("DATE", "1970-01-01 00:00:00 0000"),
        ("RELEASE", "3.8.5"),
        ("UPSNAME", "UPS_IDEN"),
        ("CABLE", "APC Cable 940-0128A"),
        ("MODEL", "BackUPS"),
        ("UPSMODE", "Stand Alone"),
        ("STARTTIME", "1970-01-01 00:00:00 0000"),
        ("LINEFAIL", "OK"),
        ("BATTSTAT", "OK"),
        ("STATFLAG", "0x008"),
        ("END APC", "1970-01-01 00:00:00 0000"),
    ]
)
