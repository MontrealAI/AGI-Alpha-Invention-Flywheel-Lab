import json,xml.etree.ElementTree as ET
from fractions import Fraction as F
from pathlib import Path
import compile_petab_forcing as c

def main():
    root=Path(__file__).resolve().parent;model=ET.parse(root/'boehm_source/model.xml').getroot()
    source_literals=[x for x in model.iter() if c.gp.local(x)=='cn' and x.attrib.get('type')=='e-notation']
    assert source_literals,'Source counterexample absent'
    witness=next(x for x in source_literals if x.text.strip()=='1.25' and x[0].tail.strip()=='-7')
    assert c.cn_value(witness)==F(1,8000000)
    cases=[('<cn type="integer">-2</cn>',F(-2)),('<cn>0.125</cn>',F(1,8)),('<cn type="e-notation">1.25<sep/>-7</cn>',F(1,8000000)),('<cn type="rational">1<sep/>3</cn>',F(1,3))]
    for text,expected in cases:assert c.cn_value(ET.fromstring(text))==expected
    rejected=0
    for text in ['<cn base="16">10</cn>','<cn type="real">1<sep/>2</cn>','<cn type="complex-cartesian">1<sep/>2</cn>']:
        try:c.cn_value(ET.fromstring(text))
        except ValueError:rejected+=1
    assert rejected==3
    report={'source_witness_expected':'1/8000000','decoded':str(c.cn_value(witness)),'prior_text_only_decoded':str(F(witness.text.strip())),'independent_numeric_reference_revalidation_required':True,'ordinary_cases_passed':len(cases),'unsupported_encodings_refused':rejected,'passed':True}
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
