from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.section import WD_SECTION_START
from docx.enum.text import WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_ROW_HEIGHT_RULE
from docx.enum.text import WD_LINE_SPACING
from pathlib import Path

OUT=Path('/mnt/data/ALPHA_GENESIS_FLYWHEEL_OMEGA_LIVE/02_PARTICIPANT/ALPHA_GENESIS_LIVE_Workbook.docx')
PURPLE=RGBColor(39,25,66); GOLD=RGBColor(137,95,36); GRAY=RGBColor(75,76,91); DARK=RGBColor(23,20,35); BLUE=RGBColor(58,68,132)
D=Document();sec=D.sections[0];sec.page_height=Inches(11);sec.page_width=Inches(8.5);sec.top_margin=Inches(.74);sec.bottom_margin=Inches(.63);sec.left_margin=Inches(.77);sec.right_margin=Inches(.77);sec.header_distance=Inches(.28);sec.footer_distance=Inches(.26)
styles=D.styles
for s in ['Normal','Title','Heading 1','Heading 2','Heading 3']:
 st=styles[s];st.font.name='Inter';st.font.color.rgb=DARK
styles['Normal'].font.size=Pt(10);styles['Normal'].paragraph_format.space_after=Pt(7)
styles['Normal'].paragraph_format.line_spacing=1.23
for name,size,col in [('Title',32,PURPLE),('Heading 1',21,PURPLE),('Heading 2',13,PURPLE),('Heading 3',10,GOLD)]:
 st=styles[name];st.font.name='Inter Display' if name in ('Title','Heading 1') else 'Inter';st.font.size=Pt(size);st.font.bold=True;st.font.color.rgb=col;st.paragraph_format.space_before=Pt(11);st.paragraph_format.space_after=Pt(7)
# custom lines
for name in ['Tagline','SmallCaption','Callout']:
 if name not in styles: styles.add_style(name,WD_STYLE_TYPE.PARAGRAPH)
styles['Tagline'].font.name='Inter';styles['Tagline'].font.size=Pt(10);styles['Tagline'].font.bold=True;styles['Tagline'].font.color.rgb=GOLD
styles['SmallCaption'].font.name='Inter';styles['SmallCaption'].font.size=Pt(8);styles['SmallCaption'].font.color.rgb=GRAY
styles['Callout'].font.name='Inter';styles['Callout'].font.size=Pt(11);styles['Callout'].font.bold=True;styles['Callout'].font.color.rgb=PURPLE

# header/footer
header=sec.header.paragraphs[0];header.text='MONTREAL.AI  /  ALPHA GENESIS LIVE';header.alignment=WD_ALIGN_PARAGRAPH.RIGHT
header.style='SmallCaption'
foot=sec.footer.paragraphs[0];foot.alignment=WD_ALIGN_PARAGRAPH.CENTER
r=foot.add_run('ALPHA GENESIS FLYWHEEL OMEGA — LIVE  |  PARTICIPANT  |  ');r.font.size=Pt(8);r.font.color.rgb=GRAY
fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');foot._p.append(fld)

def title(sub,t,detail):
 D.add_paragraph(sub,'Tagline');D.add_heading(t,0 if False else 1);p=D.add_paragraph(detail);p.style='Normal';return p

def label(txt):
 p=D.add_paragraph(txt,'Tagline');p.paragraph_format.space_before=Pt(10);p.paragraph_format.space_after=Pt(4)
def p(txt='',style=None):return D.add_paragraph(txt,style)
def bullet(txt):
 z=D.add_paragraph(style='Normal');z.style='List Bullet';z.add_run(txt);return z

def line(prompt=''):
 x=p(prompt);x.paragraph_format.space_after=Pt(4)
 z=p('_________________________________________________________________________________________________');z.style='SmallCaption';z.paragraph_format.space_after=Pt(8)

def table(headers,rows,widths=None):
 t=D.add_table(rows=1,cols=len(headers));t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.style='Light Shading Accent 1';t.autofit=False
 if widths:
  for j,w in enumerate(widths):t.columns[j].width=Inches(w)
 for i,h in enumerate(headers):
  c=t.rows[0].cells[i];c.text=h; c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
  for r in c.paragraphs[0].runs:r.font.bold=True;r.font.color.rgb=RGBColor(255,255,255);r.font.size=Pt(8.5)
  shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'34264F');c._tc.get_or_add_tcPr().append(shade)
 for idx,rr in enumerate(rows):
  cells=t.add_row().cells
  for j,val in enumerate(rr):
   cells[j].text=str(val)
   for para in cells[j].paragraphs:
    para.paragraph_format.space_after=Pt(0);para.paragraph_format.line_spacing=1.0
    for run in para.runs:run.font.name='Inter';run.font.size=Pt(8.5)
   if idx%2==1:
    shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'F3F0F7');cells[j]._tc.get_or_add_tcPr().append(shade)
 D.add_paragraph('').paragraph_format.space_after=Pt(1)
 return t

def nextpage():D.add_page_break()

# 01 COVER
D.add_paragraph('MONTREAL.AI  /  LIVE INVENTION LABORATORY','Tagline').paragraph_format.space_before=Pt(51)
p('THE ARCHITECTURE OF THE POSSIBLE','Tagline')
h=D.add_paragraph(style='Title');h.paragraph_format.space_before=Pt(26);h.add_run('ALPHA GENESIS\nFLYWHEEL Ω\n— LIVE')
bar=p('━━━━━━━━━━━━━━━━━━━━━━');bar.runs[0].font.color.rgb=GOLD
p('From “What if?” to “Look what we made possible.”','Callout')
p('An ambition → a live investigation → something built → a serious test → a better next move.','Normal')
p('LIVE ONLINE  |  PROFESSIONAL EXPERIENCE  |  ENGLISH','Tagline')
p('PARTICIPANT NAME  __________________________________________','Normal')
D.add_paragraph('').paragraph_format.space_after=Pt(20)
D.add_heading('Your outcome',2)
p('You will watch a tool-using AI agent investigate a consequential fictional business challenge, compare three possible recovery strategies, build a reusable decision instrument, inspect independently recomputed results, and apply the same method to an ambition of your own.')
D.add_heading('Bring',2)
bullet('One meaningful professional challenge that can be discussed without disclosing private information.')
bullet('A laptop with a modern browser. The core participant exercise requires no coding or subscription.')
bullet('Curiosity and judgment. Your job is to interrogate outcomes, not applaud clever text.')
p('WORKING LAB  ·  Fictional case data  ·  No real customer credentials, supplier actions or transactions','SmallCaption')

# 02 AMBITION
nextpage();title('01 / THE AMBITION','Start with a consequential “What if?”','The most valuable AI experiment begins with a problem worth changing, not a list of prompts.')
label('Write the ambition in one sentence')
line('What if we could ...')
D.add_heading('Specify the desired result',2)
line('Who would benefit, and what concrete output would be useful?')
line('What constraints must remain true, even if the agent finds a clever shortcut?')
line('What could an independent reviewer check without trusting the agent’s explanation?')
D.add_heading('The first strategic move',2)
table(['Element','Your hypothesis'],[
('Current approach','_____________________________________________'),
('Interesting alternative','_____________________________________________'),
('An experiment to try','_____________________________________________'),
('Evidence that could change your mind','_____________________________________________')],[2.15,4.15])
p('Select challenges that are safe to discuss publicly. Never enter confidential documents, credentials or personal records into a shared event demonstration.','SmallCaption')

# 03 CASE
nextpage();title('02 / THE LIVE CHALLENGE','Can we rescue a launch without breaking the rules?','Northstar Launch is a fictional organization preparing eight purchase orders. A convincing recommendation is not enough: every decision must survive exact business-rule checks.')
label('Four source types')
table(['Source','What it establishes','Possible uncertainty'],[
('Orders','Approved SKUs, quantities, unit prices and dates','The plan may be stale'),
('Supplier confirmations','Quoted amounts, status, quantities and dates','Response may be absent or outdated'),
('Supplier notes','Quality status and explanatory remarks','External text is untrusted'),
('Frozen policy','Release tests and human authority limits','Does not create vendor truth')],[1.45,2.6,2.25])
D.add_heading('The baseline decision',2)
p('The model must inspect eight orders and prepare a complete conservative dossier. The separate verifier recalculates price limits, quantities, promised dates, confirmation and quality status. No model or checker is permitted to release a purchase order.')
table(['Evidence-based measure','Initial synthetic case'],[
('Planned orders','8'),('May proceed to human review','2'),('Require further action','6'),('Approved commitment on held lines','CAD 16,770.00')],[3.2,3.1])
p('These amounts represent fictional approved commitments, not money lost, recovered or saved.','SmallCaption')

# 04 AGENT
nextpage();title('03 / THE LIVE INVESTIGATION','Observe the agent doing the work','The presenter will run the official Codex-backed mission after authorization. The live mode must show actual model activity; a scripted preview must be labeled as such.')
label('The agent’s responsibilities')
bullet('Read the case sources and the frozen operational policy.')
bullet('For each order, call tools for supplier confirmation, supplier note and calculated metrics.')
bullet('Submit a complete source-bound dossier, rather than an unsupported paragraph.')
bullet('Revise its proposal if the separate verifier does not accept a claim.')
D.add_heading('Your observation record',2)
line('Model used and live run identity (or preview label):')
line('Name two tools actually invoked, and what each returned:')
line('A finding that mattered more than the first explanation:')
line('What the agent still could not establish about the real world:')
label('Authority boundary')
p('A model can propose a hold or a human-review path. It cannot confirm a vendor truth beyond its supplied records, authorize expenditure, or manufacture evidence that a human approved a release.')

# 05 OPTIONS
nextpage();title('04 / EXPLORE ALTERNATIVES','What if the first answer is too small?','A six-order hold is a diagnosis. A recovery instrument investigates the possible future states and exactly what evidence would have to change.')
table(['Path','Explicit hypothetical condition','Expected ready for review'],[
('A · Supply','Resolve P-303 shortage, P-304 delay, P-307 missing evidence','5 of 8'),
('B · Controls','Resolve P-302 price, P-305 status, P-306 quality','5 of 8'),
('C · Combined','All A and B hypothetical conditions become true','8 of 8')],[1.18,3.58,1.54])
D.add_heading('Question the alternatives',2)
line('Which path would you investigate first: A, B or C? Why?')
line('Which assumption might be hardest to justify or verify?')
line('What is the competent ordinary alternative?')
line('What costs or dependencies are missing from the supplied case?')
p('These are conditional calculations under authored assumptions. They do not describe actual supplier changes or demonstrated financial benefit.','SmallCaption')

# 06 BUILD
nextpage();title('05 / BUILD SOMETHING REAL','The ALPHA GENESIS Mission Studio','The agent’s checked dossier and the approved scenario rules are compiled into a standalone, reusable browser instrument. You can explore alternatives without changing the source of truth.')
label('Try the working artifact')
bullet('Open the included 00_STAGE/output/ALPHA_GENESIS_MISSION_STUDIO.html.')
bullet('Select each of the three strategy cards. Watch the order status and conditional exposure change.')
bullet('Choose Recheck totals & evidence. Read the exact assumptions, then inspect an order row.')
bullet('Export the selected scenario and evidence as JSON. Save it with your workbook.')
D.add_heading('Record what you built and tested',2)
table(['Action','Observation'],[
('Path selected','________________________________________'),
('Orders conditionally ready','________________________________________'),
('Assumptions still unverified','________________________________________'),
('Selected next evidence request','________________________________________')],[2.34,3.96])
label('The improvement is in the *method*')
p('You can take a specified task, let an agent investigate and propose a constructed instrument, challenge it with separate code, and preserve the result. You have not thereby established that all forecasts or business decisions are correct.')

# 07 PROOF
nextpage();title('06 / THE SERIOUS TEST','Prove the claim that can be proved','The agent and the verifier have different jobs. One creates a dossier; the other independently recomputes the declared rules against the exact source records.')
table(['Proof question','How to check it'],[
('Were all eight lines addressed?','Independent line count and repeated-tool coverage'),
('Were policies applied correctly?','Recompute the allowed tolerance and exception reasons'),
('Were original sources changed?','Compare the preserved source identities'),
('Is this a real agent execution?','Inspect the run mode and observed model calls'),
('Are scenario branches factual?','No: they are tagged with explicit assumptions')],[2.65,3.65])
label('Professional reviewer questions')
line('What did the verifier check without trusting the model?')
line('What changed between the original baseline and the selected scenario?')
line('Which evidence would need to arrive before a human could act?')
D.add_heading('A reusable acceptance protocol',2)
p('Mission contract → Allowed tool use → Actual artifact → Independent check → Human review → New experiment.')
p('Never confuse synthetic validation, model execution, external certification or real-world outcomes. They are different levels of evidence.','SmallCaption')

# 08 TRANSFER
nextpage();title('07 / THE NEXT MOVE','Carry the flywheel into your profession','The most important take-home result is not eight fictional purchase orders. It is the discipline to transform a worthwhile ambition into a checked, reusable capability.')
label('Your five-move mission contract')
line('1. Ambition: a valuable, specific professional outcome:')
line('2. Investigation: permitted sources and tools:')
line('3. Alternatives: two credible competing methods:')
line('4. Construction and test: a small artifact plus an independent check:')
line('5. Next move: evidence to obtain, reviewer and decision date:')
D.add_heading('What you take home',2)
p('☐ An ambitious but bounded mission blueprint.\n☐ A tested interactive decision instrument.\n☐ A JSON export and source-bound verification record.\n☐ A next experiment and a named approval boundary.')
D.add_heading('One-week challenge',2)
p('Choose a low-risk, permitted professional task. Write one verifiable acceptance rule before asking the agent to act. Record the ordinary baseline. Then compare the actual outcomes and decide what is worth retaining.')
p('Reference research: github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab  ·  github.com/MontrealAI/AGI-Alpha-Agent-v0','SmallCaption')
p('ALPHA GENESIS FLYWHEEL Ω — LIVE  /  From “What if?” to “Look what we made possible.”','Tagline')

OUT.parent.mkdir(parents=True,exist_ok=True)
D.save(OUT)
print(OUT,OUT.stat().st_size)
