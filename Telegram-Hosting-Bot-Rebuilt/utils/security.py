import ast, re, stat, zipfile
from pathlib import Path, PurePosixPath
from config import MAX_EXTRACTED_MB
# Conservative heuristic scanner: findings require human review; this is not antivirus.
SUSPICIOUS = [
 (r'\b(eval|exec)\s*\(', 'dynamic code execution'),
 (r'\b(subprocess\.(Popen|run|call)|os\.system)\s*\(', 'process/shell execution'),
 (r'\b(shutil\.rmtree|os\.remove|os\.unlink)\s*\(', 'file deletion API'),
 (r'\b(requests\.(get|post)|urllib\.request)\s*\(', 'outbound HTTP request'),
 (r'\b(botfather|api\.telegram\.org/bot)', 'Telegram bot API/token-related string'),
 (r'\b(socket|pty)\.', 'low-level networking/terminal access'),
 (r'\b(pip|apt-get)\s+install\b', 'package installation command'),
]
HOSTING_MARKERS = ('docker.from_env', 'docker.sock', 'subprocess.run(["docker"', 'docker run', 'hosting bot', 'host other bots')
def inspect_python(path):
 findings=[]
 for p in Path(path).rglob("*.py"):
  try: src=p.read_text("utf-8",errors="replace")
  except OSError: continue
  try: ast.parse(src)
  except SyntaxError as e: findings.append(f"{p.name}: syntax error at line {e.lineno}")
  low=src.lower()
  for pattern,label in SUSPICIOUS:
   if re.search(pattern,src,re.I): findings.append(f"{p.name}: possible {label}")
  if any(x in low for x in HOSTING_MARKERS): findings.append(f"{p.name}: possible bot-hosting / container-management behavior")
  if re.search(r'\d{6,12}:[A-Za-z0-9_-]{25,}',src): findings.append(f"{p.name}: possible hard-coded Telegram token")
 return sorted(set(findings))
def extract_zip(src,dest):
 root=Path(dest).resolve(); total=0
 with zipfile.ZipFile(src) as z:
  infos=z.infolist()
  if len(infos)>200: raise ValueError("Archive has more than 200 entries")
  for i in infos:
   pp=PurePosixPath(i.filename); mode=(i.external_attr>>16)&0xffff
   if pp.is_absolute() or ".." in pp.parts or not pp.parts or stat.S_ISLNK(mode): raise ValueError("Unsafe ZIP path or symlink")
   total += i.file_size
   if total>MAX_EXTRACTED_MB*1024*1024: raise ValueError("Expanded archive exceeds configured limit")
  for i in infos:
   if i.is_dir(): (root / PurePosixPath(i.filename)).mkdir(parents=True,exist_ok=True)
   else:
    target=(root/PurePosixPath(i.filename)).resolve()
    if root not in target.parents: raise ValueError("Invalid archive path")
    target.parent.mkdir(parents=True,exist_ok=True)
    with z.open(i) as src, open(target,"wb") as dst:
     import shutil; shutil.copyfileobj(src,dst)
    target.chmod(0o644)
