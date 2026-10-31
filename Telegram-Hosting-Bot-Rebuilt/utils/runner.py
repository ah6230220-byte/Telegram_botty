import asyncio, shutil
from pathlib import Path
from config import DOCKER_IMAGE, CONTAINER_MEMORY, CONTAINER_CPUS, CONTAINER_PIDS, CONTAINER_NETWORK
from utils.db import project, status
async def docker(*args, timeout=60):
 if not shutil.which("docker"): raise RuntimeError("Docker is not installed")
 p=await asyncio.create_subprocess_exec("docker",*map(str,args),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
 try: out,err=await asyncio.wait_for(p.communicate(),timeout)
 except asyncio.TimeoutError: p.kill(); await p.wait(); raise RuntimeError("Docker command timed out")
 if p.returncode: raise RuntimeError((err.decode(errors="replace") or out.decode(errors="replace"))[-600:])
 return out.decode(errors="replace").strip()
async def stop(pid):
 try: await docker("rm","-f",f"hosted-project-{int(pid)}")
 except Exception: pass
 await status(pid,"stopped")
async def start(pid):
 r=await project(pid)
 if not r: raise RuntimeError("Project not found")
 _,owner,name,token,folder,st,reason=r
 if st not in ("approved","stopped","error"): raise RuntimeError("Project must be approved before launch")
 path=Path(folder).resolve()
 if not path.is_dir(): raise RuntimeError("Project files are missing")
 entry=next((n for n in ("main.py","bot.py","app.py") if (path/n).is_file()),None)
 if not entry: raise RuntimeError("Project needs main.py, bot.py or app.py at root")
 await stop(pid)
 await docker("run","-d","--name",f"hosted-project-{int(pid)}","--restart","unless-stopped",
  "--memory",CONTAINER_MEMORY,"--cpus",CONTAINER_CPUS,"--pids-limit",CONTAINER_PIDS,
  "--read-only","--tmpfs","/tmp:rw,noexec,nosuid,size=32m","--cap-drop","ALL",
  "--security-opt","no-new-privileges:true","--user","10001:10001","--network",CONTAINER_NETWORK,
  "-e",f"BOT_TOKEN={token}","-v",f"{path}:/app:ro","-w","/app",DOCKER_IMAGE,"python","-B",entry)
 await status(pid,"running")
async def logs(pid): return await docker("logs","--tail","40",f"hosted-project-{int(pid)}")
