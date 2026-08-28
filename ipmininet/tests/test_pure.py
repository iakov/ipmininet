"""Rootless unit tests for pure logic.

These tests never require root privileges and never start a network, so they
can be run locally by any user (see scripts/run-tests-local.sh) and will run
in a rootless CI job. Tests that require root are marked with `require_root`
in the other test modules.
"""
from ipaddress import ip_network
from ipaddress import IPv4Network, IPv6Network

import pytest

from ipmininet.link import _parse_addresses
from ipmininet.router.config.utils import ConfigDict, ip_statement
from ipmininet.utils import get_set, is_container, is_subnet_of


class TestParseAddresses:
    """Tests for the pure `ip address` output parser."""

    def test_parse_full_output(self):
        out = """1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
    inet6 ::1/128 scope host
       valid_lft forever preferred_lft forever
"""
        mac, v4, v6 = _parse_addresses(out)
        assert mac == "00:00:00:00:00:00"
        assert [a.with_prefixlen for a in v4] == ["127.0.0.1/8"]
        assert [a.with_prefixlen for a in v6] == ["::1/128"]

    def test_parse_empty(self):
        mac, v4, v6 = _parse_addresses("")
        assert mac is None
        assert v4 == []
        assert v6 == []

    def test_parse_ignores_malformed_lines(self):
        out = """2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue
    link/ether 00:11:22:33:44:55 brd ff:ff:ff:ff:ff:ff
    this is not a valid ip line
    inet 192.168.0.2/24 brd 192.168.0.255 scope global eth0
"""
        mac, v4, v6 = _parse_addresses(out)
        assert mac == "00:11:22:33:44:55"
        assert [a.with_prefixlen for a in v4] == ["192.168.0.2/24"]
        assert v6 == []


class TestIsSubnetOf:
    def test_v4_subnet(self):
        assert is_subnet_of(ip_network("10.0.0.0/24"), ip_network("10.0.0.0/16"))
        assert not is_subnet_of(ip_network("10.1.0.0/16"), ip_network("10.0.0.0/16"))

    def test_v4_self(self):
        assert is_subnet_of(ip_network("10.0.0.0/16"), ip_network("10.0.0.0/16"))

    def test_v6_subnet(self):
        assert is_subnet_of(ip_network("2001:db8::/32"), ip_network("2001::/16"))
        assert not is_subnet_of(ip_network("2002::/16"), ip_network("2001::/16"))

    def test_cross_version_raises(self):
        with pytest.raises(TypeError):
            is_subnet_of(IPv4Network("10.0.0.0/8"), IPv6Network("2001:db8::/32"))

    def test_non_network_raises(self):
        with pytest.raises(TypeError):
            is_subnet_of("10.0.0.0/8", IPv4Network("10.0.0.0/8"))


class TestIsContainer:
    def test_sequences(self):
        assert is_container([1, 2, 3])
        assert is_container((1, 2, 3))

    def test_not_container(self):
        assert not is_container("a string")
        assert not is_container(42)


class TestGetSet:
    def test_existing_key(self):
        d = {"a": 1}
        assert get_set(d, "a", list) == 1
        assert d == {"a": 1}

    def test_missing_key(self):
        d = {}
        assert get_set(d, "b", list) == []
        assert d == {"b": []}


class TestConfigDict:
    def test_attribute_access(self):
        d = ConfigDict(foo="bar")
        assert d.foo == "bar"
        assert d["foo"] == "bar"

    def test_missing_attribute_is_none(self):
        d = ConfigDict()
        assert d.missing is None

    def test_attribute_assignment(self):
        d = ConfigDict()
        d.foo = "bar"
        assert d["foo"] == "bar"


@pytest.mark.parametrize("ip,expected", [
    ("10.0.0.0/8", "ip"),
    (4, "ip"),
    ("2001:db8::/32", "ipv6"),
    (6, "ipv6"),
])
def test_ip_statement(ip, expected):
    assert ip_statement(ip) == expected
