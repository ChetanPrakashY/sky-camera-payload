"""Decode the payload's telemetry packets (format: docs/src/ICD.md).

    python parse_tm.py PACKETS            # prints a summary, writes PACKETS.csv
"""
import struct
import sys

ASM = bytes.fromhex("1ACFFC1D")
HEAD = struct.Struct(">BIIIH")      # version, frame index, GPS seconds, microseconds, detection count
DET = struct.Struct(">HHIhHHBB")    # x*32, y*32, flux, angle*100, length*10, npix, flags, spare


def crc16_ccitt(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def packets(blob):
    """Yield (header, detections) for every packet with a good CRC; count the bad ones."""
    i, bad = 0, 0
    while (i := blob.find(ASM, i)) >= 0:
        body = i + 4
        if body + HEAD.size > len(blob):
            break
        ver, idx, sec, usec, n = HEAD.unpack_from(blob, body)
        end = body + HEAD.size + DET.size * n
        if end + 2 > len(blob) or crc16_ccitt(blob[body:end]) != struct.unpack_from(">H", blob, end)[0]:
            bad += 1
            i += 1                      # resynchronise on the next marker
            continue
        dets = []
        for k in range(n):
            x, y, flux, ang, length, npix, flags, _ = DET.unpack_from(blob, body + HEAD.size + DET.size * k)
            dets.append(dict(x=x / 32, y=y / 32, flux_dn=flux, angle_deg=ang / 100, length_px=length / 10,
                             npix=npix, streak=bool(flags & 1), edge=bool(flags & 2), saturated=bool(flags & 4)))
        yield dict(version=ver, frame=idx, time_gps=sec + usec * 1e-6, n=n), dets
        i = end + 2
    packets.bad = bad


if __name__ == "__main__":
    blob = open(sys.argv[1], "rb").read()
    rows = []
    for head, dets in packets(blob):
        print(f"frame {head['frame']:3d}  t = {head['time_gps']:.6f}  {head['n']:3d} sources, "
              f"{sum(d['streak'] for d in dets)} streak(s)")
        rows += [dict(frame=head["frame"], time_gps=head["time_gps"], **d) for d in dets]
    print(f"{len(blob)} bytes, packets with a bad CRC: {packets.bad}")
    if rows:
        with open(sys.argv[1] + ".csv", "w") as f:
            f.write(",".join(rows[0]) + "\n")
            for r in rows:
                f.write(",".join(str(v) for v in r.values()) + "\n")
