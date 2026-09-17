# Part 1 – Test Design & Risk Analysis
## mDNS Device Discovery for Wi-Fi Connected Audio Device

## Assumptions
- The device advertises a single mDNS service type, `_speaker._tcp.local`, over standard mDNS (port 5353, multicast) ref:mdns rfc6762.
- The mobile app discovers devices by issuing an mDNS query/browse and listening for responses; it does not rely solely on a long-lived cache.
- Device and phone are on the same L2 broadcast domain / subnet (no mDNS reflector or VLAN routing involved in the base case).
- Hostname is derived from device model + serial number (e.g. `Beosound-Balance-12345678.local`) and is expected to be unique per device.
- TXT records (`sn`, `wa`, `fv`, `fn`, `pt`) are the source of truth the app uses to identify and display the device, not just the hostname.
- "Not appearing in the app" can mean either (a) the device isn't advertising, (b) the advertisement isn't reaching the app, or (c) the app has stale/cached state, and these have different root causes and different fixes.


## Test Scenarios

| # | Scenario | What could go wrong | How to detect it |
|---|----------|---------------------|-------------------|
| 1 | Device boot & initial advertisement | Device advertises before Wi-Fi/IP is fully stable; announcement lost | Capture mDNS traffic from boot; verify announce packet sent after IP is confirmed, with correct TTL |
| 2 | Wi-Fi disconnect & reconnect | Device reconnects with same or new IP but doesn't re-announce; app holds stale IP | Force disconnect/reconnect, measure time-to-reappear in app; check re-announcement packet is sent |
| 3 | Device power cycle | Device takes longer to re-advertise than app's discovery timeout; goodbye packet not sent on shutdown | Power cycle, verify a "goodbye" (TTL=0) packet is sent, then a fresh announce on boot |
| 4 | Multiple devices on same network | Devices interfere, or app dedupes incorrectly (e.g., same friendly name) | Run discovery with 2+ devices, verify each is listed distinctly |
| 5 | IP address changes (DHCP renewal) | Device gets new IP via DHCP but doesn't re-announce; app/router ARP cache holds old IP | Trigger DHCP renewal, verify device re-announces with new IP within acceptable window |
| 6 | Router reboot | Router reboot drops Wi-Fi; device reconnects with new IP; same failure mode as #5 but network-initiated | Reboot router, observe device log + app visibility (this matches the actual failure in `device_logs.txt`) |
| 7 | Duplicate hostnames / service conflicts | Two devices claim the same hostname (factory reset, cloned config); mDNS conflict resolution appends a suffix or one device silently drops | Introduce two devices with identical hostname, verify conflict is resolved (renamed) rather than one disappearing silently |

## Highest-Risk Scenarios

Ranked by likelihood × customer impact:

1. **IP address changes (DHCP renewal) / Router reboot (#5, #6)** is the highest risk. This is the exact failure pattern shown in the provided logs: IP changes on reconnect, and the device silently fails to reappear. It's also the most common real-world trigger (routers reboot for updates, DHCP leases expire).
2. **Device power cycle (#3)** is high risk if the device doesn't send a "goodbye" packet before shutdown or takes too long to re-announce on boot; apps relying on TTL expiry alone will show a stale/offline entry for a while.
3. **Duplicate hostnames (#7)** is medium to high risk, lower frequency but hard to diagnose in the field and can look identical to a discovery bug from the customer's point of view.
4. **Wi-Fi disconnect/reconnect (#2)** is medium risk, largely overlaps with #5/#6 but worth testing independently since it isolates the Wi-Fi layer from the router/DHCP layer.
5. **Multiple devices (#4)** and **boot/initial advertisement (#1)** are lower risk; these are typically easier to get right and are exercised constantly in normal use, so regressions tend to surface quickly in everyday testing.

## What to Automate First, and Why

1. **Static/mocked validation of discovery output** (device is discoverable, correct service type, valid IP, valid TXT records). This is the cheapest to automate, fully deterministic, no hardware timing involved. This is the foundation everything else builds on (Part 2 covers this).
2. **IP-change / re-announcement timing (#5, #6)**. Automate next because it's the highest real-world risk and is scriptable: trigger a DHCP renewal or simulate a router restart, then assert the device re-announces within an SLA (e.g., <5s) and the app-facing record reflects the new IP, not the old one.
3. **Power cycle re-advertisement (#3)**. Automate once hardware control (smart PDU) is available; assert a goodbye packet is sent and re-announcement happens within an acceptable boot window.
4. **Duplicate hostname conflict handling (#7)**. Automate with two devices/mocked responders once the mDNS conflict-resolution behavior is defined, since it's a lower-frequency but hard-to-debug edge case.

Multi-device (#4) and cold boot (#1) are good candidates for manual/exploratory or lower-priority automated coverage, since they are lower risk and generally already exercised as a side effect of the other automated scenarios.

---

# Part 2 – Python Automation

The full code for this part is in the separate files `mdns_discovery.py` and `test_template.py`, and the test run output is in `pytest_output.txt`. Here is a plain language summary of what was done.

`discovery_results.json` was used as the mocked mDNS output, as instructed. The following pytest tests were written or extended:

1. **Device is discoverable**: checks that at least one device shows up in the discovery results.
2. **Correct service type is advertised**: checks that the device is advertising the expected service, `_speaker._tcp.local`.
3. **IP addresses are valid**: checks that the IP address is a properly formed IP address, using each device's full record (name, hostname, IP, service, port).
4. **Additional tests added**:
   - **TXT records are valid**: checks that the extra data the device advertises (serial number, MAC address, firmware version, friendly name) is present and correctly formatted. This matters because apps often use these fields to identify the device, not just the hostname.
   - **Port is in a valid range**: checks the port number is a real, usable port (between 1 and 65535), not just any positive number.
   - **No duplicate hostnames**: checks that the current mocked data has no two devices sharing the same hostname, and includes a second test that simulates two devices with the same hostname on purpose, to prove the duplicate check actually works. This ties back to the "duplicate hostnames" risk from Part 1.
   - **Invalid MAC address is rejected**: checks that a badly formed MAC address in the TXT records is caught by validation instead of silently passing.

All 8 tests pass. The full run output is saved in `pytest_output.txt`.

---


# Part 3 – Troubleshooting

## What happened, based on the logs

1. The device boots and connects to Wi-Fi with IP `192.168.1.123`.
2. It starts sending mDNS advertisements right away.
3. The router restarts. This causes the Wi-Fi to drop.
4. The device reconnects, but this time it gets a new IP, `192.168.1.128`.
5. The app asks for devices right after this reconnect.
6. The device does not show up in the app.

## Most likely root cause

The device does not send a fresh mDNS announcement after it reconnects to Wi-Fi with a new IP address. The old announcement (tied to `192.168.1.123`) is now out of date, but nothing from the logs we have tells the network or the app that things changed. When the app asks for devices right after the reconnect, there is no valid, up to date record for it to find yet.

In short: The device changed its IP but did not "re-introduce" itself on the network fast enough, and the app happened to ask right in that gap.

A second possible factor: Even if the device did eventually re-announce, the app or the network itself might be holding on to the old IP for a short time (a stale cache), so even a fresh announcement might not be picked up right away.

## Additional information to collect

- A packet capture (like from Wireshark or tcpdump) around the reconnect, to see if and when the device sends a new mDNS announcement after getting the new IP.
- The exact timing: how many seconds after reconnect does the device send its next mDNS packet? Compare this to how long the app waits before giving up on a discovery request.
- Device firmware logs at a more detailed level, to see if the mDNS service on the device is aware that the IP changed, or if it just keeps running with old state.
- Whether the device sends a "goodbye" message (a packet that tells the network to forget the old record) before or during the disconnect.
- App side logs, to check if the app is using a cached list of devices instead of doing a fresh mDNS query every time.
- Whether this only happens after a router restart, or also after a normal Wi-Fi drop and reconnect without a router restart. This helps tell if the problem is really about the IP change, or something else tied to routers restarting.

## Regression test(s) to prevent recurrence

### RT-1: After an address change, a goodbye (TTL=0) is sent for the old address.
- **Asserts**: The Time to live (TTL) for the old record must be 0.

- **Why**: If the old record is still cached, it means it has the previous ip address mapping which will mean the device cannot be found by the app on the new address.

- **How**: Listen and capture the packet on UDP 5353 across the entire address transition then confirm a packet appeared containing the old address with TTL=0. 

### RT-2: Updated announcement arrives within 5 seconds of an address change.
- **Asserts**: The device sends a fresh mDNS announcement within 5 seconds (acceptable time window picked arbitrarily), measured from the point the interface reports its new address.

- **Why**: The log file (device_logs.txt) shows no re-announcement after reconnection therefore having an acceptable bound (5 sec) is needed to check if it is a late arrival of the announcement in that situation as the app discovery was issued within a second of the interface reporting its new address.

- **How**: Force an address change through DHCP release/renew or a router reboot then capture UDP 5353 from a third host on the network. Timestamp the first packet containing the new address, compare against threshold (5 sec).

### RT-3: Advertised A record matches the current interface address.
- **Asserts**: The A record the device advertises for its hostname resolves to the address currently assigned to its interface.

- **Why**: This serves as a final check and follow up on RT-1 where we confirm no mismatch with the hostname mapping to the interface address for any other reason besides a stale record.

- **How**: Read the device's current interface address, query the hostname over mDNS from a second host on the network and compare.
---

# Part 4 – System Thinking

## Goal

Automate mDNS validation in CI so that every time firmware or app code changes, we can check that real devices still announce themselves correctly and stay discoverable through common events like Wi-Fi drops, IP changes, and router restarts.

## How the pieces fit together

**Linux systems**
A Linux machine acts as the test controller. It sits on the same network as the test devices. This machine runs the actual mDNS discovery, using a tool like `avahi-browse` or a Python library such as `zeroconf`, so we are testing with a real mDNS client, not just a mock. It also runs our pytest test suite, and it can run packet captures if we need to check that specific mDNS packets were sent.

**Hardware test equipment**
Real devices are needed here, not just mocked JSON, because we want to catch real firmware bugs like the one in Part 3. Useful equipment includes:
- A smart power switch (PDU) so tests can power cycle a device automatically, without a person unplugging it.
- Access to the device's serial or debug logs, so test failures come with real diagnostic detail.
- Multiple physical devices, so we can also test the "multiple devices on the network" and "duplicate hostname" scenarios for real.

**Network infrastructure**
We need a small, controlled test network for this, separate from any office or production network, so tests are repeatable and do not get messed up by other traffic. This should include:
- A router or access point that can be restarted programmatically, either through its own API or by putting it on a smart power switch.
- The ability to simulate a DHCP renewal or IP change on demand.
- Enough isolation that the mDNS traffic from other devices does not interfere with the test results.

**GitHub Actions**
GitHub Actions is where we define and trigger the workflow, but the actual test devices and network live in our lab, not on GitHub's own servers. Because of this, we would use a self hosted GitHub Actions runner, meaning a machine we control (likely the same Linux test controller mentioned above, or one connected to it) that can reach the lab network. The workflow would:
1. Trigger on a pull request or a schedule (for example, run nightly).
2. Connect to the self hosted runner.
3. Run setup steps, like power cycling devices to a known clean state.
4. Run the pytest suite against the real devices, covering scenarios like reconnect and re-announce, router restart, and duplicate hostname handling.
5. Collect logs and packet captures as build artifacts if something fails.
6. Report pass or fail back to the pull request, so failures are visible before code is merged.

## Why this matters

This setup lets us catch problems like the one in Part 3 automatically, before they reach real customers. The mocked, JSON based tests from Part 2 are fast and good for checking logic and data validation on every commit. The hardware based CI pipeline described here is slower and would likely run less often (for example, nightly or before a release), but it is the layer that actually proves the device behaves correctly in real network conditions, not just in theory.
