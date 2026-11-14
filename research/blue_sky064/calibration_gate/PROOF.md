# Why the finite endpoint test really bounds the *minimum* (and not the maximum)

This addendum follows the already committed preregistration and first successful head. It clarifies a subtle numerical-analysis point before any conditional certificate is interpreted. The preregistered 196,608 corner evaluations stay unchanged. Original first-run evidence and the workflow-YAML parse failure remain their historical outcomes.

## Exact special geometry, not a universal theorem

The frozen source uses two positive contact families A and B, two increasing indentations d₀=0.010 mm and d₁=0.100 mm, and B's contact onset at h_A-h_B=0.120-0.084=0.036 mm. Therefore only A is active at d₀; both A and B are active at d₁. If this geometry is changed, the planner **refuses** the endpoint-minimum certificate rather than applying the following proof to an arbitrary contact system.

Let S_A and D_A be positive static and dynamic coefficients for family A, each a positive product of its fitted sigma and B. Let S_B,D_B be the same for family B. Let a,b>0 be the fixed first-family and second-family contact-area weights at d₁. Their absolute scale does not matter to the ratio. The preregistered increment is

> Δ = (a S_A + b S_B)/(a D_A + b D_B) − S_A/D_A.

For any fixed values of the remaining coefficients:

* As a function of S_A, Δ is **strictly decreasing** (coefficient −b D_B/[D_A(aD_A+bD_B)]). As a function of S_B it is **strictly increasing**.
* As a function of D_B, only the first ratio changes, and Δ is strictly decreasing.
* As a function of D_A=x>0, write U=aS_A+bS_B and V=bD_B. Then Δ(x)=U/(ax+V)−S_A/x. Its derivative is S_A/x²−aU/(ax+V)². It is positive as x tends to 0, negative as x grows, and has exactly one positive zero, because U>aS_A; that stationary point is a **maximum**, never a minimum.

Consequently, **for each coordinate, holding the others fixed, a minimum occurs at an interval endpoint**. Each positive sigma/B factor influences only one of S_A,D_A,S_B,D_B through an increasing linear map with other factors held fixed. Sequentially moving the eight coordinates to endpoints therefore never raises Δ and eventually reaches one of the 256 shared coefficient-box corners. Thus the smallest finite corner value is the **global minimum over the stipulated independent positive coefficient box** for *this exact model and geometry*. This does **not** mean that the largest corner is the continuous maximum—an interior maximum of D_A can exist. The report explicitly labels its upper statistic **corner-only**.

The proof is of a mathematical uncertainty set, **not of physical coverage of its independent OLS intervals or of actual transfer to mixed contacts**. Real apparatus error, correlated calibration, viscoelasticity, wear, velocity changes, contact interaction, measurement information and beneficiary acceptance remain unresolved. q=0 in particular assumes exact information about selected coefficients and is not a physically achievable zero-noise experiment. The actual contracted intervals at q=0.25 and q=0.50 have no positive source-model certificate even when all eight coefficients are chosen for hypothetical remeasurement; do not alter thresholds, seeds, contraction factors or the original failing source traces to obtain another result.

## Decision from the first exact-source executed run

GitHub workflow #42359525607, literal source `4ddb947cf01545d5a7b5ef86d58f3aa975a6c00c`, passed 12 source-bound tests and all 768 registered subsets (196,608 corners). It found:

* Original nominal increment **+0.17212125749297225**, but original no-measure adversarial box minimum **−0.30332276904934896**.
* In the **ideal exact-information q=0** case, a minimum of **four** separately remeasured coefficients is required to clear +0.05 across the modeled positive uncertainty box.
* In both **q=0.25 and q=0.50** modeled contractions, **no subset** of the eight coefficients clears that same original target, including the all-eight direct-measurement baseline.

This is a useful *negative* selection result: nominal geometry refinement alone does not remove the binding transfer/measurement gap. Conditional exact-information feasibility is not a real experiment; the next genuine requirement would be a physically supportable new measurement operation or an alternative mechanism that works without those coefficients. The report remains **HOLD / NO DEPLOY**, with costs and buyer terms unknown, not zero.

## Independent alternative and scope

A competent conventional exhaustive subset search obtains **the identical numerical answer** given these coefficients and assumptions; no AI algorithm advantage, causal invention, paid business, new industry, surface manufacture, native financial event or successor improvement has been observed. Standard clutches, passive force limiters and active controllers remain viable complete outside choices. This extra proof strengthens what the finite experiment can *mathematically* reject but supplies no new instrument or deployed response.
