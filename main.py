import os
import re
import asyncio
import aiohttp
from flask import Flask
from threading import Thread
from telethon import TelegramClient, events
from telethon.sessions import StringSession # स्ट्रिंग सेशन इम्पोर्ट किया
from playwright.async_api import async_playwright

# --- 1. पिंग के लिए Flask वेब-सर्वर सेटअप ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running!"

def run_web_server():
    app.run(host='0.0.0.0', port=10000)

# --- 2. टेलीग्राम और API कॉन्फ़िगरेशन ---
# ⚠️ ध्यान दें: यहाँ अपनी असली डिटेल्स भरें
API_ID = 34278215         # my.telegram.org से लें (बिना कोट्स के)
API_HASH = '82aafe1590473bdbc558f60c46ed3387' 
BOT_TOKEN = '8817454197:AAGdII5VzjvJfBHG2gQ6n0j6G3v0xNTKnU0' 
FILEMOON_API_KEY = '110|4mK5RhaO8YzMQb2aXgmcDuPqXTUgxdrzysgz6kP3' 

# 🎯 फिक्स: यहाँ अपनी CMD से कॉपी की हुई लंबी स्ट्रिंग को कोट्स (' ') के अंदर पेस्ट करें
TELEGRAM_STRING_SESSION = '1BVtsOMABu0gry-tc2n1t6umsoPgW6zR_cHS1EE4QfRm2L1f4pVNSgkcNyFGh_l30YudtJU0qU80dTFZ
fXrHYnYWIZDnp5XvJFlTTchxFzUZ0xQ-vlgrL3FJNJw8YqBTYrRFnPK1e7ItEttBG8qc-D60-wXcATtL
txYQ4v2HqN9CYgYy6xDp89zqLp83KEoeQIth6Qnv9SMxc_glP6zEFE6Ur2-KfVgoJ9G5UuratDWGhfnc
LstYKeqbrF7Qd4NLsXlCk-a7EYDc6Q-3UZx278jA5aeMGKyjIdQ2uxqe0tG3l6W6Nd5REGZWrNCLjooW
uJ2VkYR5ZP03kMNUGUSlvec5O2tN9B4M='

# 🎯 फिक्स: रोज़ बॉट से निकाली हुई असली प्राइवेट चैनल आईडी यहाँ डालें
SOURCE_CHANNEL = -1001732832207  
MY_CHANNEL = -1004442599529      

# अब यह बिना किसी फ़ाइल के सीधे स्ट्रिंग से लाइव कनेक्ट होगा
client = TelegramClient(StringSession(TELEGRAM_STRING_SESSION), API_ID, API_HASH).start()
bot = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# --- 3. डिस्कवाला और Filemoon का ASYNC लॉजिक ---
async def get_diskwala_mp4(diskwala_url):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
            page = await browser.new_page()
            await page.goto(diskwala_url, timeout=30000, wait_until="domcontentloaded")
            real_mp4_url = await page.eval_on_selector("video source", "el => el.src") 
            await browser.close()
            return real_mp4_url
    except Exception as e:
        print(f"DiskWala Error: {e}")
        return None

async def upload_to_filemoon(real_mp4_url):
    try:
        api_url = "https://filemoonapi.com"
        params = {'key': FILEMOON_API_KEY, 'url': real_mp4_url}
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, params=params, timeout=20) as response:
                if response.status == 200:
                    res_data = await response.json()
                    if res_data.get('status') == 200 or res_data.get('msg') == 'OK':
                        return res_data['result']['filecode'] 
    except Exception as e:
        print(f"Filemoon API Error: {e}")
    return None

# --- 4. ऑटो-फॉर्वर्डर इवेंट ---
@client.on(events.NewMessage(chats=SOURCE_CHANNEL))
async def handle_new_message(event):
    print("🔔 सोर्स चैनल में एक नया मैसेज आया है!")
    message_text = event.message.message or ""
    links = re.findall(r'(https?://(?:www\.)?diskwala\.com/[^\s]+)', message_text)
    
    if links:
        diskwala_url = links[0] # पहला लिंक उठा रहे हैं
        print(f"🔗 डिस्कवाला लिंक मिला: {diskwala_url}")
        
        real_link = await get_diskwala_mp4(diskwala_url)
        if real_link:
            filecode = await upload_to_filemoon(real_link)
            if filecode:
                bot_me = await bot.get_me()
                bot_username = bot_me.username
                secured_link = f"https://t.me{bot_username}?start={filecode}"
                new_caption = f"🎬 **New Exclusive Clip (20 Min)**\n\n👉 **Watch Full Video Here:** {secured_link}"
                
                if event.message.media and not getattr(event.message.file, 'size', 0) > 50 * 1024 * 1024:
                    try:
                        media_file = await event.message.download_media()
                        await client.send_file(MY_CHANNEL, media_file, caption=new_caption)
                        if os.path.exists(media_file): os.remove(media_file)
                    except Exception as e:
                        print(f"Media forwarding error: {e}")
                        await client.send_message(MY_CHANNEL, new_caption)
                else:
                    await client.send_message(MY_CHANNEL, new_caption)

# --- 5. यूज़र मोड (Start Button) ---
@bot.on(events.NewMessage(pattern='/start'))
async def handle_bot_start(event):
    text = event.message.message
    parts = text.split(' ')
    if len(parts) > 1:
        filecode = parts[1]
        filemoon_player_url = f"https://filemoon.sx{filecode}"
        await event.reply(
            f"👋 **यहाँ आपका वीडियो तैयार है!**\n\nनीचे दिए गए बटन पर क्लिक करके प्ले करें:",
            buttons=[[event.client.button('🎬 Play Video', url=filemoon_player_url)]]
        )
    else:
        # बाहरी यूजर अगर सर्च से आकर स्टार्ट करेगा तो यह दिखेगा:
        await event.reply("Welcome to Filemoon Link Protector Bot.\nUse a valid link from our channel to watch videos.")

# --- 6. मुख्य एक्जीक्यूशन ---
if __name__ == '__main__':
    t = Thread(target=run_web_server)
    t.daemon = True
    t.start()
    print("Web server & Bot are running smoothly...")
    client.run_until_disconnected()
