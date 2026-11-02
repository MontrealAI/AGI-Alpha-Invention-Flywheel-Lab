# Data access and fallback boundary

Metadata-only check: 2 November 2026. No measurement vectors were retrieved for this note.

## Compact measured fallback

[NIST REMI](https://github.com/usnistgov/remi/tree/596b04435fb577175264a70c4434f5539b809510/data/Combinatorial%20Libraries/Fe-Co-Ni), commit `596b04435fb577175264a70c4434f5539b809510`, contains `data/Combinatorial Libraries/Fe-Co-Ni/FeCoNi_benchmark_dataset_220501a.mat`: **289,480 bytes**, Git blob `e506db115d522d62618042abead7df2695ccf13e`. Its description specifies matched rows: `C` composition, `XRD` diffraction, `TTH` angles, `Coer` coercivity (mT), `Kerr` rotation (mrad); Python loading uses `scipy.io.loadmat`.

[REMI calls these open-access benchmarking data](https://pages.nist.gov/remi/data/) and requests Wang/Yoo citations, but its inspected tree and description contain no explicit dataset license. The separate [author starter](https://github.com/alex-aa-wang/Benchmarking-Active-Learning-Starter/tree/527de6f634e55f33d519656c75e06bb446593cab), commit `527de6f634e55f33d519656c75e06bb446593cab`, is MIT licensed and contains code, not measurements. The article's CC BY license does not automatically establish the dataset's rights.

[Wang et al.](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=934371) already benchmark GP expected improvement and CAMEO, which learns structural phase information before optimizing magnetic properties. Repeating structure-to-magnetism selection is supporting evidence, not Blue Sky admission. Admission still requires a consequential newly attainable outcome against the strongest complete alternative, with acquisition, construction, verification and continuing obligations counted. Binary retrieval remains untested here.

## Battery access status

[Stanford's dataset index](https://onorilab.stanford.edu/products/code-and-data-set) links this campaign only to [Mendeley v1](https://data.mendeley.com/datasets/zh58byr53c/1); its OSF/Dropbox links concern other datasets. The [descriptor](https://pangea.stanford.edu/ERE/pdf/OnoriPDF/Journals/91.pdf) also names Mendeley. [Version 2](https://data.mendeley.com/datasets/zh58byr53c/2) declares CC BY 4.0, but rendered landing metadata exposes no individual file URLs. No first-party measurement mirror was found in this bounded check. This is an access limitation, not evidence that the dataset is absent. Fitted parameters from another model repository cannot substitute for independently measured cell/module traces.
