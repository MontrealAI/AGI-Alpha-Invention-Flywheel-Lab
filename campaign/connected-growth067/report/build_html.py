from pathlib import Path
import re,html
R=Path(__file__).resolve().parent
lines=(R/'README.md').read_text().splitlines()
def inline(s):
 s=html.escape(s)
 s=re.sub(r'!\[([^\]]*)\]\(([^)]+)\)',r'<img src="\2" alt="\1" loading="lazy">',s)
 s=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',r'<a href="\2">\1</a>',s)
 s=re.sub(r'`([^`]+)`',r'<code>\1</code>',s)
 s=re.sub(r'\*\*(.+?)\*\*',r'<strong>\1</strong>',s)
 s=re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)',r'<em>\1</em>',s)
 return s
parts=[];i=0
while i<len(lines):
 line=lines[i]
 if not line.strip():i+=1;continue
 if line.startswith('```'):
  i+=1;buf=[]
  while i<len(lines) and not lines[i].startswith('```'):buf.append(lines[i]);i+=1
  parts.append('<pre><code>'+html.escape('\n'.join(buf))+'</code></pre>');i+=1;continue
 if line.startswith('#'):
  level=len(line)-len(line.lstrip('#'));title=line[level:].strip();ident=re.sub('[^a-z0-9]+','-',title.lower()).strip('-')
  parts.append(f'<h{level} id="{ident}">'+inline(title)+f'</h{level}>');i+=1;continue
 if line.startswith('|') and i+1<len(lines) and re.match(r'^\|[ :|\-]+$',lines[i+1]):
  rows=[]
  while i<len(lines) and lines[i].startswith('|'):
   if not re.match(r'^\|[ :|\-]+$',lines[i]):rows.append([x.strip() for x in lines[i].strip('|').split('|')])
   i+=1
  parts.append('<div class="table-wrap"><table><thead><tr>'+''.join('<th scope="col">'+inline(x)+'</th>' for x in rows[0])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+inline(x)+'</td>' for x in row)+'</tr>' for row in rows[1:])+'</tbody></table></div>');continue
 if line.startswith('- '):
  buf=[]
  while i<len(lines) and lines[i].startswith('- '):buf.append('<li>'+inline(lines[i][2:])+'</li>');i+=1
  parts.append('<ul>'+''.join(buf)+'</ul>');continue
 buf=[line];i+=1
 while i<len(lines) and lines[i].strip() and not lines[i].startswith(('#','|','- ','```')):buf.append(lines[i]);i+=1
 parts.append('<p>'+inline(' '.join(buf))+'</p>')
css="""*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f8f7fc;color:#24213b;font:17px/1.7 system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}a{color:#6030c5;text-underline-offset:3px}a:hover{color:#087f8c}:focus-visible{outline:3px solid #bba6ff;outline-offset:4px}.top{background:#fff;border-bottom:1px solid #e5deef;padding:20px max(24px,calc((100% - 1120px)/2));display:flex;justify-content:space-between;gap:20px;align-items:center}.brand{font-size:15px;letter-spacing:.1em;font-weight:800;color:#6030c5;text-decoration:none}.tag{font-size:12px;color:#665f79}.wrap{max-width:1120px;margin:38px auto 70px;background:#fff;border:1px solid #e5deef;border-radius:20px;padding:48px 50px;box-shadow:0 12px 40px #3c21600a}h1{font-size:clamp(32px,4.8vw,52px);line-height:1.12;letter-spacing:-.04em;margin:0 0 14px}h2{font-size:27px;line-height:1.25;margin:48px 0 18px;letter-spacing:-.02em}h1+h2{font-size:22px;color:#665f79;margin-top:16px;font-weight:500}p{margin:17px 0}strong{font-weight:700}img{display:block;width:100%;height:auto;border:1px solid #ece7f4;border-radius:12px;margin:24px 0}.table-wrap{overflow-x:auto;margin:22px 0 30px;border:1px solid #e5deef;border-radius:10px}table{border-collapse:collapse;width:100%;font-size:15px}th,td{text-align:left;padding:13px 17px;border-bottom:1px solid #eee9f5;vertical-align:top}th{background:#f3effb;font-weight:650}tr:last-child td{border-bottom:0}td:last-child{font-variant-numeric:tabular-nums}code{font:13px/1.6 ui-monospace,SFMono-Regular,Consolas,monospace;overflow-wrap:anywhere;background:#f5f2fa;padding:2px 4px;border-radius:3px}pre{padding:20px;background:#f5f2fa;border:1px solid #e5deef;border-radius:10px;overflow:auto}pre code{white-space:pre;overflow-wrap:normal;padding:0}li{margin:10px 0}ul{padding-left:25px}.foot{max-width:1120px;margin:0 auto 45px;font-size:13px;color:#665f79;padding:0 20px}.skip{position:absolute;top:-80px;left:20px;background:#fff;padding:10px}.skip:focus{top:10px}@media(max-width:700px){body{font-size:16px}.wrap{margin:18px 12px 40px;padding:28px 20px;border-radius:14px}h2{font-size:24px;margin-top:36px}.top{padding:18px 20px;align-items:flex-start}.tag{max-width:130px;text-align:right}th,td{padding:11px 12px;font-size:14px}img{border-radius:8px}pre{padding:14px}}"""
out='<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Independently replayed Growth 067 control case with exact native profit, cash, volume and cost charts. Conditional simulation only."><title>Growth 067 Interim Report | AGI Alpha</title><style>'+css+'</style></head><body><a class="skip" href="#report">Skip to report</a><header class="top"><a class="brand" href="https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab">AGI ALPHA</a><span class="tag">RESEARCH REPORT<br>INTERIM • CONTROL CASE</span></header><main class="wrap" id="report">'+'\n'.join(parts)+'</main><footer class="foot">Public experiment evidence · Static report · No real customers or payments claimed</footer></body></html>\n'
(R/'index.html').write_text(out)
print('HTML bytes',len(out.encode()))
