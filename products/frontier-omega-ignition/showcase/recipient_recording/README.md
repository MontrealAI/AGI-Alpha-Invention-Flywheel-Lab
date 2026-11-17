# Pairing Lab recipient demonstration

The 36-second English-captioned film shows observations from four commands executed in a fresh extraction of the public recipient kit. The accompanying [transcript](transcript.json) retains the complete commands, exit codes, standard output and test output, including the ten recipient tests. Captions identify the retrospective study, the successful two-stack policy, the failed Devstral-only Django audit and the independent exhaustive SQL comparison. The study reanalyzes published grader outcomes. No private software issues or live model inference are involved.

From the product directory, build the pinned ZIP and render the film on Linux. The renderer uses Python, Pillow, FFmpeg with libx264 and the Open Sans, Latin Modern Roman and DejaVu Sans Mono system fonts. The standalone recipient kit uses Python's standard library.

```sh
python3 flagship/package.py /tmp/Pairing_Lab.zip
python3 showcase/recipient_recording/make.py /tmp/Pairing_Lab.zip /tmp/Pairing_Lab_Demonstration.mp4 --transcript /tmp/recipient-transcript.json
ffprobe -v error -show_format -show_streams /tmp/Pairing_Lab_Demonstration.mp4
```

The intended public recipient archive has SHA-256 `cfe351fe647ee1738a8069e3c1752e739ec0642467c9b1fe075ba5a508a52d62`. Video encoding and the measured test duration can differ across toolchain versions. [Study, attribution and recipient commands](../../flagship/README.md) · [Paired observations, Figshare v1](https://doi.org/10.6084/m9.figshare.34744362.v1)
