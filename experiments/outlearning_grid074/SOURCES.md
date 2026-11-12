# Primary sources and what they support

- Masoud Farivar and Steven H. Low, Branch Flow Model: Relaxations and Convexification, Part I (2013), equations 1-3: complex Ohm law, branch power and nodal power balance. The included direct two-bus check solves these equalities on the high-voltage branch; it does not rely on convex-relaxation exactness.
  https://smart.caltech.edu/papers/FarivarLow-20130228-BFM-2parts.pdf
- S. Bhela, V. Kekatos and S. Veeramachaneni, Smart Inverter Grid Probing for Learning Loads (2019): existing active probing/identifiability work. It supports treating competent probing and observability analysis as an ordinary comparator right, not a new capability shown here.
  https://arxiv.org/abs/1806.08834v2
- B. Liu, J. H. Braslavsky and N. Mahdavi, Robust Dynamic Operating Envelopes (2023): existing uncertainty-aware operating-envelope work. No superiority to this or a completed robust comparator is claimed.
  https://arxiv.org/abs/2302.13472v5

The opportunity sources are retained in OPPORTUNITIES.md. None is evidence that this generated method delivers accepted field work, earns revenue or creates an additional viable business.

## Independent two-bus calculation used in the portable check

For source magnitude E, injection p+jq and series impedance r+jx, squared receiving voltage solves v^2-[E^2+2(rp+xq)]v+(r^2+x^2)(p^2+q^2)=0. The positive high-voltage root reconstructs a complex receiving voltage and current; the check verifies complex injected power and all signed branch equalities.

For the illustrated constant-q/p ray, v(p) is concave on its positive-discriminant branch. Its derivative is positive at the chosen upper endpoint, so voltage is increasing across that ray. Line-current magnitude increases for p>=0 because concavity and v(0)>0 imply v-p*v'>0. Thus endpoint checks establish these particular witness decisions. This payload does not supply a general full-network or unknown-regime qualification routine.
