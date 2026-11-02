"""Compatibility imports; implementations live in format-specific modules."""
from .parsing.discovery import (parse_discovery_line, parse_port_scan)
from .parsing.lookup import (parse_mac_vendor, parse_public_address, _text, _ip_text, _ip_version)
from .parsing.network import (cable_connected, parse_interfaces, parse_connection_name, _ipv4, parse_nmcli_device_ipv4, interface_network, parse_interface_ipv4, parse_default_gateway, parse_nmcli_ipv4)
from .parsing.ping import (read_ping_line, _copy_summary)
from .parsing.speed import (parse_speed_test)
from .parsing.trace import (parse_trace, _parse_trace_csv, _parse_trace_report, _trace_column, _trace_cell, _trace_loss)
from .parsing.wifi import (parse_saved_wifi, _nmcli_columns, parse_wifi_device, parse_wifi_list, parse_wifi_active, parse_interface_details, _lines, _band, _channel, _mhz, _bitrate, _duration, _size, _survey_noise, build_wifi_link)
