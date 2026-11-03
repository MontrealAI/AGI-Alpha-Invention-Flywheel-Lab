/* Directed-rounding bounds for finite binary64 linear-system outputs.
 * Exact input values are binary64; no unproved residual-size heuristic.
 * Compile flags are pinned by interval.py. Unsupported arithmetic fails closed.
 * No state, files, network, external actions or caller-controlled code execution.
 */
#include <fenv.h>
#include <float.h>
#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>

#pragma STDC FENV_ACCESS ON

static double rounded_add(double a, double b) {
    volatile double value = a + b;
    return value;
}
static double rounded_sub(double a, double b) {
    volatile double value = a - b;
    return value;
}
static double rounded_mul(double a, double b) {
    volatile double value = a * b;
    return value;
}
static double rounded_div(double a, double b) {
    volatile double value = a / b;
    return value;
}

/* Test both positive and negative ties and gradual subnormal rounding. */
int omega_interval_self_test(void) {
#if FLT_RADIX != 2 || DBL_MANT_DIG != 53 || DBL_MAX_EXP != 1024 || FLT_EVAL_METHOD != 0
    return 1;
#else
    fenv_t original;
    if (fegetenv(&original)) return 2;
    volatile double one = 1.0, half_ulp = 0x1p-53;
    volatile double tiny = 0x0.0000000000001p-1022, half = 0.5;
    int okay = 1;
    if (fesetround(FE_DOWNWARD)) okay = 0;
    if (rounded_add(one, half_ulp) != 1.0) okay = 0;
    if (rounded_add(-one, -half_ulp) >= -1.0) okay = 0;
    if (rounded_mul(tiny, half) != 0.0) okay = 0;
    if (rounded_mul(-tiny, half) != -tiny) okay = 0;
    if (fesetround(FE_UPWARD)) okay = 0;
    if (rounded_add(one, half_ulp) <= 1.0) okay = 0;
    if (rounded_add(-one, -half_ulp) != -1.0) okay = 0;
    if (rounded_mul(tiny, half) != tiny) okay = 0;
    if (rounded_mul(-tiny, half) != 0.0) okay = 0;
    if (fesetenv(&original)) okay = 0;
    return okay ? 0 : 3;
#endif
}

/* out: alpha_lower, condition_upper, absolute_error_upper,
 *      relative_error_upper (INFINITY if not bounded), scaled_residual_upper.
 * 0 = valid conservative bounds; nonzero requires exact fallback or refusal.
 * Overflow, nonfinite data, nonpositive margin, allocation and rounding faults
 * never yield accepted numerical evidence.
 */
int omega_interval_bound(size_t n, const double *a, const double *b,
                         const double *x, double *out) {
    fenv_t original;
    int status = 0;
    double *dot_lo = NULL, *dot_hi = NULL, *off_hi = NULL;
    double anorm_lo = 0.0, anorm_hi = 0.0, bnorm = 0.0, xnorm = 0.0;
    double alpha = INFINITY, residual = 0.0;
    if (!n || n > SIZE_MAX / n || n > SIZE_MAX / sizeof(double)) return 4;
    if (fegetenv(&original)) return 5;
    dot_lo = calloc(n, sizeof(double));
    dot_hi = calloc(n, sizeof(double));
    off_hi = calloc(n, sizeof(double));
    if (!dot_lo || !dot_hi || !off_hi) { status = 6; goto done; }
    for (size_t i = 0; i < n; ++i) {
        if (!isfinite(b[i]) || !isfinite(x[i])) { status = 7; goto done; }
        if (fabs(b[i]) > bnorm) bnorm = fabs(b[i]);
        if (fabs(x[i]) > xnorm) xnorm = fabs(x[i]);
        for (size_t j = 0; j < n; ++j)
            if (!isfinite(a[i*n+j])) { status = 7; goto done; }
    }
    feclearexcept(FE_ALL_EXCEPT);
    if (fesetround(FE_DOWNWARD)) { status = 8; goto done; }
    for (size_t i = 0; i < n; ++i) {
        double norm = 0.0, dot = 0.0;
        for (size_t j = 0; j < n; ++j) {
            norm = rounded_add(norm, fabs(a[i*n+j]));
            dot = rounded_add(dot, rounded_mul(a[i*n+j], x[j]));
        }
        dot_lo[i] = dot;
        if (norm > anorm_lo) anorm_lo = norm;
    }
    if (fesetround(FE_UPWARD)) { status = 8; goto done; }
    for (size_t i = 0; i < n; ++i) {
        double norm = 0.0, off = 0.0, dot = 0.0;
        for (size_t j = 0; j < n; ++j) {
            norm = rounded_add(norm, fabs(a[i*n+j]));
            if (i != j) off = rounded_add(off, fabs(a[i*n+j]));
            dot = rounded_add(dot, rounded_mul(a[i*n+j], x[j]));
        }
        dot_hi[i] = dot;
        off_hi[i] = off;
        if (norm > anorm_hi) anorm_hi = norm;
    }
    if (fetestexcept(FE_OVERFLOW | FE_INVALID | FE_DIVBYZERO)) { status = 9; goto done; }
    if (fesetround(FE_DOWNWARD)) { status = 8; goto done; }
    for (size_t i = 0; i < n; ++i) {
        double margin = rounded_sub(fabs(a[i*n+i]), off_hi[i]);
        double lo = rounded_sub(b[i], dot_hi[i]);
        if (margin < alpha) alpha = margin;
        if (fabs(lo) > residual) residual = fabs(lo);
    }
    if (!(alpha > 0.0) || !isfinite(alpha)) { status = 10; goto done; }
    if (fesetround(FE_UPWARD)) { status = 8; goto done; }
    for (size_t i = 0; i < n; ++i) {
        double hi = rounded_sub(b[i], dot_lo[i]);
        if (fabs(hi) > residual) residual = fabs(hi);
    }
    out[0] = alpha;
    out[1] = rounded_div(anorm_hi, alpha);
    out[2] = rounded_div(residual, alpha);
    if (!isfinite(out[1]) || !isfinite(out[2])) { status = 11; goto done; }
    if (fesetround(FE_DOWNWARD)) { status = 8; goto done; }
    double solution_lower = rounded_sub(xnorm, out[2]);
    double residual_scale_lower = rounded_add(rounded_mul(anorm_lo, xnorm), bnorm);
    if (fesetround(FE_UPWARD)) { status = 8; goto done; }
    out[3] = solution_lower > 0.0 ? rounded_div(out[2], solution_lower)
             : (out[2] == 0.0 ? 0.0 : INFINITY);
    out[4] = residual_scale_lower > 0.0 ? rounded_div(residual, residual_scale_lower)
             : (residual == 0.0 ? 0.0 : INFINITY);
    if (!isfinite(out[4]) || fetestexcept(FE_OVERFLOW | FE_INVALID | FE_DIVBYZERO)) status = 12;
done:
    free(dot_lo); free(dot_hi); free(off_hi);
    if (fesetenv(&original)) status = 13;
    return status;
}
