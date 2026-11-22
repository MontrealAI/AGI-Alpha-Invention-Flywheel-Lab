import argparse,hashlib,json,resource,time
from pathlib import Path
import numpy as np
from scipy.io import loadmat

ROOT=Path(__file__).resolve().parent
def main():
    p=argparse.ArgumentParser();p.add_argument('--data',default=str(ROOT/'operandoEIS_5degrees.mat'));p.add_argument('--output',required=True);args=p.parse_args()
    begin=time.monotonic();output=Path(args.output).resolve()
    if output.exists():raise FileExistsError('Refusing to overwrite '+str(output))
    output.mkdir(parents=True);source=Path(args.data).resolve();raw=source.read_bytes()
    assert len(raw)==14330409
    assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\x00'+raw).hexdigest()=='a2500c3927dcf97c11e5b758e28e276d9c79793c'
    d=loadmat(source,verify_compressed_data_integrity=True)
    required=['Hexc','P','Zwt','fs','i','tZ','v']
    if any(k not in d or d[k].dtype.kind not in 'fci' or not np.isfinite(d[k]).all() for k in required):raise ValueError('FINITE_NUMERIC_SOURCE_ARRAYS_REQUIRED')
    fs=float(d['fs'].item());periods=int(d['P'].item());i=d['i'].ravel();v=d['v'].ravel();h=d['Hexc'].ravel();tz=d['tZ'].ravel();zw=d['Zwt']
    if fs<=0 or not 1<=periods<=100 or len(i)!=len(v) or len(i)%periods or (h!=h.astype(int)).any():raise ValueError('SOURCE_IDENTITY_OR_PERIOD_SCHEMA')
    h=h.astype(int);n=len(i)//periods;tp=n/fs;duration=len(i)/fs;f=h/tp
    if n>1000000 or len(h)>256 or len(set(h))!=len(h) or min(h)<=0 or max(h)>=n//2 or zw.shape!=(len(h),len(tz)):raise ValueError('SOURCE_HARMONIC_OR_SHAPE_SCHEMA')
    if np.any(np.diff(tz)<=0) or min(tz)<0 or max(tz)>duration:raise ValueError('REFERENCE_TIME_SCHEMA')
    allowed=(f>0)&(f<10.);excluded=int(sum(~allowed));fh=f[allowed]
    centers=(np.arange(periods)+.5)*tp;interior=(centers>=.1*duration)&(centers<=.9*duration)
    tau=np.linspace(-1.,1.,n,endpoint=False);polynomial=np.column_stack([np.ones(n),tau,tau*tau]);pf=np.fft.rfft(polynomial,axis=0)
    coupling=np.vstack([pf[h].real,-pf[h].imag]);gram=polynomial.T@polynomial-(2/n)*(coupling.T@coupling)
    condition=float(np.linalg.cond(gram))
    if condition>1e12:raise ValueError('JOINT_BASELINE_ILL_CONDITIONED')
    methods={'stationary_period_fft':[],'joint_fourier_quadratic_drift':[]};min_input=[];coefficient_checks=[]
    for j in range(periods):
        samples=np.column_stack([i[j*n:(j+1)*n],v[j*n:(j+1)*n]])
        transform=np.fft.rfft(samples,axis=0);phasor=transform[h]
        minimum=float(np.min(abs(phasor[:,0])));min_input.append(minimum)
        if minimum<=1e-10:raise ValueError('UNEXCITED_SOURCE_BIN')
        methods['stationary_period_fft'].append((phasor[:,1]/phasor[:,0])[allowed])
        rhs=np.vstack([phasor.real,-phasor.imag]);trend=np.linalg.solve(gram,polynomial.T@samples-(2/n)*(coupling.T@rhs));coef=(2/n)*(rhs-coupling@trend)
        fitted_phasor=coef[:len(h)]-1j*coef[len(h):]
        methods['joint_fourier_quadratic_drift'].append((fitted_phasor[:,1]/fitted_phasor[:,0])[allowed])
        residual_moments=polynomial.T@samples-(n/2)*0
        normal_residual=gram@trend-(polynomial.T@samples-(2/n)*(coupling.T@rhs))
        coefficient_checks.append(float(np.linalg.norm(normal_residual)/max(1.,np.linalg.norm(polynomial.T@samples))))
    reference=np.array([[np.interp(t,tz,zw[k].real)+1j*np.interp(t,tz,zw[k].imag) for k in np.flatnonzero(allowed)] for t in centers])
    refs=zw[allowed][:,(tz>=.1*duration)&(tz<=.9*duration)];median=np.median(abs(refs),axis=1);change=(np.max(abs(refs),axis=1)-np.min(abs(refs),axis=1))/median
    endpoints={};serialized={}
    for name,values in methods.items():
        values=np.asarray(values);err=abs(values[interior]-reference[interior])/abs(reference[interior]);endpoints[name]={'median_relative_complex_disagreement_to_provided_dynamic_estimate':float(np.median(err)),'p95_relative_complex_disagreement':float(np.quantile(err,.95)),'max_relative_complex_disagreement':float(np.max(err)),'physical_accuracy_established':False}
        serialized[name]={'real':values.real.tolist(),'imag':values.imag.tolist()}
    report={'protocol_sha256':hashlib.sha256((ROOT/'PROTOCOL.json').read_bytes()).hexdigest(),'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'data_sha256':hashlib.sha256(raw).hexdigest(),'downloaded_bytes':len(raw),'scope':'Single real5degree battery charging data, all development; provided dynamic result is an algorithmic estimate, not independent truth','source_sample_rate_hz':fs,'samples':len(i),'periods':periods,'samples_per_period':n,'period_seconds':tp,'duration_seconds':duration,'excited_bins_total':len(h),'interpretable_frequency_bins_below10hz':int(sum(allowed)),'excluded_calibration_affected_bins_ge10hz':excluded,'frequency_range_hz':[float(min(fh)),float(max(fh))],'interior_period_count':int(sum(interior)),'source_dynamic_impedance_reference_exists':True,'source_dynamic_magnitude_relative_range_median_across_frequency':float(np.median(change)),'source_dynamic_magnitude_relative_range_max_across_frequency':float(np.max(change)),'baseline_endpoints':endpoints,'joint_fourier_schur_condition':condition,'largest_relative_normal_equation_residual':max(coefficient_checks),'minimum_excited_input_fft_magnitude':min(min_input),'causal_lever_admission':'REJECTED_AS_FLAGSHIP: nonstationary multisine impedance measurement already demonstrated by complete published operando routes; no new output class, independent physical accuracy or economic unmet constraint established','calibration_warning_honored':True,'no_commercial_demand_or_complete_profit_established':True,'next_discriminating_construction':'Source-backed2026 review identifies fast drift overlapping the lowest excitation as a common limitation. A future instrument must separate kinetics from rapid state evolution using synchronized orthogonal physical measurements or designed perturbations, tested on independently calibrated transient input/output data. Existing LTV trend-removal/differencing and dynamic alternatives receive equal access. That physical data/control inventory is missing here.','wall_seconds':time.monotonic()-begin,'cpu_seconds':resource.getrusage(resource.RUSAGE_SELF).ru_utime+resource.getrusage(resource.RUSAGE_SELF).ru_stime,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    raw_result={'frequencies_hz':fh.tolist(),'period_centers_seconds':centers.tolist(),'interior_period_mask':interior.tolist(),'provided_dynamic_reference_at_centers':{'real':reference.real.tolist(),'imag':reference.imag.tolist()},'ordinary_estimates':serialized,'source_dynamic_relative_magnitude_range':change.tolist()}
    (output/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n');(output/'RAW_DIAGNOSTICS.json').write_text(json.dumps(raw_result,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
