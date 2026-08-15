import socket
import unittest
from collections import namedtuple
from unittest import mock

from bin import mediamtx_systeminfo


Address = namedtuple("Address", "family address")
NetIo = namedtuple("NetIo", "bytes_recv bytes_sent")


class FakePsutil:
    def __init__(self, addresses):
        self._addresses = addresses

    def net_if_addrs(self):
        return self._addresses


class FakeNetIoPsutil:
    @staticmethod
    def net_io_counters(pernic=False):
        assert pernic
        return {
            "eth0": NetIo(100, 200),
            "docker0": NetIo(1000, 2000),
        }


class SystemIdentityTests(unittest.TestCase):
    def assert_server_ips(self, addresses, expected):
        with mock.patch.object(
            mediamtx_systeminfo,
            "psutil",
            FakePsutil(addresses),
        ):
            self.assertEqual(mediamtx_systeminfo.get_server_ips(), expected)

    def test_network_counters_keep_using_monitored_interfaces(self):
        with mock.patch.object(
            mediamtx_systeminfo,
            "psutil",
            FakeNetIoPsutil(),
        ):
            self.assertEqual(
                mediamtx_systeminfo.get_filtered_net_io(),
                {"bytes_recv": 100, "bytes_sent": 200},
            )

    def test_returns_one_ipv4_address(self):
        self.assert_server_ips(
            {"eth0": [Address(socket.AF_INET, "192.0.2.10")]},
            ["192.0.2.10"],
        )

    def test_returns_two_ipv4_addresses_in_interface_order(self):
        self.assert_server_ips(
            {
                "eth0": [Address(socket.AF_INET, "192.168.95.18")],
                "wg0": [Address(socket.AF_INET, "172.16.90.18")],
            },
            ["192.168.95.18", "172.16.90.18"],
        )

    def test_returns_three_ipv4_addresses(self):
        self.assert_server_ips(
            {
                "eth0": [Address(socket.AF_INET, "159.69.199.209")],
                "eth1": [Address(socket.AF_INET, "192.168.97.3")],
                "wg0": [Address(socket.AF_INET, "172.16.90.17")],
            },
            ["159.69.199.209", "192.168.97.3", "172.16.90.17"],
        )

    def test_limits_output_to_first_three_candidates(self):
        self.assert_server_ips(
            {
                "eth0": [
                    Address(socket.AF_INET, "192.0.2.1"),
                    Address(socket.AF_INET, "192.0.2.2"),
                ],
                "eth1": [
                    Address(socket.AF_INET, "192.0.2.3"),
                    Address(socket.AF_INET, "192.0.2.4"),
                ],
            },
            ["192.0.2.1", "192.0.2.2", "192.0.2.3"],
        )

    def test_ignores_ipv6_loopback_link_local_and_helper_interfaces(self):
        self.assert_server_ips(
            {
                "lo": [Address(socket.AF_INET, "127.0.0.1")],
                "eth0": [
                    Address(socket.AF_INET6, "2001:db8::10"),
                    Address(socket.AF_INET, "169.254.10.1"),
                    Address(socket.AF_INET, "10.77.0.108"),
                ],
                "docker0": [Address(socket.AF_INET, "172.17.0.1")],
                "veth123": [Address(socket.AF_INET, "172.18.0.2")],
                "wg0": [Address(socket.AF_INET, "172.16.90.123")],
            },
            ["10.77.0.108", "172.16.90.123"],
        )

    def test_removes_duplicate_ipv4_addresses(self):
        self.assert_server_ips(
            {
                "eth0": [Address(socket.AF_INET, "192.168.95.15")],
                "wg0": [
                    Address(socket.AF_INET, "192.168.95.15"),
                    Address(socket.AF_INET, "172.16.90.15"),
                ],
            },
            ["192.168.95.15", "172.16.90.15"],
        )


if __name__ == "__main__":
    unittest.main()
