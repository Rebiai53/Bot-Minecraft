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
API_KEY = "ptlc_s4rc93hrVy5jMAzA8UsgLZZGFuOHvPTJOmvtF5vZQMS"
SERVER_ID = "7037c1fe"
TARGET_CHANNEL_NAME = "botstarter"  # اسم القناة التي سيضع فيها البوت لوحة التحكم

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

status_message = None

# --- دوال الاتصال بلوحة TickHosting ---
def get_server_resources():
    url = f"{PANEL_URL}/servers/{SERVER_ID}/resources"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.json().get("attributes", {})
    except Exception as e:
        print(f"Error fetching resources: {e}")
    return None

def send_power_signal(signal: str):
    url = f"{PANEL_URL}/servers/{SERVER_ID}/power"
    try:
        response = requests.post(url, json={"signal": signal}, headers=HEADERS, timeout=10)
        return response.status_code == 204
    except Exception:
        return False

# --- بناء رسالة الحالة (Embed) ---
def build_status_embed():
    data = get_server_resources()
    if not data:
        embed = discord.Embed(
            title="🖥️ لوحة تحكم سيرفر ماين كرافت",
            description="⚠️ تعذر جلب حالة السيرفر حالياً من الاستضافة.",
            color=discord.Color.orange()
        )
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
        title="🎮 لوحة تحكم سيرفر ماين كرافت",
        description="تحكم بالسيرفر مباشرة عبر الأزرار بالأسفل أو عبر الأوامر (`!start` / `!restart` / `!stop`).",
        color=color
    )
    embed.add_field(name="📡 حالة السيرفر", value=f"**{status_text}**", inline=False)
    embed.add_field(name="🧠 استهلاك الرام (RAM)", value=f"`{ram_mb} MB`", inline=True)
    embed.add_field(name="⚡ المعالج (CPU)", value=f"`{cpu_pct}%`", inline=True)
    embed.set_footer(text="يتم تحديث الحالة تلقائياً كل 15 ثانية")
    return embed

# --- أزرار التحكم التفاعلية ---
class ServerControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="تشغيل السيرفر", style=discord.ButtonStyle.success, emoji="🟢", custom_id="btn_start")
    async def start_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if send_power_signal("start"):
            await interaction.followup.send("🟢 تم إرسال أمر **تشغيل السيرفر** بنجاح!", ephemeral=True)
        else:
            await interaction.followup.send("❌ فشل التشغيل (قد يكون السيرفر شغالاً بالفعل).", ephemeral=True)
        if status_message:
            await status_message.edit(embed=build_status_embed(), view=self)

    @discord.ui.button(label="تجديد / إعادة تشغيل", style=discord.ButtonStyle.primary, emoji="🔄", custom_id="btn_restart")
    async def restart_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if send_power_signal("restart"):
            await interaction.followup.send("🔄 جاري **إعادة تشغيل** السيرفر...", ephemeral=True)
        else:
            await interaction.followup.send("❌ تعذر إعادة تشغيل السيرفر.", ephemeral=True)
        if status_message:
            await status_message.edit(embed=build_status_embed(), view=self)

    @discord.ui.button(label="إيقاف السيرفر", style=discord.ButtonStyle.danger, emoji="🔴", custom_id="btn_stop")
    async def stop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if send_power_signal("stop"):
            await interaction.followup.send("🔴 تم إرسال أمر **إيقاف السيرفر**.", ephemeral=True)
        else:
            await interaction.followup.send("❌ تعذر إيقاف السيرفر.", ephemeral=True)
        if status_message:
            await status_message.edit(embed=build_status_embed(), view=self)

    @discord.ui.button(label="تحديث", style=discord.ButtonStyle.secondary, emoji="🔃", custom_id="btn_refresh")
    async def refresh_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=build_status_embed(), view=self)

# --- التحديث التلقائي لحالة السيرفر في قناة botstarter ---
@tasks.loop(seconds=15)
async def update_status_loop():
    global status_message
    channel = discord.utils.get(bot.get_all_channels(), name=TARGET_CHANNEL_NAME)
    if not channel:
        return

    embed = build_status_embed()
    view = ServerControlView()

    try:
        if status_message is None:
            # البحث عن آخر رسالة للبوت في القناة لتحديثها بدل إرسال رسالة جديدة
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

# --- الأوامر النصية الإضافية ---
@bot.command(name="status")
async def status_cmd(ctx):
    await ctx.send(embed=build_status_embed(), view=ServerControlView())

@bot.command(name="start")
async def start_server(ctx):
    if send_power_signal("start"):
        await ctx.send("🟢 تم إرسال أمر **تشغيل** السيرفر بنجاح!")
    else:
        await ctx.send("❌ فشل التشغيل.")

@bot.command(name="restart")
async def restart_server(ctx):
    if send_power_signal("restart"):
        await ctx.send("🔄 جاري **إعادة تشغيل** السيرفر...")
    else:
        await ctx.send("❌ تعذر إعادة تشغيل السيرفر.")

@bot.command(name="stop")
async def stop_server(ctx):
    if send_power_signal("stop"):
        await ctx.send("🔴 تم إرسال أمر **إيقاف** السيرفر بنجاح!")
    else:
        await ctx.send("❌ تعذر إيقاف السيرفر.")

@bot.command(name="cmd")
async def send_command(ctx, *, command: str):
    url = f"{PANEL_URL}/servers/{SERVER_ID}/command"
    response = requests.post(url, json={"command": command}, headers=HEADERS)
    if response.status_code == 204:
        await ctx.send(f"🎮 تم إرسال الأمر: `{command}`")
    else:
        await ctx.send("❌ تعذر إرسال الأمر (تأكد أن السيرفر يعمل حالياً).")

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("خطأ: لم يتم العثور على DISCORD_TOKEN في Environment Variables!")
    else:
        keep_alive()
        bot.run(DISCORD_TOKEN)
