import os
from threading import Thread
from flask import Flask
import discord
from discord.ext import commands
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

# --- بيانات الربط الآمنة ---
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
PANEL_URL = "https://tickhosting.com/api/client"
API_KEY = "ptlc_s4rc93hrVy5jMAzA8UsgLZZGFuOHvPTJOmvtF5vZQMS"
SERVER_ID = "7037c1fe"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"البوت متصل وجاهز: {bot.user}")

def send_power_signal(signal: str):
    url = f"{PANEL_URL}/servers/{SERVER_ID}/power"
    response = requests.post(url, json={"signal": signal}, headers=HEADERS)
    return response.status_code == 204

@bot.command(name="start")
async def start_server(ctx):
    if send_power_signal("start"):
        await ctx.send("🟢 تم إرسال أمر **تشغيل** السيرفر بنجاح!")
    else:
        await ctx.send("❌ فشل التشغيل. تأكد من صلاحيات مفتاح الـ API.")

@bot.command(name="stop")
async def stop_server(ctx):
    if send_power_signal("stop"):
        await ctx.send("🔴 تم إرسال أمر **إيقاف** السيرفر بنجاح!")
    else:
        await ctx.send("❌ تعذر إيقاف السيرفر.")

@bot.command(name="restart")
async def restart_server(ctx):
    if send_power_signal("restart"):
        await ctx.send("🔄 جاري **إعادة تشغيل** السيرفر...")
    else:
        await ctx.send("❌ تعذر إعادة تشغيل السيرفر.")

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
