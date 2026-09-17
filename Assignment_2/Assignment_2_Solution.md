# Part 1 – Test Design & Risk Analysis
## BLE and Wi-Fi Onboarding for an Audio Device

## Assumptions

- The mobile app connects to the device over BLE first, sends the Wi-Fi credentials (SSID and password) over that BLE link, and then the device should join the Wi-Fi network on its own.
- "Setup complete" means the device joined the Wi-Fi network, got a valid IP address, and is reachable or reported as online, not just that BLE finished.
- The app shows the customer some kind of progress or error state during setup, but the exact wording is not covered here.
- Once the device has the Wi-Fi credentials, it may disconnect BLE on its own as part of the normal flow, since sboth radios share the 2.4 GHz front end, so concurrent operation can reduce throughput.
- Only one device is being set up per BLE session, but more than one device could be nearby and advertising at the same time.

## Test Scenarios

| # | Scenario | What could go wrong | How to detect it |
|---|----------|---------------------|-------------------|
| 1 | First-time setup | A brand new, factory-reset device fails on its very first provisioning attempt | Run the full onboarding flow on a factory-reset device and confirm it ends in "online" status |
| 2 | Incorrect password | Device or app does not clearly report a wrong Wi-Fi password, customer thinks the device is broken | Provision with a wrong password on purpose, confirm a clear, specific failure state (not a generic timeout) |
| 3 | Weak signal | Device is far from the router or in a bad spot, join takes too long or fails partway | Provision with weak signal (attenuator or physical distance), confirm setup either succeeds within a reasonable time or fails with a clear "weak signal" style reason |
| 4 | BLE disconnect during provisioning | BLE link drops before all credentials are sent, device is left in a half configured state | Force a BLE disconnect partway through credential transfer, confirm the device does not attempt to join Wi-Fi with incomplete or corrupted credentials |
| 5 | SSID changes | Customer renames their Wi-Fi network right after or during setup | Change the SSID mid-setup, confirm the device fails clearly instead of getting stuck, and can be re-provisioned |
| 6 | DHCP delays | Router is slow to hand out an IP address, device times out too early | Simulate a slow or delayed DHCP response, confirm the device waits a reasonable amount of time (e.g 60 sec) before giving up, and reports a clear reason if it does |
| 7 | Multiple devices onboarding simultaneously | BLE advertising or Wi-Fi joins from several devices at once interfere with each other, or the app connects to the wrong device | Onboard two or more devices at the same time, confirm each one is provisioned correctly and the app does not mix them up |
| 8 | Device reboot during setup | Device restarts partway through provisioning (power issue, firmware crash), state is lost | Force a reboot mid-setup, confirm the device returns to a clean, restartable setup state rather than a stuck or half configured one |

## Highest-Risk Scenarios

Ranked by likelihood and how bad the impact is for the customer:

1. **BLE disconnect during provisioning (#4)**. This is the highest risk. It matches the exact pattern in the provided logs: BLE disconnects right after credentials are sent, and setup fails soon after with a DHCP timeout.
2. **DHCP delays (#6)**. Closely tied to #4. Even when credentials transfer correctly, a slow or unresponsive DHCP server can make a perfectly good Wi-Fi join look like a failure. This is a common real-world condition, especially on older or overloaded home routers.
3. **Weak signal (#3)**. High impact because it is very common in real homes (device placed far from the router), and it can cause failures that look identical to other problems (timeouts) unless the device or app specifically reports signal strength.
4. **SSID changes (#5)**. Lower frequency, but when it happens it can leave a device in a confusing state if not handled cleanly.
5. **Incorrect password (#2)**. Common, but usually lower risk to test because it is a simple, deterministic scenario. The main risk here is a bad error message, not a systemic failure.
6. **Multiple devices onboarding simultaneously (#7)**. Lower frequency for most households, but worth covering since a mix-up (setting up the wrong device) is very confusing for a customer.
7. **Device reboot during setup (#8)**. Lower frequency, but important to confirm the device fails safe rather than getting stuck in a bad state.
8. **First-time setup (#1)**. Lower risk on its own, since it is the most tested and most common path, but it is the baseline every other scenario builds on.

## What to Automate First, and Why

1. **First-time setup, happy path (#1)**. Automate first as a foundation. Every other test builds on top of a known-good setup flow, and it is cheap and deterministic to run.
2. **BLE disconnect during provisioning (#4) and DHCP delays (#6)**. Automate next, since together they explain the exact failure shown in the logs and represent the highest real-world risk. Both are scriptable: force a BLE drop at a specific point, or delay/withhold a DHCP response, and check the device fails safely and reports a clear reason.
3. **Weak signal (#3)**. Automate once signal attenuation hardware (like a variable RF attenuator) is available, since this is a very common real-world condition that is hard to catch otherwise.
4. **Incorrect password (#2) and SSID changes (#5)**. Automate as straightforward negative tests, since they are simple to script and mainly check that error handling and messaging are correct.
5. **Multiple devices (#7) and device reboot during setup (#8)**. Lower priority for early automation since they need more test hardware (multiple physical devices, or a way to force a reboot), but still worth adding once the core flow is stable and trusted.

---

# Part 2 – Python Automation

The full code for this part is in the separate files `wifi_setup.py` and `test_template.py`, and the test run output is in `pytest_output.txt`. Here is a plain language summary of what was done.

`connectivity_status.json` was used as the mocked connectivity data, as instructed. Two fields were added to it that were referenced by the code but missing from the original file: `ssid` (needed by `validate_setup` and by the SSID test) and `rssi` (added to support a new signal strength test tied to the "weak signal" risk from Part 1).

The following pytest tests were written or extended:

1. **BLE connection established**: checks that `ble_connected` is true.
2. **Wi-Fi provisioning successful**: checks that `wifi_provisioned` is true.
3. **Device received a valid IP address**: checks that the full setup record is valid, including a properly formed IP address.
4. **Additional tests added**:
   - **Device is online**: checks the overall `status` field is `"online"`.
   - **Wi-Fi setup complete**: checks the combined helper function that looks at BLE, Wi-Fi, and status together.
   - **SSID is not empty**: checks that the network name the device joined is actually recorded, not blank.
   - **Device ID is not empty**: matters most when several devices are being onboarded at the same time, so each one can be told apart.
   - **MAC address is valid**: checks the device's MAC address is present and in the correct format.
   - **Signal strength is within range**: checks the reported RSSI value is present and within a realistic range, so the device could warn a customer about a weak signal.
   - **Setup fails without Wi-Fi provisioning**: simulates the exact failure pattern from the device logs (BLE connected, but Wi-Fi provisioning did not finish), and confirms the helper function correctly reports this as not successful.
   - **Invalid MAC address is rejected**: checks a badly formed MAC address is caught by validation instead of silently passing.

All 11 tests pass. The full run output is saved in `pytest_output.txt`.

---

# Part 3 – Troubleshooting

## What happened, based on the logs

1. Device powers on and starts advertising over BLE.
2. The mobile app connects to the device over BLE.
3. Wi-Fi credentials are transferred to the device.
4. BLE disconnects unexpectedly, right after the credentials are sent.
5. The device then tries to join the Wi-Fi network.
6. A DHCP timeout happens, the device does not get an IP address.
7. Setup fails.

## Probable root cause

The most likely root cause is that the DHCP handshake did not complete and the device simply gave up without retrying. Standard DHCP clients typically retransmit DISCOVER packets with exponential backoff over 60 seconds before declaring failure and the log shows 15 seconds. A 15-second cutoff with no retry will fail against any router that's briefly slow, which fits the intermittent pattern customers describe. The log lacks DHCP-level detail, so confirming this requires a capture showing whether DISCOVER was sent and whether anything answered.

A secondary hypothesis is that the BLE disconnect pushed provisioning down a path that isn't properly handled.The BLE connection dropped at 14:00:18, yet the Wi-Fi join attempt did not initiate until 14:00:25, leaving a seven-second gap completely unaccounted for in the timeline. If the provisioning sequence expects the BLE session to survive throughout the handshake, dropping it midway represents a software state machine bug rather than an RF hardware fault. Once BLE drops, the device has no return channel, so the user sees a generic error regardless of what failed.

Finally, the logs cannot reliably distinguish an association failure from a genuine DHCP failure. There is no intermediate "associated" or "authenticated" event recorded between the initial join attempt and the final timeout. An incorrect password, poor signal strength, or an exhausted DHCP pool would produce a log that looks the same. This is a critical logging gap; more granular state transitions across both association and IP acquisition is a necessary prerequisite to definitively diagnosing this class of failure.



## Additional debug data required

- Firmware level logs showing exactly why the BLE link dropped (for example, a timeout, a signal loss, or an error from the BLE stack).
- Whether the Wi-Fi join itself succeeded (device associated with the router) but only the DHCP step failed, or whether the Wi-Fi join also failed or was delayed.
- Router or access point logs, to check if the router even saw a DHCP request from the device, and if so, how it responded.
- A packet capture on the Wi-Fi side, to see if a DHCP request was sent at all, and if so, whether a response came back and was ignored or missed.
- Whether this issue happens only when BLE disconnects unexpectedly, or also on a normal, clean BLE disconnect at the same point in the flow.
- Signal strength (RSSI) at the time of the Wi-Fi join, to rule out a weak signal as a contributing factor.

## Regression test(s) to prevent recurrence

### RT-1: DHCP retry policy over a defined window
- Asserts: The device makes at least a defined number of DHCP discovery attempts within a defined time window (for example, 3 attempts within 30 seconds) before reporting a setup failure, instead of giving up after a single timeout.
- Why: The logs show a single DHCP timeout leading straight to "Setup failed." Right after a BLE-to-Wi-Fi handoff, a single missed DHCP response can be a transient issue rather than a real failure. Without a retry policy, a brief delay looks identical to a real network problem.
- How: Run the device against a DHCP server configured to withhold responses for the first attempt(s) and only respond on a later attempt. Capture DHCP request packets on the network interface and confirm the number and spacing of retry attempts match the defined policy before any success or failure state is reported.

### RT-2: BLE dropped at parametrized points with provisioning still completing
- Asserts: For each tested disconnect point, wifi_provisioned becomes true and status becomes "online" within the expected setup time window.
- Why: The logs show BLE disconnecting unexpectedly right after credentials were transferred. It is not enough to test that one exact moment. If the device already has the full, correct credentials, a BLE drop at other points nearby (just before, during, or just after transfer) should not be able to derail a Wi-Fi join that would otherwise succeed.
- How: Parametrize the test to force a BLE disconnect at several defined points in the flow (for example, mid credential transfer, immediately after transfer, and a few seconds after transfer). For each point, run the full provisioning flow and check the final connectivity status.

### RT-3: Device re-enters advertising after failure so the user can retry without a power cycle
- Asserts: After a failed setup attempt, the device resumes BLE advertising within a defined time window, without needing a manual power cycle.
- Why: If the device gets stuck in a non-advertising state after a failure, the customer cannot simply reopen the app and try again. They would have to unplug and replug the device, which is a poor experience and a common source of support calls.
- How: Force a setup failure (for example, using RT-4's scenarios below), then scan for the device's BLE advertisement and confirm it reappears within the expected time window, and that the app can successfully reconnect and start a new provisioning attempt.

### RT-4: Force a wrong password and a dead DHCP server, assert distinguishable error states
- Asserts: The reported status or error code is different between the "wrong password" scenario and the "DHCP server unresponsive" scenario, so the two failures can be told apart.
- Why: Ties back to the "incorrect password" risk from Part 1. A customer, or a support agent, needs to know whether the problem is a typo in the password or a network/router issue, since the fix is completely different. A single generic "setup failed" message for both hides this and makes the problem harder to diagnose.
- How: Run two separate provisioning attempts, one with an incorrect Wi-Fi password and one against a DHCP server that never responds. Capture the resulting status or error code from each run and confirm they are distinct and each one correctly maps back to its actual root cause.

---

# Part 4 – System Thinking

## Goal

Automate BLE and Wi-Fi onboarding validation in CI, so that every firmware or app change can be checked against real devices going through the full BLE-to-Wi-Fi setup flow, including messy conditions like weak signal, dropped BLE connections, and slow DHCP.

## How the pieces fit together

**Linux systems**
A Linux test controller acts as the "phone" in this setup. It runs BLE tools (for example, `bluetoothctl` or a Python library like `bleak`) to connect to the device over BLE and send Wi-Fi credentials, the same way the mobile app would. It also runs the pytest suite, and can be used to trigger and time each step of the onboarding flow. This machine sits close to the test devices so BLE range is not an issue during testing.

**Hardware test equipment**
Real hardware is needed here because the exact failure in Part 3 is something a mocked JSON file cannot reproduce on its own. Useful equipment includes:
- The physical audio devices themselves, ideally more than one, to also test the "multiple devices onboarding simultaneously" scenario.
- A BLE-capable adapter or tool on the Linux test controller, to act as the "phone" side of the BLE connection.
- A programmable RF attenuator, to simulate weak Wi-Fi signal in a controlled, repeatable way.
- A smart power switch (PDU), to force a device reboot at a specific point during setup.

**Controlled network infrastructure**
A separate, isolated Wi-Fi network and router are needed so tests are repeatable and not affected by other traffic. This should allow:
- Changing or renaming the SSID on demand, to test the "SSID changes" scenario.
- Adding an artificial delay to DHCP responses, to test the "DHCP delays" scenario and the exact failure pattern from Part 3.
- Blocking or limiting DHCP responses entirely for short periods, to test timeout and retry behavior.

**GitHub Actions**
GitHub Actions defines and triggers the automated workflow, but the real devices, BLE tools, and controlled network all live in our lab, not on GitHub's own servers. Because of this, the workflow would run on a self hosted GitHub Actions runner, a machine we control that can reach the lab's BLE and Wi-Fi test setup (likely the same Linux test controller mentioned above). The workflow would:
1. Trigger on a pull request or on a schedule, for example nightly.
2. Reset the device(s) to a clean, unprovisioned state, using the smart power switch if needed.
3. Run the BLE-to-Wi-Fi onboarding flow against real hardware, covering scenarios like a normal setup, a forced BLE disconnect during credential transfer, and a delayed DHCP response.
4. Run the pytest suite against the resulting connectivity status, similar to the mocked-data tests in Part 2, but backed by real onboarding attempts.
5. Save logs, timing data, and any packet captures as build artifacts if a run fails.
6. Report pass or fail back to the pull request, so failures are caught before code changes reach customers.

## Why this matters

The mocked, JSON based tests from Part 2 are fast and useful for checking the validation logic itself on every commit. The hardware based CI pipeline described here is slower, and would likely run less often (for example nightly, or before a release), but it is the layer that actually proves the full BLE-to-Wi-Fi handoff works correctly under real, messy conditions, including the exact kind of timing issue uncovered in Part 3.
