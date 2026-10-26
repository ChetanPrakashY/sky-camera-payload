# Ground night-sky trial: plan and procedure

SKY-TP-001 rev 0.1, 27 October 2026
# 1 Objectives

1. Characterise the real camera (gain, read noise, dark current, saturation) and compare with the values
   assumed in SKY-PDR-001.
2. Run the complete chain on real sky: capture, on-board processing, telemetry over the radio, decoding.
3. Verify PL-001 to PL-004 and PL-008 under real conditions.

# 2 Success criteria

Fixed before the trial; the trial report states each one as met or not met.

| ID | Criterion | Requirement |
|---|---|---|
| S-1 | All characterisation quantities measured, with their uncertainty | SKY-PDR-001 section 7 |
| S-2 | At least 95% of catalogue stars brighter than the PL-001 limit detected in at least 10 frames | PL-001 |
| S-3 | Centroids agree with catalogue positions (after a plate solution) to 0.3 px rms | PL-002 |
| S-4 | At least one satellite streak detected, with its direction within 1 degree of the predicted track | PL-003 |
| S-5 | Every science frame has PPS lock | PL-004 |
| S-6 | No packet with a bad CRC accepted by the ground decoder | PL-008 |

# 3 Site, date and window

A dark site with a clear view to the south and overhead. The session starts at the end of nautical twilight
in the evening (sun 12 degrees below the horizon) and runs for 90 minutes, when low-orbit satellites are still
sunlit. Pass predictions for the night are prepared beforehand from public orbital elements.

# 4 Roles

| Role | Responsibility |
|---|---|
| Test lead | runs the procedure, decides go/no-go, keeps the log |
| Operator | camera, focus and the on-board computer |
| Ground station | radio, decoder, live check of incoming packets |

# 5 Equipment checklist

- [ ] payload with lens, lens cap and dew heater
- [ ] tripod and mount, spirit level
- [ ] charged battery (voltage above 8.0 V at rest), spare battery
- [ ] GNSS antenna with a clear sky view
- [ ] radio pair, ground laptop with the decoder
- [ ] white screen or tablet with a white image for flats
- [ ] red torch, log sheet, printed procedure
- [ ] storage card formatted and empty, spare card

# 6 Procedure

Each step is signed off on the log sheet. A step that fails is recorded as a deviation; the test lead decides
whether to continue.

1. **Set up.** Level the mount, attach the GNSS antenna, power the payload. Record battery voltage.
2. **Darks.** Lens cap on. Take 16 darks at the science exposure (0.2 s) and darks at 0.05, 0.1, 0.2, 0.4 and
   0.8 s. Record the sensor temperature.
3. **Flats and photon-transfer pairs.** Lens cap off, lens pointed at the evenly lit white screen, slightly out
   of focus. Take 16 flats, then pairs at increasing brightness until the sensor saturates.
4. **Timing.** Confirm PPS lock on the computer; record the offset reported by the PPS driver.
5. **Focus.** Point at a bright star; adjust focus until the source size reported by procframe is smallest.
   Lock the focus ring.
6. **Science.** Point at the predicted crossing region of the next satellite pass. Start the capture sequence
   (0.2 s every 2 s). The ground station confirms packets arriving with good CRCs. Continue through every
   predicted pass in the window.
7. **End darks.** Lens cap on, 16 darks at 0.2 s, to check that the dark level did not drift.
8. **Data.** Copy the storage card twice, compute checksums of both copies, log them.

# 7 Go / no-go

Stop or do not start if: cloud covers more than half the sky, the lens shows dew that the heater does not clear
within 10 minutes, the battery falls below 7.0 V, or PPS lock is lost for more than 5 minutes.

# 8 Safety

Work in pairs. Keep the battery in a fire-resistant bag when charging. Do not leave cables across paths in the
dark.

# 9 Report

The trial report (SKY-TR-001 format) gives: what was run, every deviation from this procedure, the result
for each success criterion, the characterisation results, and the actions that follow.
