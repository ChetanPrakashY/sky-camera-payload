---
id: SKY-ICD-001
title: Sky-camera payload: interface control document
revision: 0.1
date: 27 October 2026
status: Draft for review
author: Chetan Prakash
history: 0.1 / 27 Oct 2026 / First issue
---
# 1 Scope

This document fixes every interface of the sky-camera payload: the telemetry packet sent to the ground, the
files written on board, and the electrical connections between units. Software on both ends is written
against this document; a change to any table here needs a new revision.

# 2 Telemetry packet

One packet per frame. All multi-byte fields are big-endian (network order). Packets are sent back to back
on the radio link; the receiver finds each one by its sync marker and accepts it only if the CRC matches.

| Offset (bytes) | Size | Field | Type | Description |
|---|---|---|---|---|
| 0 | 4 | Sync marker | constant | 0x1ACFFC1D, the CCSDS attached sync marker |
| 4 | 1 | Version | uint8 | format version, currently 1 |
| 5 | 4 | Frame index | uint32 | counts frames since power-on |
| 9 | 4 | Time, seconds | uint32 | GPS time of the exposure start, whole seconds |
| 13 | 4 | Time, microseconds | uint32 | fractional part, 0 to 999 999 |
| 17 | 2 | N | uint16 | number of detection records that follow, 0 to 200 |
| 19 | 16 x N | Detections | record | section 2.1, brightest first |
| 19 + 16N | 2 | CRC | uint16 | CRC-16/CCITT-FALSE over bytes 4 to 18 + 16N |

Packet length is 21 + 16N bytes.

## 2.1 Detection record

| Offset | Size | Field | Type | Scale | Description |
|---|---|---|---|---|---|
| 0 | 2 | x | uint16 | 1/32 px | centroid column, from the left edge |
| 2 | 2 | y | uint16 | 1/32 px | centroid row, from the top edge |
| 4 | 4 | Flux | uint32 | 1 DN | background-subtracted sum over the source |
| 8 | 2 | Angle | int16 | 0.01 deg | major-axis angle from the +x axis, 0 to 180 |
| 10 | 2 | Length | uint16 | 0.1 px | sqrt(12 x major-axis variance): the length of a uniform line |
| 12 | 2 | Pixels | uint16 | 1 | pixels above threshold |
| 14 | 1 | Flags | uint8 | bits | bit 0 streak, bit 1 touches the frame edge, bit 2 contains a saturated pixel |
| 15 | 1 | Spare | uint8 | | 0 |

## 2.2 CRC

CRC-16/CCITT-FALSE: polynomial 0x1021, initial value 0xFFFF, no reflection, no final XOR. Check value: the
ASCII string "123456789" gives 0x29B1. It detects any single-bit error, any odd number of bit errors (the
polynomial has x + 1 as a factor) and any error burst of 16 bits or less.

# 3 Files on board

## 3.1 Raw frames

One file per frame, `<kind>_<n>.raw`: width x height unsigned 16-bit little-endian pixels, row by row, top
row first. The sensor delivers 12-bit values, so the top four bits are zero. The black level is 256 DN.

## 3.2 Frame metadata

`frames.jsonl`, one JSON object per line, one line per frame:

| Field | Type | Description |
|---|---|---|
| file | string | path of the raw file, relative to the session folder |
| width, height | integer | pixels |
| t_exp | number | exposure time, seconds |
| kind | string | dark, flat, ptc, darkramp or science |
| time_gps | number | science frames: GPS time of the exposure start, seconds |
| index | integer | science frames: frame index, as in the telemetry packet |

## 3.3 Calibration products

In `calib/`, all little-endian, same size as a frame:

| File | Type | Content |
|---|---|---|
| dark.f32 | float32 | median of 16 darks at the science exposure time, DN |
| flat.f32 | float32 | median of 16 flats minus the dark, normalised to median 1 |
| badpix.u8 | uint8 | 1 for a hot or dead pixel, else 0 |

# 4 Electrical interfaces

Values marked TBC are confirmed from the datasheets when the units are bought.

| Interface | From | To | Signal | Notes |
|---|---|---|---|---|
| Camera | camera | on-board computer | MIPI CSI-2, 2 lanes | 15-pin ribbon cable (TBC) |
| GNSS data | GNSS receiver | on-board computer | UART, 3.3 V, 9600 baud 8N1 (TBC) | NMEA sentences |
| PPS | GNSS receiver | on-board computer GPIO | 3.3 V pulse, rising edge on the UTC second (TBC) | edge time-stamped by the kernel PPS driver |
| IMU | IMU | on-board computer | I2C, 3.3 V, 400 kHz | address set by the module (TBC) |
| Telemetry | on-board computer | radio | UART, 3.3 V, 57600 baud 8N1 (TBC) | carries the packets of section 2 |
| Power | battery | buck converter | 7.4 V nominal | fused |
| Power | buck converter | computer, camera, radio | 5 V | |
| Power | LDO | GNSS, IMU | 3.3 V | |

# 5 Timing

The exposure start is time-stamped against the last PPS edge, which marks the UTC second to well under a
microsecond. PL-004 asks for 1 ms: from low Earth orbit at about 7 km/s ground speed, 1 ms of timing error
moves a measured satellite position by about 7 m along its track. Frames taken without PPS lock are flagged in
the metadata (risk R-05).
