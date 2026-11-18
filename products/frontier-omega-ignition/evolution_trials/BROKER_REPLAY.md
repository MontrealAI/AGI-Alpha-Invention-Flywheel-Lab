# Check a ZTF persistence notice

Given a notice with an object, passband, baseline and trigger, this receiver finds the first eligible later detection in ALeRCE's ZTF archive and measures its signed change from the baseline. It requires positive public-program difference photometry on the same filter, field, readout channel and reference processing ID.

## Replay the two October notices

Run these commands in the directory containing this guide. The offline check uses Python 3.9 or newer and verifies the original response bytes along with both decisions.

```sh
python3 broker_control.py --check
python3 broker_control.py
```

| ZTF26acbezdh band | First later detection | Baseline to repeat | Formal error | Result |
|---|---|---:|---:|---|
| g | 3587249065815015015 | −1.069727 mag | 0.056139 mag | Persisted |
| r | 3587389715815015003 | −0.751183 mag | 0.064913 mag | Persisted |

Each first repeat occurred on October 28, within three days of the October 26 issue midnight. Both confirm the original brightening of the positive difference signal. The signed displacement must reach both 0.20 mag and twice the quadrature error. In r, substituting the Fink notice's rounded baseline for the original ZTF value changes the unrounded answer by 0.0000001073 mag, which crosses a six-decimal rounding boundary.

## Run a different notice

The supplied example uses the public object ZTF24aalougs, also known as 2024ijp. It tests one r-band notice issued in retrospective replay on May 8, 2024. The complete bounded index returned two eligible later detections. The earlier detection, 2684267954115015003, gave a change of −0.653692 ± 0.142021 mag. [TNS object record](https://www.wis-tns.org/object/2024ijp)

```sh
python3 broker_control.py --notice broker_sources/alternate-notice.json --live
```

To use your own target, copy the example JSON and enter its ZTF object ID, UTC issue midnight, deadline, and the original baseline and trigger candidate IDs for g, r, or both. The registered maximum window is three days. For a shorter cohort window, supply its exclusive cutoff. The code checks the issue thresholds using the original packet photometry.

To keep your own replay offline, print the query URLs, save the original bounded VOTable, then save one original packet for every indexed candidate. The second command prints URLs for every returned detection. Name the packet files `CANDID.avro` or `CANDID.avro.gz`.

```sh
python3 broker_control.py --notice notice.json --queries
python3 broker_control.py --notice notice.json --queries --index index.vot
python3 broker_control.py --notice notice.json --index index.vot --packets packets/
```

A missing indexed packet, failed query or truncated index leaves the case unresolved. A coverage gap means that a complete response for the closed three-day archive window contained no qualifying later measurement. The archive records observation times. Establishing when each broker made an alert available requires additional timestamps.

The October live control transferred 531,584 response bytes in seven public GETs and took 11.147 seconds of elapsed time and 0.035 seconds of client CPU. The two brokers carry the same telescope's underlying photometry. Source identities, per-request measurements, signed calculations, public access documentation and precision conventions are in [BROKER_CONTROL.json](BROKER_CONTROL.json).
