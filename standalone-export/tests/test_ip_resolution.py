"""Regression tests for comms/IP address resolution (standalone-export/export.py).

Mirrors backend/tests/test_ip_resolution.py — same cases, adapted to this
script's own HardwareData/functions. Pure unit tests against fabricated
`detail` dicts shaped like real AlsoEnergy GET /Hardware/{id} responses —
no live API, no network.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from export import HardwareData, _channel_mode, _enrich_hardware, _le_decode_candidate  # noqa: E402


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


def _hw(id=1, function_code="PM", com_type="Unknown", port_number=0, baud_rate=0) -> HardwareData:
    return HardwareData(id=id, site_id=1, function_code=function_code,
                         com_type=com_type, port_number=port_number, baud_rate=baud_rate)


class TestConfirmedTopLevelAddress:
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
        UnitID in driver.settings — a genuine Modbus TCP gateway serving
        multiple logical meters by unit ID (ABB Ultra 1500TL modules are the
        same pattern). comType must NOT override a validated real address."""
        hw = _hw(function_code="PM", com_type="Rs485_2Wire", port_number=2)
        _enrich_hardware(hw, _detail(
            address="172.21.120.37", com_type="Rs485_2Wire", port_number=2,
            driver_name="Electro Industries Nexus 12XX (SS) Standard",
            driver_settings={"portMode": "rs485", "baud": "9600", "TCPPort": "502", "UnitID": "1"},
        ))
        assert hw.ip_address == "172.21.120.37"
        assert hw.address_source == "confirmed"
        assert _channel_mode(hw) == "TCP"

    def test_comtype_unknown_but_real_serial_config_resolves_rtu(self):
        """Real device: South Burlington Solar, 'Solectria 36kW TL V2 Inverter -
        11'. AlsoEnergy's own UI shows Port=2/Baud=9600/Address=11 (it's
        RS-485-chained off the site's Elkor meter), but config.comType is the
        generic 'Unknown' label rather than an Rs485_* value. Confirmed 557
        similar cases (mostly RS-485 string inverters: Solectria, Chint,
        Huawei, SunGrow, Delta, SolarEdge) across production before trusting
        this signal."""
        hw = _hw(function_code="PV", com_type="Unknown", port_number=2, baud_rate=9600)
        hw.address = "11"
        _enrich_hardware(hw, _detail(driver_name="Solectria TL String Inverter"))
        assert hw.ip_address is None
        assert _channel_mode(hw) == "RTU"

    def test_comtype_unknown_with_zero_baud_stays_unknown(self):
        """Real device: University of Illinois 'Hukseflux Heater Controller'
        (ADAM 4055). port_number=2 (nonzero) but baud_rate=0 — genuinely no
        serial config, must NOT be swept up by the port+baud RTU rule above
        (verified: every confirmed-unresolved GW/DA/WS device in production
        has baud_rate=0)."""
        hw = _hw(id=44904, function_code="DA", com_type="Unknown", port_number=2, baud_rate=0)
        _enrich_hardware(hw, _detail(driver_name="ADAM 4055"))
        assert hw.ip_address is None
        assert _channel_mode(hw) == "UNKNOWN"


class TestVirtualDeviceUnaffected:
    def test_genuine_virtual_device_stays_unknown(self):
        hw = _hw(function_code="WS")
        _enrich_hardware(hw, _detail(driver_name="Virtual"))
        assert hw.is_virtual_device is True
        assert hw.ip_address is None
        assert _channel_mode(hw) == "UNKNOWN"

    def test_real_gw_device_never_marked_virtual(self):
        hw = _hw(function_code="GW")
        _enrich_hardware(hw, _detail(driver_name="AlsoEnergy SCADA Site Controller"))
        assert hw.is_virtual_device is False
        assert hw.ip_address is None
        assert hw.address_source is None
        assert _channel_mode(hw) == "UNKNOWN"

    def test_real_da_device_never_marked_virtual(self):
        hw = _hw(function_code="DA")
        _enrich_hardware(hw, _detail(driver_name="PTWDashboard"))
        assert hw.is_virtual_device is False
        assert _channel_mode(hw) == "UNKNOWN"


class TestIntegerEncodedAddress:
    def test_int_address_does_not_populate_ip(self):
        hw = _hw(function_code="PV")
        _enrich_hardware(hw, _detail(address=1846388928, driver_name="SMA inverter via WebBox/SCCom"))
        assert hw.ip_address is None
        assert hw.address_source == "int_decoded_le_unconfirmed"
        assert _channel_mode(hw) == "UNKNOWN"

    def test_le_decode_candidate_matches_confirmed_real_device(self):
        assert _le_decode_candidate(1846388928) == "192.168.13.110"


class TestDriverSettingsFallback:
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
        hw = _hw(id=88888, function_code="PM")
        _enrich_hardware(hw, _detail(driver_name="Some Meter", driver_settings={"SerialNumber": "SN-84921-X"}))
        assert hw.ip_address is None
        assert hw.address_source is None
        assert _channel_mode(hw) == "UNKNOWN"
