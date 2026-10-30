import argparse, ast, hashlib, json, math, resource, statistics, time
from pathlib import Path

PIN = 'acfebab2a4004786c69dc212a6260ef22780e72f6fbb6696b94384b4276db8ac'

def run(root):
    started, cpu = time.monotonic(), time.process_time()
    source = root / 'experiments/opportunity006/upstream/run_ground_truth_for_combinatorial_perturbations.py'
    if hashlib.sha256(source.read_bytes()).hexdigest() != PIN: raise ValueError('UPSTREAM_IDENTITY_MISMATCH')
    tree = ast.parse(source.read_text())
    node = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'se_gene_expr_for_condition')
    returned = next(x.value for x in node.body if isinstance(x, ast.Return))
    expression = ast.unparse(returned)
    if expression != 'sub_data.X.toarray().std(axis=0) / sub_data.shape[0]': raise ValueError('UPSTREAM_FORMULA_CHANGED')
    values = [0., 2., 4., 6.]
    population_sd = statistics.pstdev(values)
    n = len(values)
    published_formula = population_sd / n
    iid_population_sem = population_sd / math.sqrt(n)
    empirical_excerpt = root / 'experiments/opportunity006/upstream/double_perturbation_analysis-relevant.R.txt'
    downstream = empirical_excerpt.read_text()
    empirical_labels = 'locfdr::locfdr(filter_gt_df$error' in downstream and 'slice_min(abs(fdr - 0.05)' in downstream
    return {'schema':'agi-alpha-published-source-criticism006/v1', 'source_sha256':PIN, 'source_revision':'bfa6eeea2bd145a1af2ec0127a2e808cc38456a9',
      'claim_challenged':'The helper named se_gene_expr_for_condition implements an IID standard error, and its error invalidates published interaction labels.',
      'source_expression':expression, 'numerical_reproduction':{'values':values,'n':n,'population_sd':population_sd,'published_formula':published_formula,'population_sd_over_sqrt_n':iid_population_sem,'underestimate_factor':iid_population_sem/published_formula},
      'adjudication':{'helper_name_semantics':'ESTABLISHED_SCOPED_MISMATCH_TO_IID_SEM','published_interaction_label_consequence':'NOT_ESTABLISHED','reason':'The inspected notebook derives the labels from an empirical null of observed additive residuals rather than this SE helper. This diagnostic does not invalidate the paper conclusions.','empirical_label_path_observed':empirical_labels},
      'corrective_constraint_authority':False,'constructor_should_consume_as_established_label_defect':False,
      'limits':['Numerical four-value check is a mathematical reproduction of the actual source formula, not a biological experiment.','IID cell assumptions are not guaranteed biological-replicate independence.','Source author did not supply this criticism; it was found by implementation-team inspection.'],
      'resources':{'wall_seconds':time.monotonic()-started,'cpu_seconds':time.process_time()-cpu,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'model_calls':0,'complete_monetary_cost':None}}

if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);(a.output/'REPORT.json').write_text(json.dumps(run(a.root),indent=2)+'\n')
