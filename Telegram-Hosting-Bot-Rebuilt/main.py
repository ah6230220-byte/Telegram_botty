import asyncio, logging, re, shutil, tempfile
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ConversationHandler, ContextTypes, filters
from config import *
from utils.db import init_db, user, banned, set_ban, count_projects, add_project, project, projects, status, audit
from utils.security import inspect_python, extract_zip
from utils.runner import start, stop, logs
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
NAME, TOKEN, FILE = range(3)
sessions = {}
TOKEN_RE = re.compile(r"^\d{6,12}:[A-Za-z0-9_-]{30,}$")
NAME_RE = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
def is_admin(uid): return uid in ADMIN_IDS
def kb(rows): return InlineKeyboardMarkup(rows)
async def gate(update):
    u=update.effective_user
    if not u: return False
    await user(u.id,u.username,u.full_name)
    if not is_admin(u.id) and await banned(u.id):
        target=update.effective_message
        if target: await target.reply_text("⛔ حسابك محظور. تواصل مع المالك للاعتراض.")
        return False
    return True
async def start_cmd(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    if not await gate(update): return
    rows=[[InlineKeyboardButton("📤 رفع مشروع",callback_data="upload"),InlineKeyboardButton("📋 مشاريعي",callback_data="mine")]]
    if is_admin(update.effective_user.id): rows.append([InlineKeyboardButton("🛠 الإدارة",callback_data="admin")])
    await update.effective_message.reply_text("🚀 منصة إدارة استضافة بوتات تيليجرام\nكل مشروع ينتظر موافقة المالك قبل التشغيل.\nالفحص آلي مبدئي ولا يضمن سلامة الملف.",reply_markup=kb(rows))
async def cancel(update,ctx):
    sessions.pop(update.effective_user.id,None)
    await update.effective_message.reply_text("تم إلغاء العملية.")
    return ConversationHandler.END
async def begin_upload(update,ctx):
    q=update.callback_query; await q.answer()
    if not await gate(update): return ConversationHandler.END
    uid=q.from_user.id
    if not is_admin(uid) and await count_projects(uid)>=MAX_BOTS_PER_USER:
        await q.message.reply_text("وصلت الحد المسموح من المشاريع."); return ConversationHandler.END
    sessions[uid]={"step":"name"}
    await q.message.reply_text("أرسل اسم المشروع (3-32 حرفاً إنجليزي/أرقام/_/-). /cancel للإلغاء.")
    return NAME
async def get_name(update,ctx):
    if not await gate(update): return ConversationHandler.END
    name=(update.effective_message.text or "").strip()
    if not NAME_RE.fullmatch(name):
        await update.effective_message.reply_text("اسم غير صالح، أعد الإرسال."); return NAME
    sessions[update.effective_user.id]={"step":"token","name":name}
    await update.effective_message.reply_text("أرسل توكن البوت برسالة منفصلة؛ سأحاول حذف الرسالة فوراً.")
    return TOKEN
async def get_token(update,ctx):
    if not await gate(update): return ConversationHandler.END
    token=(update.effective_message.text or "").strip()
    try: await update.effective_message.delete()
    except TelegramError: pass
    if not TOKEN_RE.fullmatch(token):
        await update.effective_chat.send_message("صيغة التوكن غير صحيحة. أعد إرساله أو /cancel.")
        return TOKEN
    sessions[update.effective_user.id]["token"]=token
    await update.effective_chat.send_message(f"أرسل الآن ملف .py أو .zip (حد {MAX_FILE_SIZE_MB}MB).")
    return FILE
async def get_file(update,ctx):
    if not await gate(update): return ConversationHandler.END
    msg=update.effective_message; doc=msg.document
    if not doc:
        await msg.reply_text("أرسل الملف كمرفق document بامتداد .py أو .zip، أو /cancel."); return FILE
    filename=doc.file_name or ""
    if Path(filename).suffix.lower() not in {".py",".zip"} or not doc.file_size or doc.file_size>MAX_FILE_SIZE_MB*1024*1024:
        await msg.reply_text(f"الامتداد غير مسموح أو الحجم يتجاوز {MAX_FILE_SIZE_MB}MB."); return FILE
    data=sessions.get(update.effective_user.id,{})
    if not data.get("token") or not data.get("name"):
        await msg.reply_text("انتهت جلسة الرفع، ابدأ من /start."); return ConversationHandler.END
    HOSTING_DIR.mkdir(parents=True,exist_ok=True)
    folder=Path(tempfile.mkdtemp(prefix=f"{update.effective_user.id}_",dir=HOSTING_DIR)).resolve()
    temp=folder/("upload"+Path(filename).suffix.lower())
    try:
        remote=await doc.get_file(); await remote.download_to_drive(custom_path=str(temp))
        if filename.lower().endswith(".zip"):
            extract_zip(temp,folder); temp.unlink(missing_ok=True)
        else: temp.replace(folder/"main.py")
        if not any((folder/n).is_file() for n in ("main.py","bot.py","app.py")):
            raise ValueError("يجب وجود main.py أو bot.py أو app.py في جذر المشروع.")
        if any(p.is_file() and p.name.lower() in {".env","id_rsa","id_ed25519"} for p in folder.rglob("*")):
            raise ValueError("الأرشيف يحتوي ملف أسرار ممنوع مثل .env أو مفتاح SSH.")
        findings=inspect_python(folder)
        # No Fernet: stored locally in SQLite; protect the database and its backups.
        pid=await add_project(update.effective_user.id,data["name"],data["token"],str(folder))
        await audit(update.effective_user.id,"upload",f"project={pid}; findings={len(findings)}")
        summary="\n".join("• "+x for x in findings[:12]) if findings else "لم تظهر مؤشرات من القواعد البسيطة."
        if len(findings)>12: summary+=f"\n… ومؤشرات أخرى: {len(findings)-12}"
        await msg.reply_text(f"✅ استلمنا المشروع #{pid}: {data['name']}\nالحالة: بانتظار مراجعة المالك؛ لم يتم تشغيله.\n\nنتائج الفحص:\n{summary}\n\nالفحص الآلي لا يثبت السلامة.")
        buttons=kb([[InlineKeyboardButton("🔎 مراجعة",callback_data=f"inspect:{pid}"),InlineKeyboardButton("⛔ رفض",callback_data=f"reject:{pid}")]])
        for aid in ADMIN_IDS:
            try: await ctx.bot.send_message(aid,f"📥 طلب جديد #{pid}\nالمالك: {update.effective_user.id}\nالاسم: {data['name']}\n{summary}",reply_markup=buttons)
            except TelegramError: pass
    except Exception as e:
        shutil.rmtree(folder,ignore_errors=True)
        await msg.reply_text(f"فشل رفع الملف: {str(e)[:250]}")
    finally: sessions.pop(update.effective_user.id,None)
    return ConversationHandler.END
async def mine(update,ctx):
    if not await gate(update): return
    rows=await projects(update.effective_user.id)
    await update.effective_message.reply_text("\n".join(f"#{r[0]} {r[1]} — {r[2]}" for r in rows) or "ما عندك مشاريع.")
async def admin_panel(update,ctx):
    if not await gate(update): return
    uid=update.effective_user.id
    if not is_admin(uid): return await update.effective_message.reply_text("هذا الأمر للمالك فقط.")
    rows=await projects()
    if not rows: return await update.effective_message.reply_text("ماكو مشاريع حالياً.")
    for r in rows[:30]:
        await update.effective_message.reply_text(f"#{r[0]} {r[2]} — {r[3]} — المالك {r[1]}",
          reply_markup=kb([[InlineKeyboardButton("فحص",callback_data=f"inspect:{r[0]}"),InlineKeyboardButton("موافقة",callback_data=f"approve:{r[0]}"),InlineKeyboardButton("رفض",callback_data=f"reject:{r[0]}")],[InlineKeyboardButton("تشغيل",callback_data=f"run:{r[0]}"),InlineKeyboardButton("إيقاف",callback_data=f"stop:{r[0]}"),InlineKeyboardButton("سجلات",callback_data=f"logs:{r[0]}")]]))
async def action(update,ctx):
    q=update.callback_query; await q.answer()
    if not await gate(update): return
    if not is_admin(q.from_user.id): return await q.message.reply_text("هذا الأمر للمالك فقط.")
    action_name,raw=q.data.split(":"); pid=int(raw); row=await project(pid)
    if not row: return await q.message.reply_text("المشروع غير موجود.")
    _,owner,name,token,folder,st,reason=row
    try:
        if action_name=="inspect":
            findings=inspect_python(folder)
            return await q.message.reply_text("نتائج الفحص:\n"+("\n".join("• "+x for x in findings[:20]) if findings else "لا توجد مؤشرات مطابقة.")+"\n\nهذا ليس ضمان أمان.")
        if action_name=="approve": await status(pid,"approved",""); result="تمت الموافقة؛ التشغيل يدوي."
        elif action_name=="reject":
            try: await stop(pid)
            except Exception: pass
            await status(pid,"rejected","رفضته الإدارة"); result="تم رفض المشروع."
        elif action_name=="run":
            await start(pid); result="تم التشغيل."
        elif action_name=="stop":
            await stop(pid); result="تم الإيقاف."
        elif action_name=="logs":
            return await q.message.reply_text((await logs(pid))[-3000:] or "لا توجد سجلات.")
        else: return
        await audit(q.from_user.id,action_name,str(pid))
        try: await ctx.bot.send_message(owner,f"تحديث مشروعك #{pid}: {result}")
        except TelegramError: pass
        await q.message.reply_text(result)
    except Exception as e: await q.message.reply_text(f"تعذر تنفيذ العملية: {str(e)[:250]}")
async def ban_cmd(update,ctx):
    if not await gate(update) or not is_admin(update.effective_user.id): return
    if not ctx.args or not ctx.args[0].isdigit(): return await update.effective_message.reply_text("الاستخدام: /ban USER_ID")
    uid=int(ctx.args[0]); await set_ban(uid,True); await audit(update.effective_user.id,"ban",str(uid))
    for r in await projects(uid):
        try: await stop(r[0])
        except Exception: pass
    try: await ctx.bot.send_message(uid,"⛔ تم حظرك من المنصة وإيقاف مشاريعك. تواصل مع المالك للاعتراض.")
    except TelegramError: pass
    await update.effective_message.reply_text(f"تم حظر {uid}.")
async def unban_cmd(update,ctx):
    if not await gate(update) or not is_admin(update.effective_user.id): return
    if not ctx.args or not ctx.args[0].isdigit(): return await update.effective_message.reply_text("الاستخدام: /unban USER_ID")
    uid=int(ctx.args[0]); await set_ban(uid,False); await audit(update.effective_user.id,"unban",str(uid))
    try: await ctx.bot.send_message(uid,"✅ تم رفع الحظر عنك.")
    except TelegramError: pass
    await update.effective_message.reply_text(f"تم رفع الحظر عن {uid}.")
async def errors(update,ctx):
    logging.error("Unhandled update error",exc_info=ctx.error)
async def post_init(app): await init_db()
def main():
    validate_config()
    app=Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    flow=ConversationHandler(entry_points=[CallbackQueryHandler(begin_upload,pattern="^upload$")],states={
      NAME:[MessageHandler(filters.TEXT & ~filters.COMMAND,get_name)],
      TOKEN:[MessageHandler(filters.TEXT & ~filters.COMMAND,get_token)],
      FILE:[MessageHandler(filters.Document.ALL,get_file),MessageHandler(filters.TEXT & ~filters.COMMAND,get_file)]},
      fallbacks=[CommandHandler("cancel",cancel)],allow_reentry=True)
    app.add_handler(CommandHandler("start",start_cmd)); app.add_handler(CommandHandler("cancel",cancel))
    app.add_handler(CommandHandler("mybots",mine)); app.add_handler(CommandHandler("admin",admin_panel))
    app.add_handler(CommandHandler("ban",ban_cmd)); app.add_handler(CommandHandler("unban",unban_cmd))
    app.add_handler(flow); app.add_handler(CallbackQueryHandler(action,pattern=r"^(inspect|approve|reject|run|stop|logs):\d+$"))
    app.add_handler(CallbackQueryHandler(mine,pattern="^mine$")); app.add_handler(CallbackQueryHandler(admin_panel,pattern="^admin$"))
    app.add_error_handler(errors); app.run_polling(allowed_updates=Update.ALL_TYPES)
if __name__=="__main__": main()
