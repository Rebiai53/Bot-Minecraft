import os
from threading import Thread
from flask import Flask
import discord
from discord.ext import commands, tasks
import requests

# --- خادم ويب لإبقاء البوت مستيقظاً على Render ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Minecraft Discord Bot is Running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# --- إعدادات الربط ---
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
PANEL_URL = "https://tickhosting.com/api/client"
API_KEY = os.environ.get("TICKHOSTING_API_KEY", "ptlc_s4rc93hrVy5jMAzA8UsgLZZGFuOHvPTJOmvtF5vZQMS")
SERVER_ID = "7037c1fe"
SERVER_IP = "craftdz.mineserver.uno"
TARGET_CHANNEL_NAME = "botstarter"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

status_message = None

# --- دوال الاتصال بلوحة TickHosting مع كشف سبب الخطأ ---
def get_server_resources():
    url = f"{PANEL_URL}/servers/{SERVER_ID}/resources"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.json().get("attributes", {}), None
        elif r.status_code == 401:
            return None, "مفتاح الـ API غير صالح أو منتهي الصلاحية (401)."
        elif r.status_code == 403:
            return None, "الاستضافة أو Cloudflare حظرت الاتصال من Render (403)."
        else:
            return None, f"خطأ من الاستضافة برمز: {r.status_code}"
    except Exception as e:
        return None, f"فشل الاتصال بالاستضافة: {str(e)}"

def send_power_signal(signal: str):
    url = f"{PANEL_URL}/servers/{SERVER_ID}/power"
    try:
        r = requests.post(url, json={"signal": signal}, headers=HEADERS, timeout=10)
        if r.status_code == 204:
            return True, "تم بنجاح"
        elif r.status_code == 401:
            return False, "مفتاح الـ API غير صالح (401). أنشئ مفتاحاً جديداً."
        elif r.status_code == 403:
            return False, "حماية Cloudflare أو الاستضافة منعت الطلب (403)."
        else:
            return False, f"رفضت الاستضافة الأمر (رمز الخطأ: {r.status_code})."
    except Exception as e:
        return False, f"خطأ في الاتصال: {str(e)}"

# --- بناء رسالة الحالة (Embed) ---
def build_status_embed():
    data, error_msg = get_server_resources()

    if error_msg or not data:
        embed = discord.Embed(
            title="🎮 لوحة تحكم سيرفر ماين كرافت (Bset Server)",
            description=f"⚠️ **تعذر جلب حالة السيرفر:**\n`{error_msg}`",
            color=discord.Color.orange()
        )
        embed.add_field(name="🌐 عنوان السيرفر (IP)", value=f"```{SERVER_IP}```", inline=False)
        embed.set_footer(text="يتم تحديث الحالة تلقائياً كل 30 ثانية")
        return embed

    state = data.get("current_state", "offline")
    resources = data.get("resources", {})
    ram_mb = round(resources.get("memory_bytes", 0) / (1024 * 1024), 1)
    cpu_pct = round(resources.get("cpu_absolute", 0), 1)

    state_map = {
        "running": ("🟢 شغال (Online)", discord.Color.green()),
        "offline": ("🔴 منطفئ (Offline)", discord.Color.red()),
        "starting": ("🟡 جاري التشغيل (Starting...)", discord.Color.gold()),
        "stopping": ("🟠 جاري الإيقاف (Stopping...)", discord.Color.orange()),
    }

    status_text, color = state_map.get(state, (f"⚪ {state}", discord.Color.light_grey()))

    embed = discord.Embed(
        title="🎮 لوحة تحكم سيرفر ماين كرافت (Bset Server)",
        description="تحكم بالسيرفر مباشرة عبر الأزرار بالأسفل أو عبر الأوامر (`!start` / `!restart` / `!stop`).",
        color=color
    )
    embed.add_field(name="🌐 عنوان السيرفر (IP)", value=f"```{SERVER_IP}```", inline=False)
    embed.add_field(name="📡 حالة السيرفر", value=f"**{status_text}**", inline=False)
    embed.add_field(name="🧠 استهلاك الرام (RAM)", value=f"`{ram_mb} MB`", inline=True)
    embed.add_field(name="⚡ المعالج (CPU)", value=f"`{cpu_pct}%`", inline=True)
    embed.set_footer(text="يتم تحديث الحالة تلقائياً كل 30 ثانية")
    return embed

# --- أزرار التحكم التفاعلية ---
class ServerControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="تشغيل السيرفر", style=discord.ButtonStyle.success, emoji="🟢", custom_id="btn_start")
    async def start_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        ok, msg = send_power_signal("start")
        if ok:
            await interaction.followup.send("🟢 تم إرسال أمر **تشغيل السيرفر** بنجاح!", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ فشل التشغيل: `{msg}`", ephemeral=True)
        if status_message:
            await status_message.edit(embed=build_status_embed(), view=self)

    @discord.ui.button(label="تجديد / إعادة تشغيل", style=discord.ButtonStyle.primary, emoji="🔄", custom_id="btn_restart")
    async def restart_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        ok, msg = send_power_signal("restart")
        if ok:
            await interaction.followup.send("🔄 جاري **إعادة تشغيل** السيرفر...", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ تعذر إعادة التشغيل: `{msg}`", ephemeral=True)
        if status_message:
            await status_message.edit(embed=build_status_embed(), view=self)

    @discord.ui.button(label="إيقاف السيرفر", style=discord.ButtonStyle.danger, emoji="🔴", custom_id="btn_stop")
    async def stop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        ok, msg = send_power_signal("stop")
        if ok:
            await interaction.followup.send("🔴 تم إرسال أمر **إيقاف السيرفر**.", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ تعذر الإيقاف: `{msg}`", ephemeral=True)
        if status_message:
            await status_message.edit(embed=build_status_embed(), view=self)

    @discord.ui.button(label="نسخ IP", style=discord.ButtonStyle.secondary, emoji="📋", custom_id="btn_ip")
    async def ip_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"🌐 عنوان السيرفر:\n`{SERVER_IP}`", ephemeral=True)

    @discord.ui.button(label="تحديث", style=discord.ButtonStyle.secondary, emoji="🔃", custom_id="btn_refresh")
    async def refresh_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=build_status_embed(), view=self)

# --- التحديث التلقائي كل 30 ثانية في قناة botstarter ---
@tasks.loop(seconds=30)
async def update_status_loop():
    global status_message
    channel = discord.utils.get(bot.get_all_channels(), name=TARGET_CHANNEL_NAME)
    if not channel:
        return

    embed = build_status_embed()
    view = ServerControlView()

    try:
        if status_message is None:
            async for msg in channel.history(limit=10):
                if msg.author == bot.user:
                    status_message = msg
                    break

        if status_message:
            await status_message.edit(embed=embed, view=view)
        else:
            status_message = await channel.send(embed=embed, view=view)
    except Exception as e:
        status_message = None
        print(f"Error updating status message: {e}")

@bot.event
async def on_ready():
    bot.add_view(ServerControlView())
    print(f"البوت متصل وجاهز: {bot.user}")
    if not update_status_loop.is_running():
        update_status_loop.start()

# --- الأوامر النصية ---
@bot.command(name="ip")
async def ip_cmd(ctx):
    await ctx.send(f"🌐 عنوان السيرفر (IP): `{SERVER_IP}`")

@bot.command(name="status")
async def status_cmd(ctx):
    await ctx.send(embed=build_status_embed(), view=ServerControlView())

@bot.command(name="start")
async def start_server(ctx):
    ok, msg = send_power_signal("start")
    await ctx.send("🟢 تم إرسال أمر **تشغيل** السيرفر بنجاح!" if ok else f"❌ فشل التشغيل: `{msg}`")

@bot.command(name="restart")
async def restart_server(ctx):
    ok, msg = send_power_signal("restart")
    await ctx.send("🔄 جاري **إعادة تشغيل** السيرفر..." if ok else f"❌ تعذر إعادة التشغيل: `{msg}`")

@bot.command(name="stop")
async def stop_server(ctx):
    ok, msg = send_power_signal("stop")
    await ctx.send("🔴 تم إرسال أمر **إيقاف** السيرفر بنجاح!" if ok else f"❌ تعذر الإيقاف: `{msg}`")

@bot.command(name="cmd")
async def send_command(ctx, *, command: str):
    url = f"{PANEL_URL}/servers/{SERVER_ID}/command"
    r = requests.post(url, json={"command": command}, headers=HEADERS)
    if r.status_code == 204:
        await ctx.send(f"🎮 تم إرسال الأمر: `{command}`")
    else:
        await ctx.send(f"❌ تعذر إرسال الأمر (رمز الخطأ: `{r.status_code}`).")

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("خطأ: لم يتم العثور على DISCORD_TOKEN!")
    else:
        keep_alive()
        bot.run(DISCORD_TOKEN)
