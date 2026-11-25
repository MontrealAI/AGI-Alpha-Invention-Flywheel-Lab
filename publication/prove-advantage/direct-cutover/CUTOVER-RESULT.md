# Terra continuity decision from direct included Codex

Research beneficiary: MONTREAL.AI. The preregistered decision concerns two Montréal-area monitoring points before NASA Terra stops new science observations on 1 December 2026. A useful direct deliverable is an executable feasibility check that prevents silently replacing a historic time series with untested input.

**Decision: preserve the historic Terra series and abstain from a matched cutover at both studied points.**

| Verified input | Morgan Arboretum | Mont-Saint-Bruno |
| --- | ---: | ---: |
| Terra calendar coverage in each registered year | 17/17 | 17/17 |
| Common Terra–Suomi 2024 windows | 1/17 | 1/17 |
| Common Terra–Suomi held 2025 windows | 0/17 | 0/17 |
| Known NOAA-21 exact granule | CMR returned metadata | CMR returned metadata |
| Actual anonymous NOAA-21 bytes | NASA Earthdata sign-in redirect | NASA Earthdata sign-in redirect |

ORNL's Suomi endpoint stopped at 24 May 2024 at both points. The sole joint 2024 window returned both actual pixel packets, with neither pair passing the registered strict QA configuration. Other portals report longer public product coverage; these results concern this anonymous access route. The NOAA-21 product was absent from ORNL. The exact data archive returned HTTP 303 on HEAD, and its documented redirected HEAD exposed a 32,134,622-byte object. A separate bounded GET requested 64 actual bytes and returned HTTP 302 toward NASA Earthdata login. No account sign-in was attempted. Distribution metadata does not justify imputing unavailable pixel measurements.

Run `python cutover_preflight.py result.json` to repeat the public access and composite overlap check (Python standard library). A comparison of raw replacement, median calibration and band-affine calibration requires the full pixel series and is withheld. Actual repeat use on two distinct public locations yielded the same scientifically necessary denial. No post-cutover measurement, source replacement, accepted business demand, or revenue occurred.

The recorded repeat took 25.6977 seconds wall and 0.078 seconds in-process CPU. Included Codex, the public evidence read and local Python were used. Actual provider token use, paid subscription allocation and complete economic cost were unavailable. No paid inference API, sign-in, purchase, external messaging or production operation was used.

Sources, blind date cutoff and the minimum accepted outcome appear in [the registration](REGISTRATION.md). A material next test requires existing approved access to a complete NOAA-21/Terra overlap and the monitoring beneficiary's acceptance contract. NASA already recommended transition in 2025, and cross-spectral harmonization was published years earlier. Novelty lies in this recent cutover and actual source feasibility for these distinct sites; no method or product superiority was established.
