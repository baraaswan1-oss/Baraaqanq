
import json, asyncio, logging, os, random, re, time
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReactionTypeEmoji, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

logging.basicConfig(level=logging.WARNING)

# قراءة المتغيرات من بيئة Render
TOKEN = os.environ.get("TOKEN", "8567697709:AAEgJBn6zW1kBYAjVoRuVGB09YaxhLvmMq0")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@Wa_Ql_Amlo")
TEST_CHANNEL_ID = os.environ.get("TEST_CHANNEL_ID", "@bvcxh852")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "6018370288"))
DATA_FILE = "data.json"
TELEGRAM_CHANNEL_LINK = os.environ.get("TELEGRAM_CHANNEL_LINK", "https://t.me/Wa_Ql_Amlo")
WHATSAPP_CHANNEL_LINK = os.environ.get("WHATSAPP_CHANNEL_LINK", "https://whatsapp.com/channel/0029VbCFQqqFMqrdjDlO6h0e")

GUARANTEED_REACTION_EMOJIS = ["❤️", "🔥", "⭐", "👍", "🎉", "😍", "👏", "🙏", "🤲", "🕋"]
ISLAMIC_REACTION_EMOJIS = ["❤️", "🤲", "🙏", "⭐", "🕋", "☪️", "🕌", "📿", "🕯️", "📖"]

def format_text(text):
    return re.sub(r'\*(.*?)\*', r'<b>\1</b>', text) if text else ""

def load_data():
    defaults = {
        "groups": [], 
        "last_channel_msg_id": None, 
        "last_channel_msg_data": None,
        "random_messages": [], 
        "random_enabled": False, 
        "random_interval": 60, 
        "scheduled_messages": [], 
        "repeat_last_enabled": False, 
        "repeat_interval": 30, 
        "reaction_bots": [], 
        "operation_logs": [],
        "last_operation_time": None,
        "test_mode": False,
        "reaction_emoji_type": "guaranteed",
        "settings": {
            "emoji_type": "guaranteed",
            "test_mode": False
        }
    }
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding='utf-8') as f:
                d = json.load(f)
                for k, v in defaults.items():
                    if k not in d:
                        d[k] = v
                for group in d["groups"]:
                    if "no_forward" not in group:
                        group["no_forward"] = False
                for msg in d.get("scheduled_messages", []):
                    if "delete_after" not in msg:
                        msg["delete_after"] = 0
                    if "sent_at" not in msg:
                        msg["sent_at"] = None
                    if "sent_message_id" not in msg:
                        msg["sent_message_id"] = None
                    if "delete_at" not in msg:
                        msg["delete_at"] = None
                return d
        except Exception as e:
            logging.error(f"Error loading data: {e}")
    return defaults

def save_data(d):
    with open(DATA_FILE, "w", encoding='utf-8') as f: 
        json.dump(d, f, ensure_ascii=False, indent=4)

def add_operation_log(operation_type, details, success=True, error=None):
    log_entry = {
        "timestamp": datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d %H:%M:%S"),
        "type": operation_type,
        "details": details,
        "success": success,
        "error": error
    }
    data["operation_logs"].append(log_entry)
    if len(data["operation_logs"]) > 50:
        data["operation_logs"] = data["operation_logs"][-50:]
    save_data(data)

data = load_data()

def get_target_channel():
    return TEST_CHANNEL_ID if data.get("test_mode", False) else CHANNEL_ID

def get_reaction_emoji():
    emoji_type = data.get("reaction_emoji_type", "guaranteed")
    if emoji_type == "islamic":
        return random.choice(ISLAMIC_REACTION_EMOJIS)
    elif emoji_type == "simple":
        return "❤️"
    else:
        return random.choice(GUARANTEED_REACTION_EMOJIS)

async def test_reaction_bot(bot_token, bot_name, channel_id):
    try:
        async with Bot(bot_token) as rb:
            me = await rb.get_me()
            try:
                await rb.send_message(me.id, "✅ اختبار البوت: البوت يعمل بشكل صحيح")
                chat = await rb.get_chat(channel_id)
                member = await chat.get_member(me.id)
                is_admin = member.status in ['administrator', 'creator']
                
                return {
                    "success": True,
                    "bot_name": me.first_name,
                    "is_admin": is_admin,
                    "status": member.status,
                    "chat_title": chat.title
                }
            except Exception as e:
                return {
                    "success": False,
                    "bot_name": me.first_name,
                    "error": f"خطأ في الاختبار: {str(e)[:100]}",
                    "is_admin": False
                }
                
    except Exception as e:
        return {
            "success": False,
            "bot_name": bot_name,
            "error": f"توكن غير صالح: {str(e)[:100]}",
            "is_admin": False
        }

async def apply_reactions(context, chat_id, msg_id, is_chan=False):
    log_details = {"chat_id": chat_id, "msg_id": msg_id, "is_chan": is_chan}
    
    try: 
        await context.bot.set_message_reaction(
            chat_id=chat_id, 
            message_id=msg_id, 
            reaction=[ReactionTypeEmoji("❤️")]
        )
        add_operation_log("reaction_main", log_details, True)
    except Exception as e: 
        add_operation_log("reaction_main", log_details, False, str(e))
        logging.error(f"Error in main reaction: {e}")
    
    if is_chan and chat_id == get_target_channel() and data.get("reaction_bots"):
        reaction_logs = []
        error_details = []
        successful_bots = 0
        failed_bots = 0
        target_channel = get_target_channel()
        
        for b in data["reaction_bots"]:
            bot_name = b.get('name', 'غير معروف')
            bot_token = b.get('token', '').strip()
            
            if not bot_token:
                error_details.append(f"{bot_name}: ❌ التوكن فارغ")
                failed_bots += 1
                continue
            
            try:
                reaction_emoji = get_reaction_emoji()
                await asyncio.sleep(3)
                
                async with Bot(bot_token) as rb:
                    try:
                        if reaction_emoji not in GUARANTEED_REACTION_EMOJIS[:3]:
                            test_emoji = "❤️"
                        else:
                            test_emoji = reaction_emoji
                        
                        await rb.set_message_reaction(
                            chat_id=target_channel, 
                            message_id=msg_id, 
                            reaction=[ReactionTypeEmoji(test_emoji)]
                        )
                        reaction_logs.append(f"{bot_name}: ✅ {test_emoji}")
                        successful_bots += 1
                        
                    except Exception as reaction_error:
                        try:
                            await asyncio.sleep(1)
                            alt_emoji = "🔥" if test_emoji == "❤️" else "❤️"
                            await rb.set_message_reaction(
                                chat_id=target_channel,
                                message_id=msg_id,
                                reaction=[ReactionTypeEmoji(alt_emoji)]
                            )
                            reaction_logs.append(f"{bot_name}: ✅ {alt_emoji} (بديل)")
                            successful_bots += 1
                            
                        except Exception as alt_error:
                            error_msg = f"{bot_name}: ❌ {str(alt_error)[:100]}"
                            error_details.append(error_msg)
                            failed_bots += 1
                            
                            add_operation_log("reaction_bot_error", {
                                "bot": bot_name,
                                "first_emoji": test_emoji,
                                "second_emoji": alt_emoji,
                                "error": str(alt_error),
                                "error_type": type(alt_error).__name__
                            }, False)
                
            except Exception as e:
                error_msg = f"{bot_name}: ❌ خطأ في الاتصال: {str(e)[:100]}"
                error_details.append(error_msg)
                failed_bots += 1
                add_operation_log("reaction_bot_connection_error", {
                    "bot": bot_name,
                    "error": str(e)
                }, False)
        
        if successful_bots > 0:
            add_operation_log("reaction_bots_success", {
                "reactions": reaction_logs,
                "total_bots": len(data["reaction_bots"]),
                "successful": successful_bots,
                "failed": failed_bots,
                "channel": target_channel
            }, True)
        
        if error_details:
            add_operation_log("reaction_bots_failed", {
                "errors": error_details,
                "total_bots": len(data["reaction_bots"]),
                "successful": successful_bots,
                "failed": failed_bots
            }, False)
        
        try:
            report = f"📊 تقرير تفاعل البوتات:\n\n"
            report += f"📺 القناة: {target_channel}\n"
            report += f"🔢 الإجمالي: {len(data['reaction_bots'])}\n"
            report += f"✅ الناجحة: {successful_bots}\n"
            report += f"❌ الفاشلة: {failed_bots}\n\n"
            
            if reaction_logs:
                report += "✅ الناجحة:\n" + "\n".join(reaction_logs) + "\n\n"
            
            if error_details and failed_bots > 0:
                report += "❌ الفاشلة:\n" + "\n".join(error_details[:3])
            
            await context.bot.send_message(ADMIN_ID, report[:4000])
        except Exception as e:
            logging.error(f"Error sending reaction report: {e}")

def remove_whatsapp_suffix(text):
    if text and WHATSAPP_CHANNEL_LINK in text:
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            if WHATSAPP_CHANNEL_LINK not in line and "لمتابعة القناة على الواتساب" not in line:
                cleaned_lines.append(line)
        return '\n'.join(cleaned_lines).strip()
    return text

def add_whatsapp_suffix(text):
    text = remove_whatsapp_suffix(text)
    return text + f"\n\n📢 لمتابعة القناة على الواتساب:\n{WHATSAPP_CHANNEL_LINK}"

def add_telegram_suffix(text):
    text = remove_whatsapp_suffix(text)
    if text and TELEGRAM_CHANNEL_LINK in text:
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            if TELEGRAM_CHANNEL_LINK not in line and "لمتابعة القناة" not in line:
                cleaned_lines.append(line)
        text = '\n'.join(cleaned_lines).strip()
    
    return text + f"\n\n📢 لمتابعة القناة:\n{TELEGRAM_CHANNEL_LINK}"

async def send_msg(context, chat_id, text, mode, file_id, is_chan=False, add_suffix=False, operation_log=None, original_forward=False):
    try:
        txt = format_text(text)
        suffix_added = False
        
        if original_forward:
            pass
        elif add_suffix:
            if is_chan:
                txt = add_whatsapp_suffix(txt)
                suffix_added = True
            else:
                txt = add_telegram_suffix(txt)
                suffix_added = True
        
        if mode == "photo": 
            m = await context.bot.send_photo(chat_id, file_id, caption=txt[:1000], parse_mode="HTML")
        elif mode == "video": 
            m = await context.bot.send_video(chat_id, file_id, caption=txt[:1000], parse_mode="HTML")
        elif mode == "document":
            m = await context.bot.send_document(chat_id, file_id, caption=txt[:1000], parse_mode="HTML")
        else: 
            m = await context.bot.send_message(chat_id, txt, parse_mode="HTML", disable_web_page_preview=True)
        
        if is_chan and chat_id == get_target_channel():
            asyncio.create_task(apply_reactions(context, chat_id, m.message_id, True))
        
        if operation_log:
            log_details = {
                "chat_id": chat_id,
                "msg_id": m.message_id,
                "mode": mode,
                "suffix_added": suffix_added,
                "text_preview": text[:50] + "..." if len(text) > 50 else text
            }
            log_details.update(operation_log)
            add_operation_log("send_message", log_details, True)
        
        return m
    except Exception as e: 
        if operation_log:
            log_details = {
                "chat_id": chat_id,
                "mode": mode,
                "error": str(e)
            }
            log_details.update(operation_log)
            add_operation_log("send_message", log_details, False, str(e))
        logging.error(f"Error in send_msg: {e}")
        return None

async def forward_to_group(context, group_id, message_id, group_name, original_forward=True):
    try:
        await context.bot.forward_message(chat_id=group_id, from_chat_id=get_target_channel(), message_id=message_id)
        add_operation_log("forward_message", {
            "group_id": group_id,
            "group_name": group_name,
            "message_id": message_id,
            "type": "forward",
            "original_forward": original_forward
        }, True)
        return True
    except Exception as e:
        add_operation_log("forward_message", {
            "group_id": group_id,
            "group_name": group_name,
            "message_id": message_id,
            "type": "forward",
            "original_forward": original_forward
        }, False, str(e))
        logging.error(f"Error forwarding to group {group_name}: {e}")
        return False

async def send_to_groups(context, msg_data, operation_type="broadcast", add_suffix=False):
    forward_results = []
    copy_results = []
    
    for g in data["groups"]:
        try:
            if g.get("no_forward", False):
                text = msg_data["text"]
                m = await send_msg(context, g["id"], text, msg_data["mode"], msg_data["file_id"], 
                                 False, add_suffix=True,
                                 operation_log={
                                     "group_name": g["title"],
                                     "operation_type": operation_type,
                                     "no_forward": True
                                 })
                if m:
                    copy_results.append(f"✅ {g['title']}: تم إرسال نسخة مع اللاحقة (تليجرام)")
                else:
                    copy_results.append(f"❌ {g['title']}: فشل إرسال النسخة")
            else:
                success = await forward_to_group(context, g["id"], msg_data["message_id"], g["title"], original_forward=True)
                if success:
                    forward_results.append(f"✅ {g['title']}: تم إعادة التوجيه (مع اللاحقة الأصلية إن وجدت)")
                else:
                    forward_results.append(f"❌ {g['title']}: فشل إعادة التوجيه")
        except Exception as e:
            error_msg = f"❌ {g['title']}: {str(e)[:100]}"
            if g.get("no_forward", False):
                copy_results.append(error_msg)
            else:
                forward_results.append(error_msg)
            logging.error(f"Error sending to group {g['title']}: {e}")
            continue
    
    if forward_results or copy_results:
        report = "📊 تقرير إرسال المنشور:\n\n"
        if forward_results:
            report += "🔄 المجموعات (إعادة توجيه):\n" + "\n".join(forward_results) + "\n\n"
        if copy_results:
            report += "📝 المجموعات (نسخة مع لاحقة):\n" + "\n".join(copy_results)
        
        try:
            await context.bot.send_message(ADMIN_ID, report[:4000], disable_web_page_preview=True)
            add_operation_log("send_report", {"report_summary": f"forward: {len(forward_results)}, copy: {len(copy_results)}"}, True)
        except Exception as e:
            logging.error(f"Error sending report: {e}")

def get_main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 المجموعات", callback_data="lg"), InlineKeyboardButton("📅 الجدولة", callback_data="ls")],
        [InlineKeyboardButton("🔄 التكرار", callback_data="menu_rep"), InlineKeyboardButton("🎲 العشوائي", callback_data="menu_rnd")],
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="st"), InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings")]
    ])

def get_settings_kb():
    test_mode_status = "🟢 مفعل" if data.get("test_mode", False) else "🔴 معطل"
    emoji_type = data.get("reaction_emoji_type", "guaranteed")
    emoji_text = "مضمون" if emoji_type == "guaranteed" else "إسلامي" if emoji_type == "islamic" else "بسيط"
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🎯 الوضع التجريبي: {test_mode_status}", callback_data="toggle_test_mode")],
        [InlineKeyboardButton(f"😊 نوع الإيموجي: {emoji_text}", callback_data="toggle_emoji_type")],
        [InlineKeyboardButton("🤖 بوتات التفاعل", callback_data="menu_react")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="main")]
    ])

def get_stats_kb():
    kb = [
        [InlineKeyboardButton("📈 آخر إرسال للقناة", callback_data="last_channel")],
        [InlineKeyboardButton("🔄 آخر إعادة توجيه", callback_data="last_forward")],
        [InlineKeyboardButton("🎲 آخر رسالة عشوائية", callback_data="last_random")],
        [InlineKeyboardButton("🤖 عمليات التفاعل", callback_data="last_reactions")],
        [InlineKeyboardButton("🔍 اختبار البوتات", callback_data="test_bots")],
        [InlineKeyboardButton("📋 سجل العمليات", callback_data="operation_logs")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="main")]
    ]
    return InlineKeyboardMarkup(kb)

def format_delete_after_time(delete_after):
    if delete_after == 0:
        return "لا حذف"
    elif delete_after < 60:
        return f"{delete_after} دقيقة"
    elif delete_after < 1440:
        hours = delete_after // 60
        minutes = delete_after % 60
        if minutes > 0:
            return f"{hours} ساعة و {minutes} دقيقة"
        else:
            return f"{hours} ساعة"
    else:
        days = delete_after // 1440
        hours = (delete_after % 1440) // 60
        if hours > 0:
            return f"{days} يوم و {hours} ساعة"
        else:
            return f"{days} يوم"

async def cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    c, u = q.data, context.user_data
    if q.from_user.id != ADMIN_ID:
        return

    if c == "main": 
        u.clear()
        await q.edit_message_text("👑 لوحة التحكم", reply_markup=get_main_kb())
    
    elif c == "settings":
        await q.edit_message_text("⚙️ الإعدادات:", reply_markup=get_settings_kb())
    
    elif c == "lg":
        kb = []
        for i, g in enumerate(data["groups"]):
            no_forward_status = "✅" if g.get("no_forward", False) else "❌"
            kb.append([
                InlineKeyboardButton(f"{no_forward_status} {g['title'][:20]}", callback_data=f"tog_nofwd_{i}"),
                InlineKeyboardButton("🗑️", callback_data=f"rmg_{i}")
            ])
        kb.append([InlineKeyboardButton("➕ إضافة", callback_data="add_g"), InlineKeyboardButton("🔙 رجوع", callback_data="main")])
        await q.edit_message_text("👥 المجموعات:\n\n✅ = عدم التوجيه مفعل (يرسل نسخة مع لاحقة التليجرام)\n❌ = عدم التوجيه معطل (يعيد توجيه من القناة)", reply_markup=InlineKeyboardMarkup(kb))
    
    elif c.startswith("tog_nofwd_"):
        index = int(c[10:])
        data["groups"][index]["no_forward"] = not data["groups"][index].get("no_forward", False)
        save_data(data)
        kb = []
        for i, g in enumerate(data["groups"]):
            no_forward_status = "✅" if g.get("no_forward", False) else "❌"
            kb.append([
                InlineKeyboardButton(f"{no_forward_status} {g['title'][:20]}", callback_data=f"tog_nofwd_{i}"),
                InlineKeyboardButton("🗑️", callback_data=f"rmg_{i}")
            ])
        kb.append([InlineKeyboardButton("➕ إضافة", callback_data="add_g"), InlineKeyboardButton("🔙 رجوع", callback_data="main")])
        status = "تم تفعيل" if data["groups"][index]["no_forward"] else "تم تعطيل"
        await q.edit_message_text(f"✅ {status} خاصية عدم التوجيه للمجموعة\n👥 المجموعات:\n\n✅ = عدم التوجيه مفعل (يرسل نسخة مع لاحقة التليجرام)\n❌ = عدم التوجيه معطل (يعيد توجيه من القناة)", reply_markup=InlineKeyboardMarkup(kb))
    
    elif c.startswith("rmg_"):
        index = int(c[4:])
        removed_group = data["groups"].pop(index)
        save_data(data)
        kb = []
        for i, g in enumerate(data["groups"]):
            no_forward_status = "✅" if g.get("no_forward", False) else "❌"
            kb.append([
                InlineKeyboardButton(f"{no_forward_status} {g['title'][:20]}", callback_data=f"tog_nofwd_{i}"),
                InlineKeyboardButton("🗑️", callback_data=f"rmg_{i}")
            ])
        kb.append([InlineKeyboardButton("➕ إضافة", callback_data="add_g"), InlineKeyboardButton("🔙 رجوع", callback_data="main")])
        await q.edit_message_text(f"✅ تم حذف المجموعة: {removed_group['title']}\n👥 المجموعات:\n\n✅ = عدم التوجيه مفعل (يرسل نسخة مع لاحقة التليجرام)\n❌ = عدم التوجيه معطل (يعيد توجيه من القناة)", reply_markup=InlineKeyboardMarkup(kb))
    
    elif c == "menu_rnd":
        st = "🟢 مفعل" if data["random_enabled"] else "🔴 معطل"
        kb = []
        for i, m in enumerate(data["random_messages"]):
            kb.append([InlineKeyboardButton(f"📝 {m[:15]}...", callback_data=f"edit_rnd_{i}"), InlineKeyboardButton("🗑️", callback_data=f"rmrnd_{i}")])
        if len(data["random_messages"]) > 0:
            kb.append([InlineKeyboardButton("📋 عرض الكل", callback_data="view_all_rnd")])
        kb.append([InlineKeyboardButton(st, callback_data="tog_rnd"), InlineKeyboardButton(f"⏱ {data['random_interval']} د", callback_data="set_rnd")])
        kb.append([InlineKeyboardButton("➕ إضافة نص", callback_data="add_rnd"), InlineKeyboardButton("🔙 رجوع", callback_data="main")])
        await q.edit_message_text("🎲 إدارة العشوائي:", reply_markup=InlineKeyboardMarkup(kb))
    
    elif c.startswith("edit_rnd_"):
        index = int(c[9:])
        u["st"] = f"edit_rnd_{index}"
        await q.edit_message_text(f"📝 تعديل الرسالة العشوائية:\n\n{data['random_messages'][index]}\n\nأرسل النص الجديد:")
    
    elif c == "tog_rnd": 
        data["random_enabled"] = not data["random_enabled"]
        save_data(data)
        st = "🟢 مفعل" if data["random_enabled"] else "🔴 معطل"
        kb = []
        for i, m in enumerate(data["random_messages"]):
            kb.append([InlineKeyboardButton(f"📝 {m[:15]}...", callback_data=f"edit_rnd_{i}"), InlineKeyboardButton("🗑️", callback_data=f"rmrnd_{i}")])
        if len(data["random_messages"]) > 0:
            kb.append([InlineKeyboardButton("📋 عرض الكل", callback_data="view_all_rnd")])
        kb.append([InlineKeyboardButton(st, callback_data="tog_rnd"), InlineKeyboardButton(f"⏱ {data['random_interval']} د", callback_data="set_rnd")])
        kb.append([InlineKeyboardButton("➕ إضافة نص", callback_data="add_rnd"), InlineKeyboardButton("🔙 رجوع", callback_data="main")])
        await q.edit_message_text(f"✅ تم {'تفعيل' if data['random_enabled'] else 'تعطيل'} العشوائي\n🎲 إدارة العشوائي:", reply_markup=InlineKeyboardMarkup(kb))
    
    elif c.startswith("rmrnd_"):
        removed_msg = data["random_messages"].pop(int(c[6:]))
        save_data(data)
        st = "🟢 مفعل" if data["random_enabled"] else "🔴 معطل"
        kb = []
        for i, m in enumerate(data["random_messages"]):
            kb.append([InlineKeyboardButton(f"📝 {m[:15]}...", callback_data=f"edit_rnd_{i}"), InlineKeyboardButton("🗑️", callback_data=f"rmrnd_{i}")])
        if len(data["random_messages"]) > 0:
            kb.append([InlineKeyboardButton("📋 عرض الكل", callback_data="view_all_rnd")])
        kb.append([InlineKeyboardButton(st, callback_data="tog_rnd"), InlineKeyboardButton(f"⏱ {data['random_interval']} د", callback_data="set_rnd")])
        kb.append([InlineKeyboardButton("➕ إضافة نص", callback_data="add_rnd"), InlineKeyboardButton("🔙 رجوع", callback_data="main")])
        await q.edit_message_text(f"✅ تم حذف الرسالة العشوائية: {removed_msg[:50]}...\n🎲 إدارة العشوائي:", reply_markup=InlineKeyboardMarkup(kb))
    
    elif c == "view_all_rnd":
        messages_text = ""
        for i, msg in enumerate(data["random_messages"]):
            messages_text += f"{i+1}. {msg[:50]}...\n"
        kb = [[InlineKeyboardButton("🔙 رجوع", callback_data="menu_rnd")]]
        await q.edit_message_text(f"📋 جميع الرسائل العشوائية ({len(data['random_messages'])}):\n\n{messages_text}", reply_markup=InlineKeyboardMarkup(kb))
    
    elif c == "menu_rep":
        st = "🟢 مفعل" if data["repeat_last_enabled"] else "🔴 معطل"
        kb = [
            [InlineKeyboardButton(st, callback_data="tog_rep")],
            [InlineKeyboardButton(f"⏱ {data['repeat_interval']} د", callback_data="set_rep")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="main")]
        ]
        await q.edit_message_text("🔄 التكرار التلقائي:", reply_markup=InlineKeyboardMarkup(kb))
    
    elif c == "tog_rep": 
        data["repeat_last_enabled"] = not data["repeat_last_enabled"]
        save_data(data)
        st = "🟢 مفعل" if data["repeat_last_enabled"] else "🔴 معطل"
        kb = [
            [InlineKeyboardButton(st, callback_data="tog_rep")],
            [InlineKeyboardButton(f"⏱ {data['repeat_interval']} د", callback_data="set_rep")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="main")]
        ]
        await q.edit_message_text(f"✅ تم {'تفعيل' if data['repeat_last_enabled'] else 'تعطيل'} التكرار\n🔄 التكرار التلقائي:", reply_markup=InlineKeyboardMarkup(kb))
    
    elif c == "ls":
        kb = []
        for i, s in enumerate(data["scheduled_messages"]):
            delete_status = "🗑️" if s.get("delete_after", 0) > 0 else "⏳"
            status_icon = "✅" if s.get("sent_at") else "⏰"
            kb.append([
                InlineKeyboardButton(f"{status_icon}{delete_status} {s['time']} | {s['text'][:15]}...", callback_data=f"edit_sch_{i}"),
                InlineKeyboardButton("🗑️", callback_data=f"rms_{i}")
            ])
        if len(data["scheduled_messages"]) > 0:
            kb.append([InlineKeyboardButton("📋 عرض الكل", callback_data="view_all_sch")])
        kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="main")])
        
        total = len(data["scheduled_messages"])
        sent = len([s for s in data["scheduled_messages"] if s.get("sent_at")])
        pending = total - sent
        with_delete = len([s for s in data["scheduled_messages"] if s.get("delete_after", 0) > 0])
        
        stats_text = f"\n📊 إحصائيات الجدولة:\n⏰ المعلقة: {pending}\n✅ المرسلة: {sent}\n🗑️ ذات حذف تلقائي: {with_delete}"
        
        await q.edit_message_text(f"📅 الرسائل المجدولة:{stats_text}", reply_markup=InlineKeyboardMarkup(kb))
    
    elif c.startswith("edit_sch_"):
        index = int(c[9:])
        scheduled_msg = data["scheduled_messages"][index]
        u["st"] = f"edit_sch_{index}"
        u["edit_sch_index"] = index
        u["edit_sch_data"] = scheduled_msg
        
        delete_info = format_delete_after_time(scheduled_msg.get("delete_after", 0))
        status_info = "✅ تم الإرسال" if scheduled_msg.get("sent_at") else "⏰ في انتظار الإرسال"
        if scheduled_msg.get("sent_at") and scheduled_msg.get("delete_after", 0) > 0:
            delete_time = scheduled_msg.get("sent_at")
            if delete_time:
                try:
                    sent_time = datetime.strptime(delete_time, "%Y-%m-%d %H:%M:%S")
                    delete_at = sent_time + timedelta(minutes=scheduled_msg["delete_after"])
                    delete_info += f" (سيتم الحذف في {delete_at.strftime('%H:%M')})"
                except:
                    pass
        
        message_info = f"📝 تعديل الرسالة المجدولة:\n\n"
        message_info += f"⏰ الوقت: {scheduled_msg['time']}\n"
        message_info += f"📝 النص: {scheduled_msg['text'][:100]}...\n"
        message_info += f"📊 الحالة: {status_info}\n"
        message_info += f"🗑️ الحذف التلقائي: {delete_info}\n\n"
        message_info += f"اختر ما تريد تعديله:"
        
        await q.edit_message_text(message_info, 
                                 reply_markup=InlineKeyboardMarkup([
                                     [InlineKeyboardButton("⏰ الوقت", callback_data=f"edit_sch_time_{index}")],
                                     [InlineKeyboardButton("📝 النص", callback_data=f"edit_sch_text_{index}")],
                                     [InlineKeyboardButton(f"🗑️ وقت الحذف", callback_data=f"edit_sch_delete_{index}")],
                                     [InlineKeyboardButton("🔙 رجوع", callback_data="ls")]
                                 ]))
    
    elif c.startswith("edit_sch_time_"):
        index = int(c[14:])
        u["st"] = f"edit_sch_time_{index}"
        await q.edit_message_text(f"⏰ تعديل وقت الرسالة المجدولة:\n\nالوقت الحالي: {data['scheduled_messages'][index]['time']}\n\nأرسل الوقت الجديد (HH:MM):")
    
    elif c.startswith("edit_sch_text_"):
        index = int(c[14:])
        u["st"] = f"edit_sch_text_{index}"
        await q.edit_message_text(f"📝 تعديل نص الرسالة المجدولة:\n\nالنص الحالي: {data['scheduled_messages'][index]['text'][:200]}...\n\nأرسل النص الجديد:")
    
    elif c.startswith("edit_sch_delete_"):
        index = int(c[16:])
        u["st"] = f"edit_sch_delete_{index}"
        current_delete = data["scheduled_messages"][index].get("delete_after", 0)
        delete_text = format_delete_after_time(current_delete)
        await q.edit_message_text(f"🗑️ تعديل وقت الحذف التلقائي:\n\nالحذف التلقائي الحالي: {delete_text}\n\nاختر وقت الحذف التلقائي (بالدقائق):",
                                 reply_markup=InlineKeyboardMarkup([
                                     [InlineKeyboardButton("❌ لا تحذف", callback_data=f"set_delete_{index}_0")],
                                     [InlineKeyboardButton("5 دقائق", callback_data=f"set_delete_{index}_5"),
                                      InlineKeyboardButton("10 دقائق", callback_data=f"set_delete_{index}_10")],
                                     [InlineKeyboardButton("30 دقيقة", callback_data=f"set_delete_{index}_30"),
                                      InlineKeyboardButton("1 ساعة", callback_data=f"set_delete_{index}_60")],
                                     [InlineKeyboardButton("3 ساعات", callback_data=f"set_delete_{index}_180"),
                                      InlineKeyboardButton("6 ساعات", callback_data=f"set_delete_{index}_360")],
                                     [InlineKeyboardButton("12 ساعة", callback_data=f"set_delete_{index}_720"),
                                      InlineKeyboardButton("1 يوم", callback_data=f"set_delete_{index}_1440")],
                                     [InlineKeyboardButton("2 يوم", callback_data=f"set_delete_{index}_2880"),
                                      InlineKeyboardButton("3 أيام", callback_data=f"set_delete_{index}_4320")],
                                     [InlineKeyboardButton("🔙 رجوع", callback_data=f"edit_sch_{index}")]
                                 ]))
    
    elif c.startswith("set_delete_"):
        parts = c.split("_")
        if len(parts) >= 4:
            index = int(parts[2])
            delete_after = int(parts[3])
            data["scheduled_messages"][index]["delete_after"] = delete_after
            
            if data["scheduled_messages"][index].get("sent_at") and delete_after > 0:
                try:
                    sent_time = datetime.strptime(data["scheduled_messages"][index]["sent_at"], "%Y-%m-%d %H:%M:%S")
                    delete_at = sent_time + timedelta(minutes=delete_after)
                    data["scheduled_messages"][index]["delete_at"] = delete_at.strftime("%Y-%m-%d %H:%M:%S")
                except Exception as e:
                    logging.error(f"Error calculating delete time: {e}")
                    data["scheduled_messages"][index]["delete_at"] = None
            
            save_data(data)
            
            delete_text = format_delete_after_time(delete_after)
            await q.edit_message_text(f"✅ تم تعيين الحذف التلقائي إلى: {delete_text}", 
                                     reply_markup=InlineKeyboardMarkup([
                                         [InlineKeyboardButton("🔙 رجوع", callback_data=f"edit_sch_{index}")]
                                     ]))
    
    elif c.startswith("rms_"):
        removed_msg = data["scheduled_messages"].pop(int(c[4:]))
        save_data(data)
        kb = []
        for i, s in enumerate(data["scheduled_messages"]):
            delete_status = "🗑️" if s.get("delete_after", 0) > 0 else "⏳"
            status_icon = "✅" if s.get("sent_at") else "⏰"
            kb.append([
                InlineKeyboardButton(f"{status_icon}{delete_status} {s['time']} | {s['text'][:15]}...", callback_data=f"edit_sch_{i}"),
                InlineKeyboardButton("🗑️", callback_data=f"rms_{i}")
            ])
        if len(data["scheduled_messages"]) > 0:
            kb.append([InlineKeyboardButton("📋 عرض الكل", callback_data="view_all_sch")])
        kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="main")])
        await q.edit_message_text(f"✅ تم حذف الرسالة المجدولة: {removed_msg['time']} - {removed_msg['text'][:50]}...\n📅 الرسائل المجدولة:", reply_markup=InlineKeyboardMarkup(kb))
    
    elif c == "view_all_sch":
        messages_text = ""
        for i, sched in enumerate(data["scheduled_messages"]):
            delete_info = format_delete_after_time(sched.get("delete_after", 0))
            status = "✅ مرسلة" if sched.get("sent_at") else "⏰ معلقة"
            messages_text += f"{i+1}. ⏰ {sched['time']}: {sched['text'][:40]}...\n   📊 {status} | 🗑️ {delete_info}\n"
        
        total = len(data["scheduled_messages"])
        sent = len([s for s in data["scheduled_messages"] if s.get("sent_at")])
        pending = total - sent
        
        kb = [[InlineKeyboardButton("🔙 رجوع", callback_data="ls")]]
        await q.edit_message_text(f"📋 جميع الرسائل المجدولة ({total}):\n⏰ المعلقة: {pending} | ✅ المرسلة: {sent}\n\n{messages_text}", reply_markup=InlineKeyboardMarkup(kb))
    
    elif c == "st":
        test_mode_status = "🟢 مفعل" if data.get("test_mode", False) else "🔴 معطل"
        emoji_type = data.get("reaction_emoji_type", "guaranteed")
        emoji_text = "مضمون" if emoji_type == "guaranteed" else "إسلامي" if emoji_type == "islamic" else "بسيط"
        current_channel = TEST_CHANNEL_ID if data.get("test_mode", False) else CHANNEL_ID
        
        total_scheduled = len(data["scheduled_messages"])
        sent_scheduled = len([s for s in data["scheduled_messages"] if s.get("sent_at")])
        pending_scheduled = total_scheduled - sent_scheduled
        with_delete_scheduled = len([s for s in data["scheduled_messages"] if s.get("delete_after", 0) > 0])
        
        txt = f"📊 إحصائيات:\n👥 مجموعات: {len(data['groups'])}\n🎲 عشوائي: {len(data['random_messages'])}\n📅 مجدولة: {total_scheduled} (⏰ {pending_scheduled} | ✅ {sent_scheduled} | 🗑️ {with_delete_scheduled})\n⚡ بوتات تفاعل: {len(data['reaction_bots'])}\n🎯 الوضع: {test_mode_status}\n😊 إيموجي: {emoji_text}\n📺 القناة: {current_channel}"
        await q.edit_message_text(txt, reply_markup=get_stats_kb())
    
    elif c == "last_channel":
        if data.get("last_channel_msg_data"):
            msg_data = data["last_channel_msg_data"]
            txt = "📺 آخر إرسال للقناة:\n\n"
            txt += f"⏰ الوقت: {data.get('last_operation_time', 'غير معروف')}\n"
            txt += f"📝 النوع: {msg_data.get('mode', 'نص')}\n"
            txt += f"📄 المحتوى: {msg_data.get('text', '')[:200]}...\n\n"
            txt += f"🔗 معرف الرسالة: {msg_data.get('message_id', 'غير معروف')}"
        else:
            txt = "📭 لا توجد عمليات إرسال سابقة للقناة."
        await q.edit_message_text(txt, reply_markup=get_stats_kb())
    
    elif c == "last_forward":
        forward_logs = [log for log in data["operation_logs"] if log["type"] == "forward_message"]
        if forward_logs:
            last_log = forward_logs[-1]
            txt = "🔄 آخر عملية إعادة توجيه:\n\n"
            txt += f"⏰ الوقت: {last_log['timestamp']}\n"
            txt += f"👥 المجموعة: {last_log['details'].get('group_name', 'غير معروف')}\n"
            txt += f"✅ الحالة: {'نجاح' if last_log['success'] else 'فشل'}\n"
            if last_log.get('error'):
                txt += f"⚠️ الخطأ: {last_log['error'][:100]}"
        else:
            txt = "📭 لا توجد عمليات إعادة توجيه سابقة."
        await q.edit_message_text(txt, reply_markup=get_stats_kb())
    
    elif c == "last_random":
        random_logs = [log for log in data["operation_logs"] if log["type"] == "send_message" and 
                      log["details"].get("operation_type") == "random"]
        if random_logs:
            last_log = random_logs[-1]
            txt = "🎲 آخر رسالة عشوائية:\n\n"
            txt += f"⏰ الوقت: {last_log['timestamp']}\n"
            txt += f"👥 المجموعة: {last_log['details'].get('group_name', 'جميع المجموعات')}\n"
            txt += f"📝 المحتوى: {last_log['details'].get('text_preview', 'غير معروف')}\n"
            txt += f"✅ الحالة: {'نجاح' if last_log['success'] else 'فشل'}"
        else:
            txt = "📭 لا توجد رسائل عشوائية سابقة."
        await q.edit_message_text(txt, reply_markup=get_stats_kb())
    
    elif c == "last_reactions":
        reaction_logs = [log for log in data["operation_logs"] if "reaction" in log["type"]]
        if reaction_logs:
            txt = "🤖 آخر عمليات التفاعل:\n\n"
            for i, log in enumerate(reaction_logs[-10:]):
                status = "✅" if log["success"] else "❌"
                txt += f"{status} {log['timestamp'][11:16]} - {log['type']}\n"
                if log.get('details'):
                    if 'successful' in log['details']:
                        txt += f"   ✅ نجاح: {log['details']['successful']}/{log['details']['total_bots']}\n"
                    if 'failed' in log['details']:
                        txt += f"   ❌ فشل: {log['details']['failed']}\n"
                if log.get('error'):
                    txt += f"   ⚠️ {log['error'][:50]}...\n"
        else:
            txt = "📭 لا توجد عمليات تفاعل سابقة."
        await q.edit_message_text(txt, reply_markup=get_stats_kb())
    
    elif c == "operation_logs":
        if data["operation_logs"]:
            txt = f"📋 سجل العمليات (آخر {len(data['operation_logs'])} عملية):\n\n"
            for i, log in enumerate(data["operation_logs"][-10:]):
                status = "✅" if log["success"] else "❌"
                txt += f"{i+1}. {status} {log['timestamp'][11:16]} - {log['type']}\n"
        else:
            txt = "📭 سجل العمليات فارغ."
        await q.edit_message_text(txt, reply_markup=get_stats_kb())
    
    elif c == "menu_react":
        kb = []
        for i, b in enumerate(data["reaction_bots"]):
            kb.append([InlineKeyboardButton(f"🗑️ {b['name']}", callback_data=f"rmr_{i}")])
        kb.append([InlineKeyboardButton("➕ إضافة بوت", callback_data="add_r"), 
                  InlineKeyboardButton("🔍 اختبار", callback_data="test_bots"), 
                  InlineKeyboardButton("🔙 رجوع", callback_data="settings")])
        
        emoji_type = data.get("reaction_emoji_type", "guaranteed")
        emoji_text = "مضمون" if emoji_type == "guaranteed" else "إسلامي" if emoji_type == "islamic" else "بسيط"
        
        txt = f"⚡ بوتات التفاعل:\n\nالقناة: {get_target_channel()}\nعدد البوتات: {len(data['reaction_bots'])}\nنوع الإيموجي: {emoji_text}\n\nاستخدم زر '🔍 اختبار' لفحص البوتات"
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    
    elif c.startswith("rmr_"):
        removed_bot = data["reaction_bots"].pop(int(c[4:]))
        save_data(data)
        kb = []
        for i, b in enumerate(data["reaction_bots"]):
            kb.append([InlineKeyboardButton(f"🗑️ {b['name']}", callback_data=f"rmr_{i}")])
        kb.append([InlineKeyboardButton("➕ إضافة بوت", callback_data="add_r"), 
                  InlineKeyboardButton("🔍 اختبار", callback_data="test_bots"), 
                  InlineKeyboardButton("🔙 رجوع", callback_data="settings")])
        await q.edit_message_text(f"✅ تم حذف بوت التفاعل: {removed_bot['name']}\n⚡ بوتات التفاعل:", reply_markup=InlineKeyboardMarkup(kb))
    
    elif c == "test_bots":
        if not data.get("reaction_bots"):
            await q.edit_message_text("⚠️ لا توجد بوتات تفاعل مضافة", reply_markup=get_stats_kb())
            return
        
        await q.edit_message_text("🔍 جاري فحص البوتات...")
        
        test_results = []
        current_channel = get_target_channel()
        
        for b in data["reaction_bots"]:
            result = await test_reaction_bot(b['token'], b['name'], current_channel)
            if result["success"]:
                status = "✅" if result["is_admin"] else "⚠️"
                admin_status = "مشرف" if result["is_admin"] else "ليس مشرفاً"
                test_results.append(f"{status} {b['name']}: {admin_status} في {result.get('chat_title', current_channel)}")
            else:
                test_results.append(f"❌ {b['name']}: {result.get('error', 'خطأ غير معروف')}")
        
        report = "📊 نتائج فحص البوتات:\n\n"
        report += f"📺 القناة: {current_channel}\n"
        report += f"🔢 عدد البوتات: {len(data['reaction_bots'])}\n\n"
        report += "\n".join(test_results)
        report += "\n\n📝 ملاحظات:\n✅ = البوت يعمل وهو مشرف\n⚠️ = البوت يعمل ولكنه ليس مشرفاً\n❌ = البوت لا يعمل أو لديه مشكلة"
        
        await q.edit_message_text(report[:4000], reply_markup=get_stats_kb())
    
    elif c == "toggle_test_mode":
        data["test_mode"] = not data.get("test_mode", False)
        save_data(data)
        test_mode_status = "🟢 مفعل" if data["test_mode"] else "🔴 معطل"
        current_channel = TEST_CHANNEL_ID if data["test_mode"] else CHANNEL_ID
        await q.edit_message_text(f"✅ تم {'تفعيل' if data['test_mode'] else 'تعطيل'} الوضع التجريبي\n📺 القناة المستخدمة الآن: {current_channel}", reply_markup=get_settings_kb())
    
    elif c == "toggle_emoji_type":
        current_type = data.get("reaction_emoji_type", "guaranteed")
        if current_type == "guaranteed":
            new_type = "islamic"
            message = "إسلامي 🕌"
        elif current_type == "islamic":
            new_type = "simple"
            message = "بسيط ❤️"
        else:
            new_type = "guaranteed"
            message = "مضمون 👍"
        
        data["reaction_emoji_type"] = new_type
        save_data(data)
        await q.edit_message_text(f"✅ تم تغيير نوع الإيموجي إلى: {message}", reply_markup=get_settings_kb())
    
    elif c in ["add_g", "set_rep", "add_rnd", "set_rnd", "add_r"]: 
        u["st"] = c
        await q.edit_message_text("📝 أرسل المطلوب الآن:")
    
    elif c.startswith("p_"):
        p = u.get("tmp")
        if c == "p_y":
            u["add_suffix"] = True
            suffix_text = "مع اللاحقة (واتساب للقناة)"
        else:
            u["add_suffix"] = False
            suffix_text = "بدون لاحقة"
        u["ready"] = {"t": p["t"], "m": p["m"], "f": p["f"]}
        await q.edit_message_text(f"📍 وجهة النشر ({suffix_text}):", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📺 القناة", callback_data="s_c"), InlineKeyboardButton("👥 المجموعات", callback_data="s_g")],
            [InlineKeyboardButton("🔄 الكل", callback_data="s_a")],
            [InlineKeyboardButton("📅 جدولة", callback_data="s_s")]
        ]))
    
    elif c.startswith("s_"):
        act = c[2:]
        p = u.get("ready")
        add_suffix = u.get("add_suffix", False)
        
        if act == "s": 
            u["st"] = "ssch"
            await q.edit_message_text("⏰ وقت الجدولة (HH:MM):")
            return
        
        channel_id = get_target_channel()
        
        if act == "c":
            m = await send_msg(context, channel_id, p["t"], p["m"], p["f"], True,
                             add_suffix=add_suffix,
                             operation_log={"operation_type": "channel_only"})
            if m: 
                data["last_channel_msg_data"] = {
                    "message_id": m.message_id,
                    "text": p["t"],
                    "mode": p["m"],
                    "file_id": p["f"]
                }
                data["last_channel_msg_id"] = m.message_id
                data["last_operation_time"] = datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d %H:%M:%S")
                save_data(data)
                
        elif act == "g":
            for g in data["groups"]:
                try: 
                    if g.get("no_forward", False):
                        m = await send_msg(context, g["id"], p["t"], p["m"], p["f"], False,
                                         add_suffix=True,
                                         operation_log={
                                             "group_name": g["title"],
                                             "operation_type": "groups_only",
                                             "no_forward": True
                                         })
                    else:
                        m = await send_msg(context, g["id"], p["t"], p["m"], p["f"], False,
                                         add_suffix=False,
                                         operation_log={
                                             "group_name": g["title"],
                                             "operation_type": "groups_only",
                                             "no_forward": False
                                         })
                except Exception as e:
                    add_operation_log("send_groups_only", {"group": g["title"], "error": str(e)}, False)
                    logging.error(f"Error sending to group {g['title']}: {e}")
                    continue
                    
        elif act == "a":
            m = await send_msg(context, channel_id, p["t"], p["m"], p["f"], True,
                             add_suffix=add_suffix,
                             operation_log={"operation_type": "broadcast_to_channel"})
            if m: 
                msg_data = {
                    "message_id": m.message_id,
                    "text": p["t"],
                    "mode": p["m"],
                    "file_id": p["f"]
                }
                data["last_channel_msg_data"] = msg_data
                data["last_channel_msg_id"] = m.message_id
                data["last_operation_time"] = datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d %H:%M:%S")
                save_data(data)
                await send_to_groups(context, msg_data, "broadcast")
        
        await q.edit_message_text("✅ تم التنفيذ! سيصلك تقرير بالنتائج.", reply_markup=get_main_kb())

async def msg_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.message.from_user.id != ADMIN_ID:
        return
    
    u, text = context.user_data, update.message.text or ""
    st = context.user_data.get("st", "")
    await asyncio.sleep(0.1)
    
    if st == "add_g":
        clean_id = text.strip().split('/')[-1].replace('@', '')
        if not clean_id.startswith('-'):
            clean_id = f"@{clean_id}"
        try:
            chat = await context.bot.get_chat(clean_id)
            if any(g['id'] == chat.id for g in data["groups"]):
                await update.message.reply_text("⚠️ المجموعة مضافة بالفعل")
            else:
                data["groups"].append({"id": chat.id, "title": chat.title, "no_forward": False})
                save_data(data)
                add_operation_log("add_group", {"group": chat.title, "id": chat.id}, True)
                await update.message.reply_text(f"✅ تمت إضافة: {chat.title}", reply_markup=get_main_kb())
        except Exception as e:
            add_operation_log("add_group", {"group_id": clean_id, "error": str(e)}, False)
            await update.message.reply_text("❌ لم أستطع العثور على المجموعة. تأكد من إضافتي فيها كمسؤول أولاً!")
    
    elif st == "set_rep": 
        try:
            data["repeat_interval"] = int(text)
            save_data(data)
            add_operation_log("set_repeat", {"interval": int(text)}, True)
            await update.message.reply_text("✅ تم الحفظ", reply_markup=get_main_kb())
        except ValueError:
            await update.message.reply_text("❌ الرقم غير صالح")
    
    elif st == "set_rnd": 
        try:
            data["random_interval"] = int(text)
            save_data(data)
            add_operation_log("set_random", {"interval": int(text)}, True)
            await update.message.reply_text("✅ تم الحفظ", reply_markup=get_main_kb())
        except ValueError:
            await update.message.reply_text("❌ الرقم غير صالح")
    
    elif st == "add_rnd": 
        data["random_messages"].append(text)
        save_data(data)
        add_operation_log("add_random", {"message_preview": text[:50] + "..." if len(text) > 50 else text}, True)
        await update.message.reply_text("✅ أضيف للعشوائي", reply_markup=get_main_kb())
    
    elif st.startswith("edit_rnd_"):
        index = int(st[9:])
        if index < len(data["random_messages"]):
            old_msg = data["random_messages"][index]
            data["random_messages"][index] = text
            save_data(data)
            add_operation_log("edit_random", {"index": index, "old": old_msg[:50], "new": text[:50]}, True)
            await update.message.reply_text("✅ تم تحديث الرسالة العشوائية", reply_markup=get_main_kb())
    
    elif st.startswith("edit_sch_time_"):
        index = int(st[14:])
        if index < len(data["scheduled_messages"]):
            old_time = data["scheduled_messages"][index]["time"]
            data["scheduled_messages"][index]["time"] = text
            save_data(data)
            add_operation_log("edit_schedule_time", {"index": index, "old": old_time, "new": text}, True)
            await update.message.reply_text(f"✅ تم تحديث الوقت إلى {text}", reply_markup=get_main_kb())
    
    elif st.startswith("edit_sch_text_"):
        index = int(st[14:])
        if index < len(data["scheduled_messages"]):
            old_text = data["scheduled_messages"][index]["text"]
            data["scheduled_messages"][index]["text"] = text
            save_data(data)
            add_operation_log("edit_schedule_text", {"index": index, "old": old_text[:50], "new": text[:50]}, True)
            await update.message.reply_text("✅ تم تحديث النص", reply_markup=get_main_kb())
    
    elif st.startswith("edit_sch_delete_"):
        index = int(st[16:])
        try:
            delete_after = int(text)
            if delete_after < 0:
                await update.message.reply_text("❌ الرقم غير صالح. يجب أن يكون عدد الدقائق أكبر من أو يساوي 0")
                return
            
            data["scheduled_messages"][index]["delete_after"] = delete_after
            
            if data["scheduled_messages"][index].get("sent_at") and delete_after > 0:
                try:
                    sent_time = datetime.strptime(data["scheduled_messages"][index]["sent_at"], "%Y-%m-%d %H:%M:%S")
                    delete_at = sent_time + timedelta(minutes=delete_after)
                    data["scheduled_messages"][index]["delete_at"] = delete_at.strftime("%Y-%m-%d %H:%M:%S")
                except Exception as e:
                    logging.error(f"Error calculating delete time: {e}")
                    data["scheduled_messages"][index]["delete_at"] = None
            
            save_data(data)
            delete_text = format_delete_after_time(delete_after)
            await update.message.reply_text(f"✅ تم تعيين الحذف التلقائي إلى: {delete_text}", reply_markup=get_main_kb())
        except ValueError:
            await update.message.reply_text("❌ الرقم غير صالح. أرسل عدد الدقائق (0 يعني لا حذف)")
    
    elif st == "ssch":
        p = u.get("ready")
        u["tmp_schedule"] = {"time": text, "text": p["t"], "mode": p["m"], "file_id": p["f"]}
        u["st"] = "ssc_delete"
        await update.message.reply_text("⏰ وقت الجدولة: " + text + "\n\n🗑️ كم دقيقة بعد الإرسال تريد حذف الرسالة؟\nأرسل 0 إذا كنت لا تريد الحذف التلقائي:")
        return
    
    elif st == "ssc_delete":
        try:
            delete_after = int(text)
            if delete_after < 0:
                await update.message.reply_text("❌ الرقم غير صالح. أرسل عدد الدقائق (0 يعني لا حذف)")
                return
            
            schedule_data = u.get("tmp_schedule", {})
            new_schedule = {
                "time": schedule_data["time"],
                "text": schedule_data["text"],
                "mode": schedule_data["mode"],
                "file_id": schedule_data["file_id"],
                "delete_after": delete_after,
                "sent_at": None,
                "sent_message_id": None,
                "delete_at": None
            }
            
            data["scheduled_messages"].append(new_schedule)
            save_data(data)
            
            delete_text = format_delete_after_time(delete_after)
            add_operation_log("add_schedule", {
                "time": schedule_data["time"],
                "message_preview": schedule_data["text"][:50] + "..." if len(schedule_data["text"]) > 50 else schedule_data["text"],
                "delete_after": delete_text
            }, True)
            
            await update.message.reply_text(f"📅 تمت الجدولة لوقت {schedule_data['time']}\n🗑️ الحذف التلقائي: {delete_text}", reply_markup=get_main_kb())
        except ValueError:
            await update.message.reply_text("❌ الرقم غير صالح. أرسل عدد الدقائق (0 يعني لا حذف)")
            return
    
    elif st == "add_r":
        try:
            async with Bot(text.strip()) as tb:
                me = await tb.get_me()
                data["reaction_bots"].append({"token": text.strip(), "name": me.first_name})
                save_data(data)
                current_channel = TEST_CHANNEL_ID if data.get("test_mode", False) else CHANNEL_ID
                add_operation_log("add_reaction_bot", {"bot": me.first_name}, True)
                
                test_result = await test_reaction_bot(text.strip(), me.first_name, current_channel)
                if test_result["success"]:
                    if test_result["is_admin"]:
                        message = f"✅ تم إضافة بوت التفاعل: {me.first_name}\n\n✅ البوت يعمل وهو مشرف في القناة {current_channel}"
                    else:
                        message = f"✅ تم إضافة بوت التفاعل: {me.first_name}\n\n⚠️ البوت يعمل ولكنه ليس مشرفاً في القناة {current_channel}\nيرجى إضافته كمسؤول مع صلاحية 'تغيير تفاعلات الرسائل'"
                else:
                    message = f"✅ تم إضافة بوت التفاعل: {me.first_name}\n\n❌ البوت لديه مشكلة: {test_result.get('error', 'خطأ غير معروف')}\nيرجى التأكد من التوكن وإضافة البوت للقناة"
                
                await update.message.reply_text(message, reply_markup=get_main_kb())
        except Exception as e:
            add_operation_log("add_reaction_bot", {"token": text.strip(), "error": str(e)}, False)
            await update.message.reply_text(f"❌ توكن خطأ أو البوت غير مفعل\n\nالخطأ: {str(e)[:200]}", reply_markup=get_main_kb())
    
    elif not st:
        m, f, t = "text", None, text
        if update.message.photo: 
            m, f, t = "photo", update.message.photo[-1].file_id, update.message.caption or ""
        elif update.message.video: 
            m, f, t = "video", update.message.video.file_id, update.message.caption or ""
        elif update.message.document:
            m, f, t = "document", update.message.document.file_id, update.message.caption or ""
            
        u["tmp"] = {"t": t, "m": m, "f": f}
        await update.message.reply_text("📦 خيارات اللاحقة:\n\n✅ بلاحقة: تضاف لاحقة الواتساب للقناة\n❌ بدون: لا تضاف أي لاحقة", 
                                      reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ بلاحقة", callback_data="p_y"), InlineKeyboardButton("❌ بدون", callback_data="p_n")]
        ]))
        return
    
    u.clear()

async def check_and_delete_messages(context):
    now = datetime.now(timezone(timedelta(hours=3)))
    messages_to_remove = []
    
    for i, msg in enumerate(data.get("scheduled_messages", [])):
        if msg.get("sent_at") and msg.get("delete_at") and msg.get("sent_message_id"):
            try:
                delete_time = datetime.strptime(msg["delete_at"], "%Y-%m-%d %H:%M:%S")
                if delete_time <= now:
                    try:
                        await context.bot.delete_message(
                            chat_id=get_target_channel(),
                            message_id=msg["sent_message_id"]
                        )
                        add_operation_log("auto_delete_scheduled", {
                            "message_id": msg["sent_message_id"],
                            "scheduled_time": msg["time"],
                            "sent_at": msg["sent_at"],
                            "delete_after": msg.get("delete_after", 0)
                        }, True)
                        
                        await context.bot.send_message(
                            ADMIN_ID,
                            f"🗑️ تم حذف الرسالة المجدولة تلقائياً:\n\n⏰ الوقت: {msg['time']}\n📝 النص: {msg['text'][:100]}...\n⏱️ بعد: {format_delete_after_time(msg.get('delete_after', 0))}"
                        )
                        
                    except Exception as e:
                        error_msg = str(e)
                        if "Message to delete not found" in error_msg or "message can't be deleted" in error_msg:
                            add_operation_log("auto_delete_scheduled", {
                                "message_id": msg["sent_message_id"],
                                "scheduled_time": msg["time"],
                                "error": "الرسالة غير موجودة أو لا يمكن حذفها"
                            }, False)
                        else:
                            add_operation_log("auto_delete_scheduled", {
                                "message_id": msg["sent_message_id"],
                                "scheduled_time": msg["time"],
                                "error": error_msg
                            }, False)
                    
                    messages_to_remove.append(i)
                    
            except Exception as e:
                logging.error(f"Error processing auto-delete for message {i}: {e}")
                continue
    
    for index in sorted(messages_to_remove, reverse=True):
        if index < len(data["scheduled_messages"]):
            removed = data["scheduled_messages"].pop(index)
            logging.info(f"Removed scheduled message from list: {removed.get('time')}")
    
    if messages_to_remove:
        save_data(data)

async def job_handler(context):
    now = datetime.now(timezone(timedelta(hours=3)))
    t_str = now.strftime("%H:%M")
    
    for msg in data.get("scheduled_messages", []):
        if not msg.get("sent_at") and msg["time"] == t_str:
            m = await send_msg(context, get_target_channel(), msg["text"], msg["mode"], msg["file_id"], True,
                             add_suffix=True,
                             operation_log={"operation_type": "scheduled"})
            
            if m:
                msg["sent_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
                msg["sent_message_id"] = m.message_id
                
                if msg.get("delete_after", 0) > 0:
                    delete_at = now + timedelta(minutes=msg["delete_after"])
                    msg["delete_at"] = delete_at.strftime("%Y-%m-%d %H:%M:%S")
                
                msg_data = {
                    "message_id": m.message_id,
                    "text": msg["text"],
                    "mode": msg["mode"],
                    "file_id": msg["file_id"]
                }
                data["last_channel_msg_data"] = msg_data
                data["last_channel_msg_id"] = m.message_id
                data["last_operation_time"] = now.strftime("%Y-%m-%d %H:%M:%S")
                
                save_data(data)
                await send_to_groups(context, msg_data, "scheduled")
                
                delete_info = ""
                if msg.get("delete_after", 0) > 0:
                    delete_info = f"\n🗑️ سيتم الحذف تلقائياً بعد: {format_delete_after_time(msg['delete_after'])}"
                
                await context.bot.send_message(
                    ADMIN_ID,
                    f"✅ تم إرسال الرسالة المجدولة:\n\n⏰ الوقت: {msg['time']}\n📝 النص: {msg['text'][:100]}...{delete_info}"
                )
    
    t_min = now.hour * 60 + now.minute
    if data["repeat_last_enabled"] and data.get("last_channel_msg_data") and (t_min % data.get("repeat_interval", 30) == 0):
        await send_to_groups(context, data["last_channel_msg_data"], "repeat")
    
    if data["random_enabled"] and data["random_messages"] and (t_min % data.get("random_interval", 60) == 0):
        msg = random.choice(data["random_messages"])
        for g in data["groups"]: 
            try:
                await send_msg(context, g["id"], msg, "text", None, False, add_suffix=True,
                             operation_log={
                                 "group_name": g["title"],
                                 "operation_type": "random",
                                 "no_forward": g.get("no_forward", False)
                             })
            except Exception as e:
                add_operation_log("random_message", {"group": g["title"], "error": str(e)}, False)
                continue
    
    await check_and_delete_messages(context)

def main():
    app = Application.builder().token(TOKEN).build()
    app.job_queue.run_repeating(job_handler, 60)
    app.add_handler(CommandHandler("start", lambda u,c: u.message.reply_text(f"👑 لوحة التحكم\n\nالقناة: {TELEGRAM_CHANNEL_LINK}", reply_markup=get_main_kb(), disable_web_page_preview=True)))
    app.add_handler(CallbackQueryHandler(cb_handler))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, msg_handler))
    print("🚀 البوت جاهز ويعمل الآن...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__": 
    main()
