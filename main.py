import os
import re
import asyncio
import aiohttp
from flask import Flask
from threading import Thread
from telethon import TelegramClient, events
from telethon.sessions import StringSession 
from playwright.async_api import async_playwright

# --- 1. पिंग के लिए Flask वेब-सर्वर सेटअप ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running!"

def run_web_server():
    app.run(host='0.0.0.0', port=10000)

# --- 2. टेलीग्राम और API कॉन्फ़िगरेशन ---
# ⚠️ यहाँ अपनी असली डिटेल्स ध्यान से भरें:
API_ID = 34278215         # my.telegram.org से लें (बिना कोट्स के)
API_HASH = '82aafe1590473bdbc558f60c46ed3387' 
BOT_TOKEN = '8817454197:AAGdII5VzjvJfBHG2gQ6n0j6G3v0xNTKnU0' 
FILEMOON_API_KEY = '110|4mK5RhaO8YzMQb2aXgmcDuPqXTUgxdrzysgz6kP3' 

# 🎯 आपकी नोटपैड वाली लंबी स्ट्रिंग यहाँ आएगी:
TELEGRAM_STRING_SESSION = """1BVtsOMABu0gry-tc2n1t6umsoPgW6zR_cHS1EE4QfRm2L1f4pVNSgkcNyFGh_l30YudtJU0qU80dTFZfXrHYnYWIZDnp5XvJFlTTchxFzUZ0xQ-vlgrL3FJNJw8YqBTYrRFnPK1e7ItEttBG8qc-D60-wXcATtLtxYQ4v2HqN9CYgYy6xDp89zqLp83KEoeQIth6Qnv9SMxc_glP6zEFE6Ur2-KfVgoJ9G5UuratDWGhfncLstYKeqbrF7Qd4NLsXlCk-a7EYDc6Q-3UZx278jA5aeMGKyjIdQ2uxqe0tG3l6W6Nd5REGZWrNCLjooWuJ2VkYR5ZP03kMNUGUSlvec5O2tN9B4M="""

# 🎯 रोज़ बॉट से निकाली हुई असली प्राइवेट चैनल आईडी यहाँ डालें (बिना कोट्स के)
SOURCE_CHANNEL = -1001732832207  
MY_CHANNEL = -1004442599529      

client = TelegramClient(StringSession(TELEGRAM_STRING_SESSION), API_ID, API_HASH).start()
bot = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# --- 3. डिस्कवाला और Filemoon का ASYNC लॉजिक (Updated Auto-Click) ---
async def get_diskwala_mp4(diskwala_url):
    """Playwright से /app/ पेज खोलकर बटन क्लिक करके असली .mp4 लिंक निकालना"""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True, 
                args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            page = await browser.new_page()
            
            print(f"⏳ डिस्कवाला लिंक खोल रहा हूँ: {diskwala_url}")
            await page.goto(diskwala_url, timeout=30000, wait_until="domcontentloaded")
            
            # बैकअप: अगर डायरेक्ट सोर्स दिख रहा हो
            try:
                real_mp4_url = await page.eval_on_selector("video source", "el => el.src")
                if real_mp4_url:
                    await browser.close()
                    return real_mp4_url
            except:
                pass

            # 🎯 न्यू फ़िक्स: अगर डाउनलोड/प्लेयर बटन है, तो उस पर क्लिक करने का इंतज़ार करें
            # यह डिस्कवाला के सामान्य प्लेयर/डाउनलोड बटन सिलेक्टर्स को ढूंढेगा
            button_selectors = ["a.btn", "button", "a[href*='download']", "a[href*='stream']"]
            for selector in button_selectors:
                try:
                    if await page.is_visible(selector):
                        print(f"🖱️ बटन मिला ({selector}), क्लिक कर रहा हूँ...")
                        await page.click(selector)
                        await page.wait_for_timeout(3000) # लोड होने के लिए 3 सेकंड रुकें
                        break
                except:
                    continue
            
            # क्लिक करने के बाद दोबारा वीडियो सोर्स चेक करें
            html_content = await page.content()
            match = re.search(r'["\'](https?://[^\s"\']+\.mp4[^\s"\']*)["\']', html_content)
            if match:
                real_mp4_url = match.group(1)
                print(f"✅ असली MP4 लिंक मिल गया!")
                await browser.close()
                return real_mp4_url
                
            await browser.close()
    except Exception as e:
        print(f"❌ DiskWala Extraction Error: {e}")
    return None

async def upload_to_filemoon(real_mp4_url):
    """Filemoon Remote Upload API का उपयोग करके वीडियो अपलोड करना"""
    try:
        api_url = "https://filemoonapi.com"
        params = {
            'key': FILEMOON_API_KEY, 
            'url': real_mp4_url
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, params=params, timeout=20) as response:
                if response.status == 200:
                    res_data = await response.json()
                    if res_data.get('status') == 200 or res_data.get('msg') == 'OK':
                        return res_data['result']['filecode']
                    else:
                        print(f"⚠️ Filemoon API Error Response: {res_data}")
    except Exception as e:
        print(f"❌ Filemoon API Error: {e}")
    return None

# --- 4. ऑटो-फॉर्वर्डर इवेंट ---
@client.on(events.NewMessage(chats=SOURCE_CHANNEL))
async def handle_new_message(event):
    print("🔔 सोर्स चैनल में एक नया मैसेज आया है!")
    message_text = event.message.message or ""
    links = re.findall(r'(https?://(?:www\.)?diskwala\.com/[^\s]+)', message_text)
    
    if links:
        diskwala_url = links[0]
        print(f"🔗 डिस्कवाला लिंक मिला: {diskwala_url}")
        
        real_link = await get_diskwala_mp4(diskwala_url)
        if real_link:
            print(f"⏳ Filemoon पर अपलोड शुरू किया जा रहा है...")
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
                print("✅ टारगेट चैनल में पोस्ट सफलतापूर्वक भेज दी गई है!")
        else:
            print("❌ डिस्कवाला से असली वीडियो लिंक नहीं निकाला जा सका।")

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
        await event.reply("Welcome to Filemoon Link Protector Bot.\nUse a valid link from our channel to watch videos.")

# --- 6. मुख्य एक्जीक्यूशन ---
if __name__ == '__main__':
    t = Thread(target=run_web_server)
    t.daemon = True
    t.start()
    print("Web server & Bot are running smoothly...")
    client.run_until_disconnected()
