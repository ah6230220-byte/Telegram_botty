import os, aiosqlite
from config import DATABASE_PATH
os.makedirs(os.path.dirname(DATABASE_PATH) or ".", exist_ok=True)
async def init_db():
 async with aiosqlite.connect(DATABASE_PATH) as d:
  await d.executescript('''
  PRAGMA journal_mode=WAL;
  CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, banned INTEGER DEFAULT 0);
  CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY AUTOINCREMENT, owner INTEGER, name TEXT, token TEXT, folder TEXT, status TEXT DEFAULT 'pending', reason TEXT DEFAULT '', created TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, actor INTEGER, action TEXT, details TEXT, created TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
  ''')
  cols={r[1] for r in await (await d.execute("PRAGMA table_info(projects)")).fetchall()}
  if "token" not in cols:
   await d.execute("ALTER TABLE projects ADD COLUMN token TEXT NOT NULL DEFAULT ''")
   if "token_enc" in cols:
    await d.execute("UPDATE projects SET status='needs_token', reason='Please submit token again after migration'")
  await d.commit()
 try: os.chmod(DATABASE_PATH, 0o600)
 except OSError: pass
async def run(sql,args=(),fetch="none"):
 async with aiosqlite.connect(DATABASE_PATH) as d:
  cur=await d.execute(sql,args)
  if fetch=="all": rows=await cur.fetchall()
  elif fetch=="one": rows=await cur.fetchone()
  elif fetch=="lastrowid": rows=cur.lastrowid
  else: rows=None
  await d.commit(); return rows
async def user(uid,username=None,full_name=None):
 await run("INSERT INTO users(id,username,full_name) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET username=excluded.username,full_name=excluded.full_name",(uid,username,full_name))
async def banned(uid):
 r=await run("SELECT banned FROM users WHERE id=?",(uid,),"one"); return bool(r and r[0])
async def set_ban(uid,val):
 await run("INSERT INTO users(id,banned) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET banned=excluded.banned",(uid,int(val)))
async def count_projects(uid):
 r=await run("SELECT COUNT(*) FROM projects WHERE owner=?",(uid,),"one"); return r[0]
async def add_project(uid,name,token,folder):
 return await run("INSERT INTO projects(owner,name,token,folder) VALUES(?,?,?,?)",(uid,name,token,folder),"lastrowid")
async def project(pid):
 return await run("SELECT id,owner,name,token,folder,status,reason FROM projects WHERE id=?",(pid,),"one")
async def projects(owner=None):
 if owner is None: return await run("SELECT id,owner,name,status FROM projects ORDER BY id DESC LIMIT 40",fetch="all")
 return await run("SELECT id,name,status FROM projects WHERE owner=? ORDER BY id DESC",(owner,),"all")
async def status(pid,val,reason=""):
 await run("UPDATE projects SET status=?,reason=? WHERE id=?",(val,reason,pid))
async def audit(actor,action,details=""):
 await run("INSERT INTO audit(actor,action,details) VALUES(?,?,?)",(actor,action,details[:500]))
