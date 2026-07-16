"""Regression tests for comms/IP address resolution (backend/app/sync.py, csv_export.py).

These are pure unit tests against fabricated `detail` dicts shaped like real
AlsoEnergy GET /Hardware/{id} responses — no live API, no network. The cases
mirror real devices found during manual investigation of client export bugs:
Elkor WattsOn Mark II / Mohave SMA inverters (TCP, no TCPPort key), SMA
WebBox/SCCom and Axis Camera (address hidden in driver.settings), and the
two real non-virtual GW/DA devices found stuck at UNKNOWN in production data.
"""
from app.csv_export import _channel_mode
from app.models import Hardware
from app.sync import _enrich_hardware, _le_decode_candidate


def _detail(address="0", port_mode="Unknown", com_type="Unknown", port_number=0,
            driver_name="Generic", driver_settings=None, gateway_id=None):
    return {
        "address": address,
        "portMode": port_mode,
        "gatewayId": gateway_id,
        "driver": {"name": driver_name, "settings": driver_settings or {}},
        "config": {"comType": com_type, "portNumber": port_number},
        "flags": ["IsEnabled"],
        "registerGroups": [],
    }


def _hw(id=1, function_code="PM", com_type="Unknown", port_number=0) -> Hardware:
    return Hardware(id=id, site_id=1, session_id="s", function_code=function_code,
                     com_type=com_type, port_number=port_number)


class TestConfirmedTopLevelAddress:
    """Bug #1 shape: real dotted IP at the top level, no TCPPort key in
    driver.settings (Elkor WattsOn Mark II @ South Burlington, Mohave SMA)."""

    def test_resolves_to_tcp_with_correct_ip(self):
        hw = _hw(function_code="PV")
        _enrich_hardware(hw, _detail(
            address="192.168.13.120", driver_name="SMA inverter via WebBox/SCCom",
            driver_settings={"UnitID": "3"},
        ))
        assert hw.ip_address == "192.168.13.120"
        assert hw.address_source == "confirmed"
        assert _channel_mode(hw) == "TCP"


class TestExistingRtuUnaffected:
    """Devices that already worked before Bug #1's fix must not regress."""

    def test_rtu_device_stays_rtu_with_no_ip(self):
        hw = _hw(function_code="PM", com_type="Rs485_2Wire", port_number=2)
        _enrich_hardware(hw, _detail(
            address="0", com_type="Rs485_2Wire", port_number=2,
            driver_name="Elkor WattsOn UPT", driver_settings={"baud": "9600", "portMode": "rs485"},
        ))
        assert hw.ip_address is None
        assert hw.address_source is None
        assert _channel_mode(hw) == "RTU"

    def test_confirmed_ip_wins_even_when_com_type_reads_as_serial(self):
        """Real device found in production data (University of Illinois, 'New
        Nexus 1272 Meter'): comType=Rs485_2Wire at the top level, but the
        detail response also carries a real dotted IP and a clean TCPPort/
        UnitID in driver.settings. This is a genuine Modbus TCP gateway
        serving multiple logical meters by unit ID (ABB Ultra 1500TL modules
        are the same pattern) — comType is a stale/generic label here and
        must NOT override a validated real address."""
        hw = _hw(function_code="PM", com_type="Rs485_2Wire", port_number=2)
        _enrich_hardware(hw, _detail(
            address="172.21.120.37", com_type="Rs485_2Wire", port_number=2,
            driver_name="Electro Industries Nexus 12XX (SS) Standard",
            driver_settings={"portMode": "rs485", "baud": "9600", "TCPPort": "502", "UnitID": "1"},
        ))
        assert hw.ip_address == "172.21.120.37"
        assert hw.address_source == "confirmed"
        assert _channel_mode(hw) == "TCP"


class TestVirtualDeviceUnaffected:
    def test_genuine_virtual_device_stays_unknown(self):
        hw = _hw(function_code="WS")
        _enrich_hardware(hw, _detail(driver_name="Virtual"))
        assert hw.is_virtual_device is True
        assert hw.ip_address is None
        assert _channel_mode(hw) == "UNKNOWN"

    def test_real_gw_device_never_marked_virtual(self):
        """Real device found in production cache: 'INDUSTRIAL COMPUTER -
        DATALOGGER', function_code=GW, all-zero/Unknown config. GW is
        excluded from the virtual heuristic by construction, so this must
        stay non-virtual and land in UNKNOWN for a human to triage."""
        hw = _hw(function_code="GW")
        _enrich_hardware(hw, _detail(driver_name="AlsoEnergy SCADA Site Controller"))
        assert hw.is_virtual_device is False
        assert hw.ip_address is None
        assert hw.address_source is None
        assert _channel_mode(hw) == "UNKNOWN"

    def test_real_da_device_never_marked_virtual(self):
        """Real device found in production cache: 'PT Dashboard Device',
        function_code=DA. Same reasoning as the GW case above."""
        hw = _hw(function_code="DA")
        _enrich_hardware(hw, _detail(driver_name="PTWDashboard"))
        assert hw.is_virtual_device is False
        assert _channel_mode(hw) == "UNKNOWN"


class TestIntegerEncodedAddress:
    """Byte-order is unconfirmed — must never silently guess."""

    def test_int_address_does_not_populate_ip(self):
        hw = _hw(function_code="PV")
        _enrich_hardware(hw, _detail(address=1846388928, driver_name="SMA inverter via WebBox/SCCom"))
        assert hw.ip_address is None
        assert hw.address_source == "int_decoded_le_unconfirmed"
        assert _channel_mode(hw) == "UNKNOWN"

    def test_le_decode_candidate_matches_confirmed_real_device(self):
        """Real Mohave device: config.address=1846388928 decodes little-endian
        to 192.168.13.110, which matches that device's independently-confirmed
        real IP. This is diagnostic-only — never assigned to ip_address."""
        assert _le_decode_candidate(1846388928) == "192.168.13.110"


class TestDriverSettingsFallback:
    """Some drivers don't expose a usable top-level address at all; the real
    IP is embedded in a driver-specific settings key instead."""

    def test_sma_webbox_serial_number_holds_real_ip(self):
        hw = _hw(id=26598, function_code="DA")
        _enrich_hardware(hw, _detail(
            driver_name="SMA WebBox/SCCom",
            driver_settings={"RegOffset": "0", "UnitID": "1", "SerialNumber": "172.16.5.110"},
        ))
        assert hw.ip_address == "172.16.5.110"
        assert hw.address_source == "driver_settings.SerialNumber"
        assert _channel_mode(hw) == "TCP"

    def test_axis_camera_access_url_holds_real_ip(self):
        # portMode must not be "Unknown" here, or this trips the virtual-device
        # heuristic (addr_zero + portMode=Unknown + comType=Unknown + port=0)
        # before the fallback ever runs — matches the real cached devices,
        # which have is_virtual_device=False.
        hw = _hw(id=33693, function_code="VC")
        _enrich_hardware(hw, _detail(
            port_mode="Ethernet", driver_name="Axis Camera",
            driver_settings={"accessURL": "https://166.164.242.83:8080"},
        ))
        assert hw.ip_address == "166.164.242.83"
        assert hw.address_source == "driver_settings.accessURL"
        assert hw.is_virtual_device is False
        assert _channel_mode(hw) == "TCP"

    def test_serial_number_that_is_an_actual_serial_number_is_not_misread_as_ip(self):
        """Negative case: proves the fallback validates IP shape rather than
        blindly trusting whatever string sits under a known key."""
        hw = _hw(id=88888, function_code="PM")
        _enrich_hardware(hw, _detail(driver_name="Some Meter", driver_settings={"SerialNumber": "SN-84921-X"}))
        assert hw.ip_address is None
        assert hw.address_source is None
        assert _channel_mode(hw) == "UNKNOWN"
