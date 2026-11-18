"""Private, offline enrollment, packet delivery and blinded adjudication for RR-H1."""
import argparse
from hashlib import sha256
import hmac
import json
from pathlib import Path
import random
import re
import secrets
import sqlite3
import sys
import tempfile

from materials import ARMS, HERE, REG, build, script_data, shell

STRATA = ('ordinary', 'screen_reader')
WILLIAMS = ((0,1,3,2),(1,2,0,3),(2,3,1,0),(3,0,2,1))
GRADES = {'accepted','ordinary_error','consequential_error','unresolved'}
COSTS = ('development_and_failed_attempts','maintenance','materials_and_preparation','study_administration',
         'reader_and_assistance','independent_review','support_and_delivery','compute_and_software')
SCHEMA = """
CREATE TABLE meta (seed TEXT NOT NULL, authorization TEXT NOT NULL, accounting TEXT NOT NULL);
CREATE TABLE enrollment (subject TEXT PRIMARY KEY, lang TEXT NOT NULL, stratum TEXT NOT NULL,
 ordinal INTEGER NOT NULL, arm TEXT NOT NULL, order_json TEXT NOT NULL, session TEXT UNIQUE NOT NULL,
 consent_hash TEXT NOT NULL, withdrawn INTEGER NOT NULL DEFAULT 0, response TEXT,
 UNIQUE(lang,stratum,ordinal));"""


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def dump(path,obj):
    with Path(path).open('x',encoding='utf-8') as f:
        json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False); f.write('\n')


def identifier(value):
    if not isinstance(value,str) or not re.fullmatch('[A-Za-z0-9_-]{3,80}',value):
        raise ValueError('Use a pseudonymous identifier with 3–80 simple characters.')
    return value


def key(seed, *parts):
    return hmac.digest(bytes.fromhex(seed), '\0'.join(map(str,parts)).encode(), 'sha256').hex()


def allocation(seed,lang,stratum,ordinal):
    block,slot=divmod(ordinal,4)
    arms=list(ARMS)
    random.Random(key(seed,'arms',lang,stratum,block)).shuffle(arms)
    arm=arms[slot]
    tasks=[t['id'] for t in REG['tasks'] if t['lang']==lang]
    random.Random(key(seed,'tasks',lang,stratum)).shuffle(tasks)
    order=[tasks[i] for i in WILLIAMS[(block+ARMS.index(arm))%4]]
    return arm,order


def initialize(path,authorization):
    auth=read(authorization)
    if auth.get('study')!=REG['id'] or auth.get('human_collection_authorized') is not True or not auth.get('authority_reference'):
        raise ValueError('The operator must record actual authorization for human collection.')
    plan=auth.get('accounting',{})
    if (not isinstance(plan,dict) or not re.fullmatch('[A-Z]{3}',str(plan.get('currency',''))) or
            any(not isinstance(plan.get(k),str) or not plan[k].strip() for k in ('allocation_rule','measurement_window'))):
        raise ValueError('Freeze the currency, allocation rule and measurement window before enrollment.')
    path.mkdir(mode=0o700)
    with sqlite3.connect(path/'roster.sqlite') as db:
        db.executescript(SCHEMA)
        db.execute('INSERT INTO meta VALUES (?,?,?)',(secrets.token_hex(32),sha256(Path(authorization).read_bytes()).hexdigest(),json.dumps(plan)))
    (path/'roster.sqlite').chmod(0o600)


def enroll(db, consent_path):
    consent=read(consent_path)
    subject=identifier(consent['subject'])
    lang,stratum=consent['lang'],consent['stratum']
    if (consent['study']!=REG['id'] or lang not in ('en','fr') or stratum not in STRATA or
        any(consent.get(k) is not True for k in ('consented','fluent','reads_research','paper_and_key_unseen',
                                                 'unique_person','retention_terms_explained')) or not consent.get('consent_reference')):
        raise ValueError('Consent, inclusion, language and assignment stratum must be confirmed.')
    db.execute('BEGIN IMMEDIATE')
    ordinal=db.execute('SELECT count(*) FROM enrollment WHERE lang=? AND stratum=?',(lang,stratum)).fetchone()[0]
    seed=db.execute('SELECT seed FROM meta').fetchone()[0]
    arm,order=allocation(seed,lang,stratum,ordinal)
    session=key(seed,'packet',subject)[:24]
    db.execute('INSERT INTO enrollment(subject,lang,stratum,ordinal,arm,order_json,session,consent_hash) VALUES(?,?,?,?,?,?,?,?)',
               (subject,lang,stratum,ordinal,arm,json.dumps(order),session,sha256(Path(consent_path).read_bytes()).hexdigest()))
    db.commit()
    return subject


def packet(row,out):
    if out.exists(): raise ValueError('Choose a new packet directory.')
    if row['withdrawn']: raise ValueError('Enrollment withdrawn.')
    lang=row['lang']
    prompts={t['id']:t['prompt'] for t in REG['tasks']}
    tr=lambda a,b: a if lang=='en' else b
    title=tr('Reading session','Séance de lecture')
    cfg={'session':row['session'],'maxPage':REG['languages'][lang]['pdf_pages'],
         'tasks':[{'id':t,'prompt':prompts[t]} for t in json.loads(row['order_json'])]}
    body=f"""<p>{tr("Use this local publication and your usual reading tools. Count the cover as physical page 1. Keep this form open. You may stop at any time. Download partial or completed answers and return them only to your study coordinator.","Utilisez la publication locale et vos outils de lecture habituels. Comptez la couverture comme première page physique. Gardez le formulaire ouvert. Vous pouvez arrêter à tout moment. Téléchargez vos réponses partielles ou complètes et remettez-les uniquement à la coordination.")}</p>
    <a href="publication/index.html" target="_blank" rel="noopener">{tr('Open publication in a new tab','Ouvrir la publication dans un nouvel onglet')}</a>
    <h2 id="next" tabindex="-1"></h2><button id="start">{tr('Reveal task and start timing','Afficher la tâche et démarrer le chronomètre')}</button>
    <form id="task" hidden><h3 id="question" tabindex="-1"></h3><label>{tr('Outcome','Résultat')} <select id="outcome"><option value="answered">{tr('Answered','Répondu')}</option><option value="unresolved">{tr('Unresolved','Non résolue')}</option><option value="abandoned">{tr('Abandoned','Abandonnée')}</option></select></label>
    <label>{tr('Answer and units if applicable','Réponse et unités pertinentes')}<textarea id="answer" class="field"></textarea></label><label>{tr('Physical PDF page','Page physique du PDF')}<input type="number" min="1" max="{cfg['maxPage']}" id="page"></label><label>{tr('Supporting quotation','Citation à l’appui')}<textarea id="quote" class="field"></textarea></label>
    <label>{tr('Interruptions or coordinator assistance','Interruptions ou aide de la coordination')}<input id="interruption" class="field"></label><button>{tr('Save task','Enregistrer la tâche')}</button></form>
    <label>{tr('Reading tools actually used','Outils de lecture réellement utilisés')}<input class="field" id="technology"></label><label>{tr('Access barriers, if any. Omit personal details.','Obstacles d’accès, le cas échéant. Évitez les détails personnels.')}<textarea id="barrier" class="field"></textarea></label>
    <button id="download">{tr('Download responses','Télécharger les réponses')}</button><p id="notice" role="status"></p>
    <script type="application/json" id="task-data">{script_data(cfg)}</script><script>{(HERE/'form.js').read_text()}</script>"""
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
        stage=Path(tmp)/'packet';stage.mkdir()
        build(lang,row['arm'],stage/'publication')
        (stage/'START.html').write_text(shell(lang,title,body),encoding='utf-8')
        stage.rename(out)


def receive(db,path):
    data=read(path)
    db.execute('BEGIN IMMEDIATE')
    r=db.execute('SELECT * FROM enrollment WHERE session=? AND withdrawn=0',(data['session'],)).fetchone()
    if r is None: raise ValueError('Unknown or withdrawn session.')
    order=json.loads(r['order_json']); rows=data['rows']
    if not isinstance(rows,list) or not rows or [x['task'] for x in rows]!=order[:len(rows)]:
        raise ValueError('Submission differs from assigned order.')
    for field in ('barrier','technology'):
        if not isinstance(data.get(field),str):raise ValueError('Missing access observation.')
    for item in rows:
        state=item['status'];ms=item['elapsed_ms']
        if state not in ('answered','unresolved','abandoned') or type(ms) is not int or ms<0:
            raise ValueError('Invalid task status or elapsed time.')
        if any(not isinstance(item.get(k),str) for k in ('answer','quote','interruption')):
            raise ValueError('Invalid task response.')
        if state=='answered' and (not item['answer'].strip() or not item['quote'].strip() or type(item['page']) is not int or not 1<=item['page']<=REG['languages'][r['lang']]['pdf_pages']):
            raise ValueError('Answered tasks need an answer, supporting page and quotation.')
    if r['response']:
        previous=json.loads(r['response'])['rows']
        if rows[:len(previous)]!=previous: raise ValueError('Previous responses cannot be replaced.')
    db.execute('UPDATE enrollment SET response=? WHERE subject=?',(json.dumps(data,ensure_ascii=False),r['subject']))
    db.commit()


def observed(db):
    seed=db.execute('SELECT seed FROM meta').fetchone()[0]
    for r in db.execute('SELECT * FROM enrollment WHERE withdrawn=0 ORDER BY subject'):
        data=json.loads(r['response']) if r['response'] else {'rows':[],'barrier':None,'technology':None}
        by={x['task']:x for x in data['rows']}
        for task in json.loads(r['order_json']):
            yield key(seed,'grade',r['subject'],task)[:24],r,task,by.get(task),data


def blind(db,out):
    tasks={t['id']:t for t in REG['tasks']}
    rows=[{'id':k,'task':t,'prompt':tasks[t]['prompt'],'reference_page':tasks[t]['page'],
           'reference_excerpt':tasks[t]['evidence'],'rubric':tasks[t]['rubric'],
           'answer':item['answer'],'quote':item['quote'],'page':item['page']}
          for k,_,t,item,_ in observed(db) if item and item['status']=='answered']
    dump(out,sorted(rows,key=lambda x:x['id']))


def gradefile(path):
    d=read(path); who=identifier(d['reviewer']); out={}
    for row in d['decisions']:
        if row['id'] in out or row['grade'] not in GRADES or not isinstance(row['basis'],str) or not row['basis'].strip():
            raise ValueError('Each grade needs a unique blinded ID and source-grounded basis.')
        out[row['id']]=row['grade']
    return who,out


def adjudicate(db,a,b,tie):
    wa,ga=gradefile(a);wb,gb=gradefile(b)
    needed={k for k,_,_,i,_ in observed(db) if i and i['status']=='answered'}
    if wa==wb or set(ga)!=needed or set(gb)!=needed: raise ValueError('Two distinct complete and blinded grade sets required.')
    conflicts={k for k in needed if ga[k]!=gb[k]}
    if conflicts:
        if not tie: raise ValueError(f'{len(conflicts)} disagreements require independent adjudication.')
        wt,gt=gradefile(tie)
        if wt in {wa,wb} or set(gt)!=conflicts:raise ValueError('Adjudicator must resolve exactly the disagreements.')
        ga.update(gt)
    elif tie: raise ValueError('No disagreement needs adjudication.')
    return ga


def summarize(db,grades,cost_path):
    strata={}
    subjects={}
    for k,row,task,item,data in observed(db):
        group=f"{row['lang']}.{row['stratum']}.{row['arm']}"
        s=subjects.setdefault(row['subject'],{'cohort':group,'assigned':0,'accepted':0,'consequential_errors':0,
                 'ordinary_errors':0,'unresolved':0,'abandoned':0,'missing':0,'elapsed_ms':0,'attempted':0,
                 'barrier':data['barrier'],'technology':data['technology'],'interruptions':[]})
        s['assigned']+=1
        if not item: s['missing']+=1;continue
        s['attempted']+=1;s['elapsed_ms']+=item['elapsed_ms']
        if item['interruption']:s['interruptions'].append(item['interruption'])
        verdict=grades[k] if item['status']=='answered' else item['status']
        col={'consequential_error':'consequential_errors','ordinary_error':'ordinary_errors'}.get(verdict,verdict)
        s[col]+=1
    plan=json.loads(db.execute('SELECT accounting FROM meta').fetchone()[0])
    costs=read(cost_path) if cost_path else {}
    if costs and (costs.get('currency')!=plan['currency'] or not isinstance(costs.get('groups'),dict)):
        raise ValueError('Supply costs in the registered currency for each group.')
    names=('assigned','accepted','consequential_errors','ordinary_errors','unresolved','abandoned','missing','elapsed_ms','attempted')
    for lang in ('en','fr'):
        for stratum in STRATA:
            for arm in ARMS:
                group=f'{lang}.{stratum}.{arm}'
                participants=[v for v in subjects.values() if v['cohort']==group]
                totals={n:sum(x[n] for x in participants) for n in names}
                total_cost=None
                if group in costs.get('groups',{}):
                    bill=costs['groups'][group]
                    if set(bill)!=set(COSTS) or any(v is not None and (type(v) is not int or v<0) for v in bill.values()):
                        raise ValueError('Each cost category requires a nonnegative integer in currency millionths or null.')
                    if all(v is not None for v in bill.values()): total_cost=sum(bill.values())
                totals.update(participants=len(participants),reported_barriers=sum(bool(x['barrier']) for x in participants),
                              complete_cost_micros=total_cost,
                              cost_micros_per_accepted=(total_cost/totals['accepted'] if total_cost is not None and totals['accepted'] else None),
                              accepted_fraction=totals['accepted']/totals['assigned'] if totals['assigned'] else None,
                              consequential_error_fraction=totals['consequential_errors']/totals['assigned'] if totals['assigned'] else None,
                              observed_ms_per_accepted=totals['elapsed_ms']/totals['accepted'] if totals['accepted'] else None,
                              observed_ms_per_attempt=totals['elapsed_ms']/totals['attempted'] if totals['attempted'] else None)
                strata[group]=totals
    if set(costs.get('groups',{}))-set(strata):raise ValueError('Unknown cost group.')
    withdrawn=db.execute('SELECT count(*) FROM enrollment WHERE withdrawn=1').fetchone()[0]
    ready=(not withdrawn and all(g['participants']==4 and g['missing']==0 and not g['reported_barriers']
                  and g['cost_micros_per_accepted'] is not None and g['observed_ms_per_accepted'] is not None for g in strata.values()))
    candidates={}
    for arm in ('C','D'):
        meets=[]
        if ready:
            for lang in ('en','fr'):
                for stratum in STRATA:
                    groups=[strata[f'{lang}.{stratum}.{a}'] for a in ('A','B',arm)]
                    c=groups[2]
                    for ref in groups[:2]:
                        gain=c['accepted_fraction']-ref['accepted_fraction']
                        meets.append(c['consequential_error_fraction']<=ref['consequential_error_fraction']
                            and (gain>=.15 or (gain>=0 and c['observed_ms_per_accepted']<=.8*ref['observed_ms_per_accepted'])))
        candidates[arm]=('eligible_for_confirmation' if all(meets) else 'did_not_meet_registered_gain') if ready else 'unmeasured_or_incomplete'
    return {'study':'RR-H1','assigned_including_withdrawn':len(subjects)+withdrawn,'withdrawn':withdrawn,
            'private_participant_summaries':subjects,'strata':strata,'accounting':plan,'pilot_verdict':candidates,
            'economic_adoption':'requires_review_of_complete_costs_and_outside_options' if ready else 'unmeasured'}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--private',type=Path,required=True)
    subs=ap.add_subparsers(dest='command',required=True)
    subs.add_parser('init').add_argument('--authorization',type=Path,required=True)
    subs.add_parser('enroll').add_argument('--consent',type=Path,required=True)
    p=subs.add_parser('packet');p.add_argument('--subject',required=True);p.add_argument('--output',required=True,type=Path)
    subs.add_parser('receive').add_argument('file',type=Path)
    subs.add_parser('withdraw').add_argument('--subject',required=True)
    subs.add_parser('blind').add_argument('--output',required=True,type=Path)
    p=subs.add_parser('analyze')
    for f in ('a','b','tie','costs','output'):p.add_argument('--'+f,type=Path,required=f in ('a','b','output'))
    args=ap.parse_args()
    if args.command=='init':
        initialize(args.private,args.authorization);return
    db_path=(args.private/'roster.sqlite').resolve()
    with sqlite3.connect(db_path.as_uri()+'?mode=rw',uri=True) as db:
        db.row_factory=sqlite3.Row
        if args.command=='enroll':print(enroll(db,args.consent))
        elif args.command=='packet':
            row=db.execute('SELECT * FROM enrollment WHERE subject=?',(identifier(args.subject),)).fetchone()
            if row is None:raise ValueError('Unknown enrollment.')
            packet(row,args.output)
        elif args.command=='receive':receive(db,args.file)
        elif args.command=='withdraw':
            if db.execute('UPDATE enrollment SET withdrawn=1,response=NULL WHERE subject=? AND withdrawn=0',(identifier(args.subject),)).rowcount!=1:
                raise ValueError('No active enrollment.')
        elif args.command=='blind':blind(db,args.output)
        else:dump(args.output,summarize(db,adjudicate(db,args.a,args.b,args.tie),args.costs))


if __name__=='__main__':
    try:main()
    except (ValueError,TypeError,KeyError,OSError,sqlite3.Error) as exc:sys.exit(str(exc))
