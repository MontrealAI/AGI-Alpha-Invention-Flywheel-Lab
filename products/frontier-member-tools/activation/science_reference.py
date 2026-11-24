"""Independent decimal computation for the registered ephemeris decision."""

from decimal import Decimal, localcontext, ROUND_CEILING, ROUND_FLOOR


def verified(case):
    label = case['witness']
    withheld = {'epoch': None, 'sigma_s': None, 'witness': label}
    if case['basis'] != 'BJD_TDB' or case['anchor'] is None:
        return {**withheld, 'decision': 'ABSTAIN_TIME_BASIS'}
    table = case['ephemeris']
    if None in table.values():
        return {**withheld, 'decision': 'ABSTAIN_MISSING'}
    with localcontext() as arithmetic:
        arithmetic.prec = 128
        fields = {key: Decimal(value) for key,value in table.items()}
        t = fields['t0_day']
        p = fields['period_day']
        s = fields['t0_sigma_day']
        d = fields['period_sigma_day']
        anchor = Decimal(case['anchor'])
        epoch = int((anchor-t)//p)
        if t+epoch*p < anchor:
            epoch += 1
        if not t+(epoch-1)*p < anchor <= t+epoch*p:
            raise ValueError('EPOCH_WITNESS')
        # The time variance is affine in correlation. Test the ends of the
        # admissible correlation interval, retaining the sign of the epoch.
        v1 = s*s + (epoch*d)**2 + 2*epoch*s*d
        v2 = s*s + (epoch*d)**2 - 2*epoch*s*d
        low, high = min(v1,v2), max(v1,v2)
        limit_squared = fields['duration_hour']**2
        result = ('WITHIN' if high*288**2 <= limit_squared else 'EXCEEDS' if low*288**2 > limit_squared
                  else 'COVARIANCE_SENSITIVE')
        seconds = [int((value.sqrt()*86400).to_integral_value(rounding=rounding))
                   for value,rounding in ((low,ROUND_FLOOR),(high,ROUND_CEILING))]
        return {'decision':result, 'epoch':epoch, 'sigma_s':seconds, 'witness':label}
