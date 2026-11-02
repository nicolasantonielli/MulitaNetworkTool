"""Etiquetas de hechos y formato localizado únicamente para presentación."""
from mulita.presentation.i18n import Translator
import re

WIFI_LABELS = {'ssid': 'factSsid',
 'bssid': 'factBssid',
 'security': 'factSecurity',
 'mode': 'factMode',
 'interface': 'factIface',
 'mac': 'factMac',
 'address': 'factIp',
 'netmask': 'factMask',
 'gateway': 'factGateway',
 'dns': 'factDns',
 'ipv6': 'factIpv6',
 'band': 'factBand',
 'channel': 'factChannel',
 'frequency': 'factFreq',
 'width': 'factWidth',
 'center': 'factCenter',
 'signal': 'factSignal',
 'noise': 'factNoise',
 'snr': 'factSnr',
 'rate_rx': 'factRateRx',
 'rate_tx': 'factRateTx',
 'mcs_rx': 'factMcsRx',
 'mcs_tx': 'factMcsTx',
 'tx_power': 'factTxPower',
 'uptime': 'factUptime',
 'beacon': 'factBeacon',
 'dtim': 'factDtim',
 'retries': 'factRetries',
 'failed': 'factFailed',
 'beacon_loss': 'factBeaconLoss',
 'rx': 'factRx',
 'tx': 'factTx'}
PUBLIC_LABELS = {'ip': 'pubIp',
 'version': 'pubVersion',
 'asn': 'pubAsn',
 'organization': 'pubOrg',
 'isp': 'pubIsp',
 'domain': 'pubDomain',
 'country': 'pubCountry',
 'region': 'pubRegion',
 'city': 'pubCity',
 'coordinates': 'pubCoords',
 'timezone': 'pubZone'}
MODES = {'managed': 'wifiModeInfra',
 'AP': 'wifiModeAp',
 'monitor': 'wifiModeMonitor',
 'mesh point': 'wifiModeMesh',
 'IBSS': 'wifiModeAdhoc'}


def wifi_facts(link, translator: Translator):
    rows = []
    for key, value in link.facts():
        if key == 'mode':
            value = translator.tr(MODES[value]) if value in MODES else value
        elif key in ('mcs_rx', 'mcs_tx'):
            value = value.replace('short GI', translator.tr('wifiShortGi')).replace('long GI', translator.tr('wifiLongGi'))
        elif key == 'signal':
            value = re.sub(r' · avg (-?\d+) dBm', lambda match: translator.tr('signalAvg', value=match[1]), value)
        rows.append((translator.tr(WIFI_LABELS[key]), value))
    return rows


def public_facts(info, translator: Translator):
    return [(translator.tr(PUBLIC_LABELS[key]), value) for key, value in info.facts()]
