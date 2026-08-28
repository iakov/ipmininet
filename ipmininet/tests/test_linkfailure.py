""""This module test the Link Failure API"""

import time

import pytest

from ipmininet.clean import cleanup
from ipmininet.ipnet import IPNet
from ipmininet.iptopo import IPTopo
from ipmininet.router import IPNode
from . import require_root
from .utils import assert_connectivity, assert_node_not_connected
from ..examples.link_failure import FailureTopo


def _wait_route(router: IPNode, dst_ip: str, v6=False, timeout=120):
    """Wait for `router` to have a route (with a next-hop) to `dst_ip`."""
    cmd = "ip %sroute get %s" % ("-6 " if v6 else "", dst_ip)
    t = 0
    while t < timeout:
        out = router.cmd(cmd.split(" "))
        if "via" in out:
            return
        time.sleep(1)
        t += 1
    pytest.fail("No route to %s from %s within %ds" % (dst_ip, router.name,
                                                       timeout))


def _wait_reconvergence(net: IPNet, timeout=120):
    """Wait for OSPF to recompute routes after link restoration.

    The connectivity probe can false-negative while the routing tables are
    still empty right after `restoreIntfs`, so wait for each router to learn
    a route to the far host (both address families) before probing.
    """
    for v6 in (False, True):
        h1_ip = net["h1"].defaultIntf().ip6 if v6 \
            else net["h1"].defaultIntf().ip
        h2_ip = net["h2"].defaultIntf().ip6 if v6 \
            else net["h2"].defaultIntf().ip
        _wait_route(net["r1"], h2_ip, v6=v6, timeout=timeout)
        _wait_route(net["r2"], h1_ip, v6=v6, timeout=timeout)


class Topo(IPTopo):

    def build(self, *args, **kwargs):
        r1 = self.addRouter("r1")
        r2 = self.addRouter("r2")
        h1 = self.addHost("h1")
        h2 = self.addHost("h2")

        self.addLinks((r1, r2), (h1, r1), (h2, r2))
        super().build(*args, **kwargs)


@require_root
def test_failure_topo():
    try:
        net = IPNet(topo=FailureTopo())
        net.start()

        # Check example connectivity
        assert_connectivity(net, v6=False)
        assert_connectivity(net, v6=True)

        net.stop()
    finally:
        cleanup()


@require_root
@pytest.mark.parametrize("plan", [
    [("r1", "r2")],
    [("h1", "r1")],
    [("r1", "h1"), ("r2", "r1"), ("r2", "h2")],
])
def test_failurePlan(plan):
    try:
        net = IPNet(topo=Topo())
        net.start()

        # Wait for OSPF convergence
        assert_connectivity(net, v6=False)
        assert_connectivity(net, v6=True)

        interface_down = net.runFailurePlan(plan)

        # Check failures
        for n1, n2 in plan:
            assert_node_not_connected(src=net[n1], dst=net[n2], v6=False)
            assert_node_not_connected(src=net[n1], dst=net[n2], v6=True)

        net.restoreIntfs(interface_down)

        # Wait for OSPF reconvergence before probing connectivity
        _wait_reconvergence(net)

        # Check link restoration
        assert_connectivity(net, v6=False)
        assert_connectivity(net, v6=True)
        net.stop()
    finally:
        cleanup()


@require_root
@pytest.mark.parametrize("downed_links", [1, 2, 3])
def test_randomFailure(downed_links):
    try:
        net = IPNet(topo=Topo())
        net.start()

        # Wait for OSPF convergence
        assert_connectivity(net, v6=False)
        assert_connectivity(net, v6=True)

        interface_down = net.randomFailure(downed_links)

        # Check a failure between both hosts
        assert_node_not_connected(src=net["h1"], dst=net["h2"], v6=False)
        assert_node_not_connected(src=net["h1"], dst=net["h2"], v6=True)

        net.restoreIntfs(interface_down)

        # Wait for OSPF reconvergence before probing connectivity
        _wait_reconvergence(net)

        # Check link restoration
        assert_connectivity(net, v6=False)
        assert_connectivity(net, v6=True)
        net.stop()
    finally:
        cleanup()


@require_root
def test_randomFailureOnTargetedLink():
    try:
        net = IPNet(topo=Topo())
        net.start()

        # Wait for OSPF convergence
        assert_connectivity(net, v6=False)
        assert_connectivity(net, v6=True)

        itfs = net.randomFailure(1,
                                 weak_links=[net["r1"].intf("r1-eth0").link])

        # Check a failure between both hosts
        assert_node_not_connected(src=net["h1"], dst=net["h2"], v6=False)
        assert_node_not_connected(src=net["h1"], dst=net["h2"], v6=True)

        net.restoreIntfs(itfs)

        # Wait for OSPF reconvergence before probing connectivity
        _wait_reconvergence(net)

        # Check link restoration
        assert_connectivity(net, v6=False)
        assert_connectivity(net, v6=True)
        net.stop()
    finally:
        cleanup()
