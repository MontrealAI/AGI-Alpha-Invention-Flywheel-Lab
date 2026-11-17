"""Film real results from a pinned Pairing Lab recipient ZIP. See README.md for dependencies."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import tempfile
import textwrap
from zipfile import ZipFile

from PIL import Image, ImageDraw, ImageFont

ZIP_SHA = "cfe351fe647ee1738a8069e3c1752e739ec0642467c9b1fe075ba5a508a52d62"
WIDTH, HEIGHT = 1600, 900
SANS = "/usr/share/fonts/truetype/open-sans/OpenSans-Regular.ttf"
MEDIUM = "/usr/share/fonts/truetype/open-sans/OpenSans-Semibold.ttf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
SERIF = "/usr/share/texmf/fonts/opentype/public/lm/lmroman12-regular.otf"
GOLD, CREAM, DUST = "#ecd197", "#f9f2e8", "#c8bfd2"
GREEN, ROSE = "#9cdec1", "#efaab4"


def capture(root, args):
    command = ["python3", "-B", *args]
    proc = subprocess.run(command, cwd=root, capture_output=True, text=True, check=True)
    return {"command": shlex.join(command), "exit_code": proc.returncode,
            "stdout": proc.stdout, "stderr": proc.stderr}


def title(draw, at, value, size, face=SANS, fill=CREAM):
    font = ImageFont.truetype(face, size)
    if draw.textlength(value, font=font) + at[0] > WIDTH - 30:
        raise ValueError(f"Text does not fit screen: {value}")
    draw.text(at, value, font=font, fill=fill, anchor="lt")


def scene(index, heading, subhead, number, qualifier, note, command, actual, duration, tone=GOLD):
    image = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(image)
    # Static light field. Each scene holds a stable, readable original observation.
    for y in range(HEIGHT):
        t = y / HEIGHT
        color = tuple(round(a * (1 - t) + b * t) for a, b in zip((26, 20, 39), (15, 13, 23)))
        draw.line((0, y, WIDTH, y), fill=color)
    margin = 80
    title(draw, (margin, 48), "MONTREAL.AI   ×   QUEBEC.AI", 20, MEDIUM, GOLD)
    title(draw, (990, 48), "FRONTIER Ω IGNITION   /   PAIRING LAB", 21, MEDIUM)
    draw.line((margin, 94, WIDTH-margin, 94), fill="#5b4b63")
    title(draw, (margin, 136), heading, 65, SERIF)
    title(draw, (margin, 226), subhead, 27, SANS, DUST)
    draw.rounded_rectangle((margin, 316, 690, 698), radius=12, fill="#221c2d", outline="#564a60", width=1)
    title(draw, (116, 357), qualifier, 22, MEDIUM, tone)
    title(draw, (112, 417), number, 104, SERIF)
    for n, line in enumerate(note):
        title(draw, (118, 566+n*42), line, 23, SANS, DUST)
    draw.rounded_rectangle((719, 316, 1520, 698), radius=12, fill="#101018", outline="#514657", width=1)
    title(draw, (754, 349), "RECIPIENT COMMAND", 18, MEDIUM, GOLD)
    y = 398
    for line in command:
        title(draw, (754, y), line, 21, MONO)
        y += 34
    draw.line((754, y+8, 1482, y+8), fill="#463d4e")
    title(draw, (754, y+30), "RECORDED OUTPUT  /  SELECTED LINES", 17, MEDIUM, "#ababbb")
    y += 75
    for line in actual:
        title(draw, (754, y), line, 20, MONO, tone)
        y += 33
    draw.line((margin, 751, WIDTH-margin, 751), fill="#55465b")
    title(draw, (margin, 781), "Recipient execution  ·  Reanalysis of previously graded runs", 22, MEDIUM)
    title(draw, (margin, 825), "Pairing Matters  /  Zhao, Poskitt & Lo  /  Figshare v1  /  CC BY 4.0", 18, SANS, DUST)
    for i in range(4):
        x = 1403 + 30*i
        draw.rounded_rectangle((x, 790, x+21, 795), radius=2, fill=GOLD if i <= index else "#4d4355")
    return image, duration


def output_excerpt(record):
    lines = record["stdout"].splitlines()
    start = lines.index('  "audit": {')
    end = next(i for i in range(start, len(lines)) if lines[i] == "  },")
    return [s.strip() for s in lines[start:end+1]]


def run(archive, output, transcript, frames=None):
    if hashlib.sha256(archive.read_bytes()).hexdigest() != ZIP_SHA:
        raise ValueError("Recipient ZIP bytes differ from the pinned release")
    with tempfile.TemporaryDirectory() as temp:
        work = Path(temp)
        receiver = work / "recipient"
        with ZipFile(archive) as bundle:
            bundle.extractall(receiver)  # Archive identity verified before extraction.
        records = {
            "single": capture(receiver, ["pairing_lab.py", "--width", "1", "--summary"]),
            "pair": capture(receiver, ["pairing_lab.py", "--summary"]),
            "successor": capture(receiver, ["pairing_lab.py", "--model", "devstral", "--repository", "django__django", "--summary"]),
            "sql": capture(receiver, ["qualify.py", "--check", "receipt.json"]),
            "tests": capture(receiver, ["-m", "unittest", "discover", "-v"])}
        checks = json.loads((receiver/"receipt.json").read_text())
        single, pair, nxt = [json.loads(records[k]["stdout"]) for k in ("single", "pair", "successor")]
        if (single["audit"], pair["audit"], nxt["audit"]) != tuple(checks["arms"][key]["audit"] for key in ("2000000/1","2000000/2","successor")):
            raise ValueError("Filmed outputs and registered arms disagree")
        assert pair["qualifies"] and not nxt["budget_pass"] and not nxt["resolution_pass"]
        assert len(checks["arms"]) == 7 and all(r["conventional_sql"]["agreement"] for r in checks["arms"].values())
        transcript.write_text(json.dumps({"archive_sha256": ZIP_SHA, "records": records}, indent=2) + "\n")
        audit = lambda obj: f"{obj['audit']['solved']} / {obj['audit']['tasks']}"
        delta = pair["audit"]["tokens"] - single["audit"]["tokens"]
        sql_message = records["sql"]["stdout"].strip()
        assert sql_message == "Matched every registered receipt and both split scores for every allowed policy."
        cards = [
            scene(0, "Which coding agents merit a private pilot?",
                  "Start with 1,800 published runs. Select on 60 issues and audit once on 40 held-out issues.",
                  audit(single), "SELECTED SINGLE STACK",
                  ["Qwen3-Coder-Next with Agentless.", "The 45% resolution floor is missed."],
                  [records["single"]["command"]], output_excerpt(records["single"]), 8),
            scene(1, "A second stack resolves two more issues.",
                  "The paired policy adds GLM-4.7-Flash with AutoCodeRover. Both attempts count toward the budget.",
                  audit(pair), "TWO-STACK POLICY",
                  [f"{delta:,} more charged tokens", "than the selected single stack."],
                  [records["pair"]["command"]], output_excerpt(records["pair"]), 10, GREEN),
            scene(2, "The same instrument rejects a new policy.",
                  "Limit the audit to Devstral on Django. Keep the 45% floor and the two-million-token average cap.",
                  audit(nxt), "DEVSTRAL-ONLY DJANGO AUDIT",
                  [f"{nxt['audit']['tokens']/nxt['audit']['tasks']/1e6:.2f}M tokens per issue.", "Both acceptance thresholds were missed."],
                  ["python3 -B pairing_lab.py --model devstral", "  --repository django__django --summary"],
                  [line.strip() for line in records["successor"]["stdout"].splitlines() if any(s in line for s in ('"verdict"', '"budget_pass"', '"resolution_pass"'))], 10, ROSE),
            scene(3, "Independent SQL reproduces the decisions.",
                  "The recipient kit recomputes the registered results offline. The next test is a prospective private pilot.",
                  "7 / 7", "REGISTERED COMPARISONS",
                  ["Archived model outcomes were reanalyzed.", "No model inference was rerun."],
                  [records["sql"]["command"]],
                  textwrap.wrap(sql_message, width=50), 8, GREEN)]
        concat = []
        for i, (im, seconds) in enumerate(cards):
            png = work / f"scene{i}.png"
            im.save(png)
            if frames:
                frames.mkdir(exist_ok=True, parents=True)
                im.save(frames/png.name)
            clip = work/f"clip{i}.mp4"
            subprocess.run(["ffmpeg","-v","error","-y","-loop","1","-framerate","24","-i",str(png),"-t",str(seconds),
                            "-vf",f"fade=in:d=0.20,fade=out:st={seconds-.20}:d=0.20,format=yuv420p",
                            "-c:v","libx264","-threads","2","-preset","veryfast","-tune","stillimage",
                            "-crf","18","-an",str(clip)],check=True)
            concat.append(f"file '{clip.name}'")
        listing = work/"clips.txt"
        listing.write_text("\n".join(concat)+"\n")
        subprocess.run(["ffmpeg","-v","error","-y","-f","concat","-safe","0","-i",str(listing),"-c","copy",
                        "-movflags","+faststart",str(output)],check=True)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("zip", type=Path)
    cli.add_argument("output", type=Path)
    cli.add_argument("--transcript", type=Path, default=Path("transcript.json"))
    cli.add_argument("--frames", type=Path)
    a = cli.parse_args()
    run(a.zip.resolve(), a.output.resolve(), a.transcript.resolve(), a.frames)
