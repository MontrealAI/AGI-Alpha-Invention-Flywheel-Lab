# Focused dependency check: varied masks paired with manufactured geometry

2026-11-02, source/schema only. No outcome arrays/images inspected, fitted or evaluated.

**YES:** https://doi.org/10.18434/mds2-2950 provides random grayscale masks paired with independent laser-scanning confocal measurements of actual single-layer prints. This resolves the AMBench single-pattern identification limitation, but requires a separately frozen experimental scope. It does not establish cross-printer transfer, multilayer functionality, or physical acceptance of newly invented masks.

## Provenance and compact access

Metadata https://data.nist.gov/rmm/records/mds2-2950 version1.0.1; README version1.0.0. Release1.0.1 only adds additive-manufacturing collection membership. License https://www.nist.gov/open/license . Local source copies: `2950.json`, `2950_README.txt`.

Base URL: https://data.nist.gov/od/ds/mds2-2950/

| File | Bytes | SHA256 |
|---|---:|---|
| training_pairs.zip |441187839|75484c53e25562bcc9efb4689017516ee88caad6e72571ae5479cb691eedfa71|
| photomasks.zip |436393|de1483c9c50a79b5c510eaec104ae3a9eb0f54dad6c5c446063334d1078a95c4|
| modified_pix2pix.zip |993046483|327ae7ad38e5c7fb1119377b7f2677d929628a2df556bf907fe49515efea3860|
| Jupyter_notebooks.zip |31738708|cdd978623ca8a85e8cc00e5fed4df49a1829ec9889b450f1b5b10149eb96ea5e|
| raw_print_data.zip |2317242659|06020d4693add77cb41119f50cb69a9e4e2062c50973bc55ae85ddb1a0c56b43|

Only metadata, README, paper and ZIP directory fetched. HTTP206 range support verified on training_pairs.zip. Central directory178144bytes starts441009673; EOCD last22bytes. `2950_entries.json` records1570 names, compressed/uncompressed sizes and local header offsets. All1444PNG members total4375159 compressed bytes and lie in contiguous payload region436549007..441009672 (approximately4.46MB). These can be fetched after freeze without downloading441MB. Individual CRC metadata and sample hashes should be recorded during extraction; whole-archive SHA cannot be independently checked from partial ranges.

## Actual pairing and holdout units

Five physical slides/masks:24676,33040,33986,51497,77989. Four microscopy columns C1..C4 per slide. Parent random mask320x240; full printer1280x720. Each paired PNG128high x256wide contains aligned scaled8x8 mask and print. Mask0..255; print0..255 corresponds0..280.83µm. Native .vk4 data readable with open Gwyddion/vk4 Python driver but not required for first processed-data test.

Published split and actual ZIP directory: `training_pairs/train/0000.png` onward1030; `training_pairs/val/train/0000.png` onward114; `training_pairs/test/0000.png` onward300. Test is complete independently printed slide51497. README mistakenly says1130train; paper and actualdirectory1030. Training/validation draw random patches from otherfour slides and exclude full-intensity fiducials. Do not claim patch-level independence or new grouped validation from anonymous training PNG filenames. NPY names preserve slide+column, but are larger. The single held-out slide permits prospective within-machine physical-transfer validation, not multiple-machine validation.

## Strong existing baseline

Primary paper https://doi.org/10.1002/smll.202301987 ; public NIST manuscript https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=936540 . Local Small2023.pdf/.txt. Existing pix2pix conditional GAN and nonadversarial U-Net with L1/MSE losses already predict arbitrary grayscale-mask geometry. Published best compromise:128x128 inputs/outputs, batch8, single-layer larger-patch discriminator, paired horizontal/vertical mirror augmentation,5..200epochs; reduced10/100training-pair versions also studied. Full existing baseline must not be replaced rhetorically by pointwise Jacobs law alone. Source code supplied in modified_pix2pix archive. Published method reports scale-up and antialiasing; neither novel-mask inverse prediction nor ordinary machine-learning training is a new capability by itself.

## Scope discipline

A new inverse mask evaluated by its own forward model is model-assumption output, not manufactured truth. Restrict physical acceptance to exact previously printed masks selected prospectively against withheld measured geometry, or leave fresh-mask physical acceptance explicitly unresolved. Define target requirements independently of the hidden measured outputs. Strong ordinary alternative is existing pix2pix/U-Net plus finite recipe search or direct fabrication/calibration. Do not claim AI-specific advantage, real cost savings, sale acceptance, or general machine transfer from this dataset alone.

## Completed bounded baseline/protocol extension (20:27 UTC)

No measured/prediction image or numeric outcome viewed. Source-code cells were separated from notebooks without displaying saved cell outputs.

The author's baseline archive central directory is8684131bytes at984362330,50862members. Saved metadata `2950_baseline_entries.json` includes CRC32,compressionmethod,offset,size. No .pth/.pt checkpoints. HOWEVER frozen200epoch predictions are available: `2950_baseline_test200_entries.json` lists1800 non-color PNG files (300predictions+300input masks for each of cGAN,L1,MSE). Matching IDs must be checked after freeze, not assumed. Exact member roots:
- `modified_pix2pix/results/pix2pixnetD1L_refs200epoch/test_200/images/`: range411344689..412538502,600PNGs,total1127214compressedbytes.
- `modified_pix2pix/results/L1netD1L_refs200epoch/test_200/images/`: range96048114..97046206,600PNGs,total934493compressedbytes.
- `modified_pix2pix/results/MSEnetD1L_refs200epoch/test_200/images/`: range230695849..231748189,600PNGs,total988141compressedbytes.
Names `0000_fake.png` to`0299_fake.png`, corresponding`_real.png`. `models/test_model.py` confirms real=inputA and fake=G(real), NOT measuredheight. Groundtruth remains pairedPNGheight. `util/util.py` tensor2im maps[-1,1] to uint8[0,255]. Check exact input equality, shape and scaling prospectively before admitting these as comparable controls. Stored test_opt.txt is later large-mask/latest run and NOT evidence of200epoch128² options.

Source protocol pinned via `2950_code_manifest.json`, `2950_protocol_manifest.json`, `2950_preprocess_manifest.json`, `2950_pair_manifest.json`. Small files in`baseline_code/`; stripped code-only notebooks saved as`.source.py`. Reuse data under NISTopenlicense, supplied implementation carries Jun-YanZhu/TaesungPark2017 BSD-style notice (retain exactLICENSE). environment.yml pins Python3.8/PyTorch1.8.1/torchvision0.9.1/etc, whereas paper saysPyTorch1.13.1; do not claim exact executable environment reproduction from template alone. No package installation/training performed.

Exact geometry and orientation source chain:
- `generate_print_masks_and_files.source.py`: ACUltra,1280×720,pixel_size80µm.
- `read_lscm_data_and_align_patterns.source.py`: submask_dimension8,padding_required=floor(8/2)=4,partition16.
- `process_imgs_for_pix2pix.source.py`: crop=False,output_size128,nearest-neighbor mask resize, print-image resize; exports masks toA and prints toB, test51497_C1b..C4b, trainingotherfourIDs.
- `datasets/combine_A_and_B.py`: concatenate([im_A,im_B],axis1); hence maskLEFT,heightRIGHT.
- Center[32:96,32:96] of each128²half is intended8×8 nativepattern; eachnativepixel maps8outputpixels. This is preprocessing-supported geometric correspondence, not an inspected result.

Training-derived maximum rescales height before conversion; README gives280.83µm. Preprocessing uses training(max) for test normalization, no observed test-derived scaling. Some notebook exploratory commands are not a fully executable provenance DAG; exact archival image identity still requires independent byte-level acceptance.
