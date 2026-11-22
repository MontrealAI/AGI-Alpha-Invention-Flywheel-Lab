"""Adversarial synthetic-only tests; never fake physical acceptance."""
import csv,io,unittest
from research.eit_sparse108.study import (
    CHANNELS,CLASSES,PAIRS,group_position_key,is_held_out,metrics,
    parse_16_channel_row,parse_csv,prepare,vector,verify_source,
)

def make_row(a=0,label="circle",r="4",phi="50",num="7"):
    b=(a+8)%16
    names=("value_desc","object","material","r","phi","meas_num","ex_mat_0","ex_mat_1")+CHANNELS
    row=dict.fromkeys(names,"1.2")
    row.update({"value_desc":"measurement","object":label,"material":"PETG",
                "r":r,"phi":phi,"meas_num":num,"ex_mat_0":str(a),"ex_mat_1":str(b)})
    absent={a,(a+1)%16,b,(b+1)%16}
    for i,k in enumerate(CHANNELS): row[k]="NA" if i in absent else "1.2"
    return row

def render(rows):
    names=("value_desc","object","material","r","phi","meas_num","ex_mat_0","ex_mat_1")+CHANNELS
    f=io.StringIO()
    w=csv.DictWriter(f,fieldnames=names,lineterminator="\n")
    w.writeheader();w.writerows(rows)
    return f.getvalue().encode()

class FrozenGuards(unittest.TestCase):
    def test_all_features_observed(self):
        a,vals=parse_16_channel_row(make_row())
        self.assertEqual((a,len(vals),vals[0]),(0,12,1.2))
    def test_bad_injection(self):
        row=make_row();row["ex_mat_1"]="1"
        with self.assertRaisesRegex(ValueError,"INJECTION"): parse_16_channel_row(row)
    def test_fake_finite_on_injection(self):
        row=make_row();row["E_01"]="0"
        with self.assertRaisesRegex(ValueError,"INJECTION_NEIGHBOR"): parse_16_channel_row(row)
    def test_missing_real_voltage(self):
        row=make_row();row["E_03"]="NA"
        with self.assertRaisesRegex(ValueError,"MISSING_REQUIRED"): parse_16_channel_row(row)
    def test_nonfinite(self):
        row=make_row();row["E_03"]="NaN"
        with self.assertRaisesRegex(ValueError,"NONFINITE"): parse_16_channel_row(row)
    def test_shape_mismatch(self):
        with self.assertRaisesRegex(ValueError,"LABEL"): parse_csv(render([make_row()]),"square")
    def test_one_physical_archive_group_not_16_independent(self):
        g,s=parse_csv(render([make_row(a=a) for a in range(16)]),"circle")
        self.assertEqual((s["archive_measurement_groups"],s["measurement_rows"]),(1,16))
        one=next(iter(g.values()))
        self.assertEqual((len(vector(one,PAIRS[4])),len(vector(one,PAIRS[16]))),(48,192))
    def test_duplicate_acquisition(self):
        rows=[make_row(a=a) for a in range(16)]+[make_row()]
        with self.assertRaisesRegex(ValueError,"DUPLICATE"): parse_csv(render(rows),"circle")
    def test_empty_group(self):
        with self.assertRaisesRegex(ValueError,"INCOMPLETE"):
            parse_csv(render([make_row(a=a) for a in range(15)]),"circle")
    def test_changed_source(self):
        with self.assertRaisesRegex(ValueError,"MD5"): verify_source(b"synthetic", "circle")
    def test_position_holdout_same_across_classes(self):
        self.assertEqual(is_held_out("7","10"),is_held_out("7","10"))
        self.assertIsInstance(is_held_out("7","10"),bool)
    def test_missing_position(self):
        with self.assertRaisesRegex(ValueError,"POSITION"): group_position_key("","0")
    def test_metrics_confusion(self):
        m=metrics(["circle","square","triangle"],["circle","circle","triangle"])
        self.assertEqual((m["correct_groups"],m["per_class_recall"]["square"]),(2,0))
    def test_unknown_result(self):
        with self.assertRaisesRegex(ValueError,"UNKNOWN"):
            metrics(["circle"],["unknown"])
    def test_refuse_tiny_heldout(self):
        g,_=parse_csv(render([make_row(a=a) for a in range(16)]),"circle")
        with self.assertRaisesRegex(ValueError,"INSUFFICIENT"): prepare({c:g for c in CLASSES})
    def test_tampered_vector(self):
        g,_=parse_csv(render([make_row(a=a) for a in range(16)]),"circle")
        d=next(iter(g.values()));d[5]=(2.0,)
        with self.assertRaisesRegex(ValueError,"INVALID_GROUP"): vector(d,PAIRS[16])
    def test_missing_column(self):
        b=render([make_row(a=a) for a in range(16)]).replace(b"E_01",b"E_17",1)
        with self.assertRaisesRegex(ValueError,"FIELDS"): parse_csv(b,"circle")

if __name__=="__main__": unittest.main()
