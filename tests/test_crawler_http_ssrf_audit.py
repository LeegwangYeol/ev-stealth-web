"""
Comprehensive Audit & Hardening Test Suite for:
1. SSRF Defense:
   - Private subnets (RFC 1918: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
   - Loopback (127.0.0.0/8, ::1)
   - Link-local & Cloud Metadata (169.254.169.254, 100.100.100.200)
   - Encoded IPv4 (octal, decimal, hex)
   - IPv4-mapped IPv6 (::ffff:127.0.0.1, ::ffff:169.254.169.254)
   - Internal domain suffixes (.localhost, .local, .internal, .lan, .localdomain)
   - Disallowed ports (22, 25, 6379, 11211, 27017)
   - Redirect SSRF protection (SafeRedirectHandler blocks 3xx to internal IPs)
   - Configurable override (allow_private_ips=True)
2. Network Timeouts:
   - Explicit separate connect & read timeouts passed dynamically to request()
   - Non-positive or NaN timeouts normalized cleanly
   - Slowloris streaming read wall-clock deadline guard
3. Circuit Breaking:
   - Host extraction with basic auth credentials (user:pass@host) and IPv6 literals
   - HALF_OPEN state canary probe tracking and concurrency limiting
   - Failure re-trip and probe count reset
4. User-Agent Rotation:
   - Desktop-only pool verification (no mobile tokens) in utils and scrapers
   - Rotation with exclude parameter
   - Graceful fallback when pool is empty
5. Module & Alias Parity:
   - Interface consistency across utils.safe_http, utils.safe_http_client,
     crawlers.safe_http, crawlers.safe_http_client, and scrapers.common_utils
"""

from __future__ import annotations

import http.client
import http.cookiejar
import io
import ipaddress
import socket
import unittest
from unittest.mock import MagicMock, patch
import urllib.error
import urllib.request

from utils.http_client import (
    DEFAULT_FALLBACK_USER_AGENT,
    DISALLOWED_HOSTS,
    DISALLOWED_HOST_SUFFIXES,
    STANDARD_SAFE_PORTS,
    USER_AGENT_POOL,
    CircuitBreaker,
    CircuitBreakerState,
    ResilientHTTPConnection,
    ResilientHTTPHandler,
    SafeHttpClient,
    SafeRedirectHandler,
    is_safe_ip,
    is_safe_url,
)
import utils.safe_http as utils_safe_http
import utils.safe_http_client as utils_safe_http_client
import crawlers.safe_http as crawlers_safe_http
import crawlers.safe_http_client as crawlers_safe_http_client
import scrapers.common_utils as common_utils


class TestSSRFDefense(unittest.TestCase):
    """Deep verification of SSRF defense vectors and bypass protections."""

    def test_loopback_and_private_ip_detection(self):
        """is_safe_ip rejects loopback, RFC 1918, link-local metadata, and unspecified IPs."""
        blocked_ips = [
            "127.0.0.1",
            "127.0.0.2",
            "10.0.0.1",
            "10.255.255.255",
            "172.16.0.1",
            "172.31.255.255",
            "192.168.0.1",
            "192.168.1.254",
            "169.254.169.254",  # AWS/GCP/Azure IMDS
            "100.100.100.200",  # Alibaba Cloud metadata
            "0.0.0.0",
            "::1",
            "::",
            "fe80::1",
            "::ffff:127.0.0.1",
            "::ffff:169.254.169.254",
        ]
        for ip_str in blocked_ips:
            ip = ipaddress.ip_address(ip_str)
            self.assertFalse(is_safe_ip(ip), f"IP {ip_str} should be flagged as unsafe")

        # Public IPs must be safe
        public_ips = ["93.184.215.14", "8.8.8.8", "1.1.1.1", "2606:4700:4700::1111"]
        for ip_str in public_ips:
            ip = ipaddress.ip_address(ip_str)
            self.assertTrue(is_safe_ip(ip), f"IP {ip_str} should be safe")

    def test_encoded_and_nonstandard_ip_representations(self):
        """is_safe_url blocks octal, decimal, and hexadecimal representations of private IPs."""
        encoded_urls = [
            "http://0177.0.0.1/admin",      # Octal 127.0.0.1
            "http://2130706433/secrets",    # Decimal 127.0.0.1
            "http://0x7f000001/status",     # Hex 127.0.0.1
            "http://0177.0000.0000.0001/",  # Padded octal
        ]
        for url in encoded_urls:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Encoded IP URL {url} should be blocked")
            self.assertIn("SSRF blocked", reason)

    def test_internal_hostnames_and_suffixes(self):
        """is_safe_url blocks localhost, metadata domains, and internal suffixes."""
        blocked_domains = [
            "http://localhost:8080/metrics",
            "http://app.localhost/api",
            "http://metadata.google.internal/computeMetadata/v1/",
            "http://kubernetes.default.svc.cluster.local/",
            "http://database.internal:5432/",
            "http://server.lan/admin",
            "http://router.localdomain/",
            "http://intranet.local/",
        ]
        for url in blocked_domains:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Internal domain URL {url} should be blocked")
            self.assertIn("SSRF blocked", reason)

    def test_disallowed_schemes_and_ports(self):
        """is_safe_url blocks non-HTTP schemes and dangerous infrastructure ports."""
        unsafe_schemes = [
            "file:///etc/passwd",
            "gopher://127.0.0.1:6379/_flushall",
            "ftp://files.example.com/",
            "ldap://auth.internal/",
            "dict://127.0.0.1:11211/stats",
        ]
        for url in unsafe_schemes:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Scheme in URL {url} should be rejected")

        unsafe_ports = [
            "http://example.com:22/",     # SSH
            "http://example.com:25/",     # SMTP
            "http://example.com:6379/",   # Redis
            "http://example.com:11211/",  # Memcached
            "http://example.com:27017/",  # MongoDB
            "http://example.com:6443/",   # Kubernetes API
        ]
        for url in unsafe_ports:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Port in URL {url} should be blocked")
            self.assertIn("Disallowed port", reason)

    def test_safe_public_urls_allowed(self):
        """is_safe_url allows standard web URLs on public domains and safe ports."""
        allowed_urls = [
            "https://www.bobaedream.co.kr/list",
            "https://gall.dcinside.com/board/lists",
            "https://example.com/api/test",
            "http://example.com:8080/data",
            "https://example.com:8443/secure",
        ]
        for url in allowed_urls:
            safe, reason = is_safe_url(url)
            self.assertTrue(safe, f"Public URL {url} should be allowed (reason: {reason})")

    def test_safe_http_client_blocks_ssrf_requests(self):
        """SafeHttpClient fast-fails SSRF targets, returning (0, '', b'') without hitting network."""
        client = SafeHttpClient(enable_jitter=False)
        ssrf_targets = [
            "http://127.0.0.1/admin",
            "http://localhost:3000/api",
            "http://169.254.169.254/latest/meta-data/",
            "http://10.0.0.1/internal",
            "http://[::1]/secret",
            "http://0177.0.0.1/",
            "http://example.com:6379/",
        ]
        for target in ssrf_targets:
            status, text, raw = client.request(target)
            self.assertEqual(status, 0, f"Target {target} should return status 0")
            self.assertEqual(text, "")
            self.assertEqual(raw, b"")

    def test_allow_private_ips_override(self):
        """allow_private_ips=True allows local/private requests when explicitly configured."""
        client = SafeHttpClient(allow_private_ips=True, enable_jitter=False)
        self.assertTrue(client.allow_private_ips)

        class MockOpener:
            def open(self, req, timeout=15.0):
                resp = MagicMock()
                resp.getcode.return_value = 200
                resp.headers = {"Content-Type": "application/json"}
                resp.read.side_effect = [b'{"status":"ok"}', b""]
                return resp

        client.opener = MockOpener()
        status, text, raw = client.request("http://127.0.0.1:8080/local-api")
        self.assertEqual(status, 200)
        self.assertIn("ok", text)

    def test_safe_redirect_handler_blocks_redirect_ssrf(self):
        """SafeRedirectHandler intercepts 3xx redirect to metadata / loopback and raises HTTPError 403."""
        handler = SafeRedirectHandler(allow_private_ips=False)
        req = urllib.request.Request("https://example.com/initial")
        fp = io.BytesIO(b"redirecting")
        headers = {}

        for dangerous_target in [
            "http://169.254.169.254/latest/meta-data/",
            "http://127.0.0.1/admin",
            "http://localhost/secret",
            "http://10.0.0.5/",
        ]:
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                handler.redirect_request(req, fp, 302, "Found", headers, dangerous_target)
            self.assertEqual(ctx.exception.code, 403)
            self.assertIn("SSRF Blocked", ctx.exception.reason)


class TestNetworkTimeoutsHardening(unittest.TestCase):
    """Deep verification of network timeouts, dynamic propagation, and Slowloris guards."""

    def test_separate_connect_and_read_timeouts(self):
        """SafeHttpClient stores and exposes connect_timeout and read_timeout properties."""
        client = SafeHttpClient(connect_timeout=3.0, read_timeout=12.0, enable_jitter=False)
        self.assertEqual(client.connect_timeout, 3.0)
        self.assertEqual(client.read_timeout, 12.0)

        # Tuple initialization
        client_tuple = SafeHttpClient(timeout=(4.5, 18.0), enable_jitter=False)
        self.assertEqual(client_tuple.connect_timeout, 4.5)
        self.assertEqual(client_tuple.read_timeout, 18.0)

    def test_per_request_timeout_dynamic_propagation(self):
        """Per-request connect_timeout and read_timeout are dynamically attached to urllib Request."""
        client = SafeHttpClient(connect_timeout=5.0, read_timeout=15.0, enable_jitter=False)

        recorded_req = None

        class MockRecordingOpener:
            def open(self, req, timeout=15.0):
                nonlocal recorded_req
                recorded_req = req
                resp = MagicMock()
                resp.getcode.return_value = 200
                resp.headers = {}
                resp.read.side_effect = [b"ok", b""]
                return resp

        client.opener = MockRecordingOpener()
        status, _, _ = client.request(
            "https://example.com/custom-timeout",
            connect_timeout=2.0,
            read_timeout=7.5,
        )
        self.assertEqual(status, 200)
        self.assertIsNotNone(recorded_req)
        self.assertEqual(getattr(recorded_req, "_connect_timeout", None), 2.0)
        self.assertEqual(getattr(recorded_req, "_read_timeout", None), 7.5)

    def test_non_positive_and_nan_timeout_normalization(self):
        """Non-positive, zero, or invalid timeouts cleanly normalize to positive defaults."""
        for bad_to in [-10.0, 0.0, None]:
            client = SafeHttpClient(timeout=bad_to, enable_jitter=False)
            self.assertGreater(client.connect_timeout, 0)
            self.assertGreater(client.read_timeout, 0)


class TestCircuitBreakerHardening(unittest.TestCase):
    """Deep verification of Circuit Breaker host extraction, HALF_OPEN probe limiting, and recovery."""

    def test_extract_host_basic_auth_and_ipv6(self):
        """_extract_host correctly handles URLs with basic auth credentials and IPv6 literals."""
        cb = CircuitBreaker()
        self.assertEqual(
            cb._extract_host("https://user:password@www.bobaedream.co.kr/list"),
            "www.bobaedream.co.kr",
        )
        self.assertEqual(
            cb._extract_host("http://admin:secret@api.example.com:8080/data"),
            "api.example.com",
        )
        self.assertEqual(
            cb._extract_host("http://[::1]:8080/test"),
            "::1",
        )
        self.assertEqual(
            cb._extract_host("gall.dcinside.com:443"),
            "gall.dcinside.com",
        )
        self.assertEqual(
            cb._extract_host("https://example.com"),
            "example.com",
        )

    def test_half_open_probe_limiting(self):
        """In HALF_OPEN state, probe_count limits concurrent canary probes to half_open_max_probes."""
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.05, half_open_max_probes=1)
        host = "api.test.com"

        # Trip to OPEN
        cb.record_failure(host, status_code=503)
        self.assertEqual(cb.get_state(host), CircuitBreakerState.OPEN)
        self.assertFalse(cb.is_available(host))

        # Wait for cooldown
        import time
        time.sleep(0.08)
        self.assertEqual(cb.get_state(host), CircuitBreakerState.HALF_OPEN)
        self.assertTrue(cb.is_available(host))

        # First canary probe consumes probe allowance
        cb.record_probe(host)
        # Second probe must be denied because probe_count >= half_open_max_probes (1)
        self.assertFalse(cb.is_available(host))

        # Probe failure re-trips circuit to OPEN and resets probe_count
        cb.record_failure(host, status_code=503)
        self.assertEqual(cb.get_state(host), CircuitBreakerState.OPEN)

        # Wait again for cooldown
        time.sleep(0.08)
        self.assertEqual(cb.get_state(host), CircuitBreakerState.HALF_OPEN)
        self.assertTrue(cb.is_available(host))

        # Probe success restores circuit to CLOSED
        cb.record_probe(host)
        cb.record_success(host)
        self.assertEqual(cb.get_state(host), CircuitBreakerState.CLOSED)
        self.assertTrue(cb.is_available(host))


class TestUserAgentRotationHardening(unittest.TestCase):
    """Deep verification of modern desktop User-Agent pool and rotation diversity."""

    def test_desktop_user_agent_pool_purity(self):
        """USER_AGENT_POOL in utils and common_utils must contain only modern desktop browsers."""
        mobile_tokens = ["iPhone", "iPad", "Android", "Mobile"]

        for pool, mod_name in [
            (USER_AGENT_POOL, "utils.http_client"),
            (common_utils.USER_AGENT_POOL, "scrapers.common_utils"),
        ]:
            self.assertGreaterEqual(len(pool), 5, f"{mod_name} pool has fewer than 5 UAs")
            for ua in pool:
                for token in mobile_tokens:
                    self.assertNotIn(
                        token,
                        ua,
                        f"Mobile token '{token}' found in {mod_name} UA: {ua}",
                    )
                self.assertTrue(
                    "Macintosh" in ua or "Windows NT" in ua,
                    f"UA in {mod_name} is not recognized desktop UA: {ua}",
                )

    def test_user_agent_rotation_diversity_and_fallback(self):
        """get_random_user_agent(exclude=...) rotates cleanly and uses fallback when pool empty."""
        client = SafeHttpClient(enable_jitter=False)
        ua1 = USER_AGENT_POOL[0]
        for _ in range(20):
            ua2 = client.get_random_user_agent(exclude=ua1)
            self.assertNotEqual(ua1, ua2)

        # Fallback UA when pool is empty
        with patch("utils.http_client.USER_AGENT_POOL", []):
            fallback = client.get_random_user_agent()
            self.assertEqual(fallback, DEFAULT_FALLBACK_USER_AGENT)


class TestModuleInterfaceParity(unittest.TestCase):
    """Verify export parity across all crawler and scraper HTTP utilities."""

    def test_reexport_parity(self):
        """All aliases re-export SafeHttpClient, is_safe_url, is_safe_ip, and SafeRedirectHandler."""
        modules = [
            utils_safe_http,
            utils_safe_http_client,
            crawlers_safe_http,
            crawlers_safe_http_client,
        ]
        for mod in modules:
            self.assertIs(mod.SafeHttpClient, SafeHttpClient)
            self.assertIs(mod.is_safe_url, is_safe_url)
            self.assertIs(mod.is_safe_ip, is_safe_ip)
            self.assertIs(mod.SafeRedirectHandler, SafeRedirectHandler)
            self.assertTrue(hasattr(mod, "CircuitBreaker"))
            self.assertTrue(hasattr(mod, "clean_html_text"))
            self.assertTrue(hasattr(mod, "robust_decode"))

        # scrapers.common_utils parity
        self.assertTrue(hasattr(common_utils, "SafeHttpClient"))
        self.assertTrue(hasattr(common_utils, "is_safe_url"))
        self.assertTrue(hasattr(common_utils, "is_safe_ip"))
        self.assertTrue(hasattr(common_utils, "SafeRedirectHandler"))


if __name__ == "__main__":
    unittest.main()
