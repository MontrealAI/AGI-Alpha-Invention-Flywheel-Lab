# Short observation identifiability and constructive follow up

Prospective numerical stage registered 2 November 2026 after the sparse-anchor cost gate failed at protocol inspection, before numerical challenge outcomes. It does not replace or soften the first registration.

## Question

Can a short high-state-of-charge cell characterization support an accurate **ex ante2100-second discharge-interval** branch-current prediction when the unobserved low-state-of-charge voltage curve is uncertain? If not, can an additional observation distinguish the surviving candidate models before accepting the successor? Affordability must include unresolved setup and validation costs.

## Finite model and controls

Use independent monotone OCV curves, one-RC polarization, positive capacity and resistances, and a four-cell ladder network. Positive current denotes discharge. The constructor uses a compiled impedance matrix with Cholesky factorization and OCV interpolation; the verifier uses full two-rail nodal Kirchhoff equations and independent integration with analytic OCV. Both use the same declared model class, so agreement verifies implementation and a finite mathematical claim, not real battery validity.

The verifier owns an adversarial pair with identical observable high-SOC response and different capacity and low-SOC knee. It fixed the pair before inspecting constructor code: capacities Q=2 Ah and Q=3 Ah; cumulative discharged charge q=Q(1-SOC); OCV U(q)=4.2-0.4q-c max(q-0.4,0)^2, where c=(4.2-0.4Q-2.5)/(Q-0.4)^2. Both cells have R0=0.020 ohm, R1=0.010 ohm, tau=30 seconds, initial SOC1 and zero initial polarization. Both monotone curves reach 2.5 V at empty and coincide for every admitted history restricted to q<=0.4 Ah.

No full physical measurements are fitted. The short observation is600 seconds at0.75 A from SOC1, with2 mV bounded observation error; the verifier additionally checks the stronger1440-second1 A observation reaching the entire shared0.4 Ah range. The subsequent pack task is8 A constant-current discharge of four cells through2 milliohm loop segments (1 milliohm on each rail), with the uncertain cell in position0 and three known Q2 cells, over2100 seconds. Record both plausible worlds, not a favorable chosen world. Test a dense reference, retained compiled network, zero-interconnect ablation, equal sharing, and numerical step refinement. The constructor represents OCV with2001 uniform SOC knots; the verifier evaluates the independent analytic formula.

The short-data identifiability gate requires the two worlds to agree within2 mV on all admitted observations, while the subsequent2100-second interval prediction must satisfy the originally registered branch-current RMSE and peak contract in both. Peak requirements are incompatible when absolute peak difference exceeds0.1 times the sum of the two true peak magnitudes, making the respective10 percent acceptance intervals disjoint. Also report half the full-trace RMS separation as a minimax lower bound. A single-point error does not by itself falsify a whole-trace RMSE claim. Return explicit ambiguity or abstention when the registered contract cannot be guaranteed.

## Constructive response

Search a finite menu of additional single-cell observations: cumulative discharged-charge fractions 0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60 of a COMMON nominal2 Ah at rates 0.15 C, 0.5 C and 0.75 C relative to that SAME nominal capacity, followed by300 seconds rest. The actions and current are identical across worlds; no unknown true capacity can choose a probe. The initial short acquisition is counted separately, with state-reset/preparation an unresolved physical cost. A probe separates two candidates only if their predicted voltages differ by more than4 mV, twice the bounded error. Select the minimum-duration separating probe within this finite two-world set, and compare its discharge/rest duration with the reference C/20 discharge duration. Report exact search size, remaining ambiguity, duration and objective gap; no global optimum or safe physical protocol is claimed.

Count the source model/prior and setup as unqualified prerequisites. A selected probe may be an engineering candidate for later measurement, not proof that a real cell belongs to the two-world set. More model candidates, temperature shift, observation drift or unknown capacity can invalidate the result. Numerical success only establishes a precise observation-design hypothesis worth testing against independent physical measurements.

## Outputs and stopping

Freeze constructor and verifier hashes, preserve the initial cost-bound failure, run the finite identifiability challenge, and retain a portable capability/probe record with explicit scope and invalidation conditions. Close this stage after its independently recomputed result. Any physical-validation extension requires public measured data, source freeze and prospective acceptance; revenue and scale remain gated.
