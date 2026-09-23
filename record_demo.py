import asyncio
import os
import shutil
from playwright.async_api import async_playwright

ARTIFACTS_DIR = "/config/.gemini/antigravity/brain/0eca49ad-1285-4ad3-95c8-e21604a6a68a"
APP_URL = "https://support-pulse-frontend-464482224032.us-central1.run.app"
TEMP_REC_DIR = os.path.join(os.getcwd(), "temp_rec")

async def record_demo():
    os.makedirs(TEMP_REC_DIR, exist_ok=True)
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            record_video_dir=TEMP_REC_DIR,
            record_video_size={"width": 1280, "height": 800}
        )
        page = await context.new_page()

        print("Navigating to SupportPulse live web app...")
        await page.goto(APP_URL, wait_until="networkidle")
        await asyncio.sleep(2)

        chat_input = page.locator("#user-input")
        send_btn = page.locator("#send-btn")

        # --- PROMPT 1: Order Tracking ---
        prompt1 = "Track order ORD-1001 and show me delivery status"
        print(f"Submitting Prompt 1: {prompt1}")
        await chat_input.fill(prompt1)
        await asyncio.sleep(1)
        await send_btn.click()

        print("Waiting for response to Prompt 1...")
        for _ in range(8):
            await asyncio.sleep(1)
            await page.evaluate("window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });")
            await page.evaluate("document.getElementById('log').scrollTo({ top: document.getElementById('log').scrollHeight, behavior: 'smooth' });")

        await asyncio.sleep(2)

        # --- PROMPT 2: Multi-Tool (Database + Video + Image) ---
        prompt2 = "Check inventory for SKU-HEADPHONES in database, then generate a promotional product video and a new product preview image for Wireless Headphones."
        print(f"Submitting Prompt 2: {prompt2}")
        await chat_input.fill(prompt2)
        await asyncio.sleep(1)
        await send_btn.click()

        print("Waiting for response to Prompt 2 (video & image generation)...")
        for i in range(35):
            await asyncio.sleep(1)
            if i % 5 == 0:
                await page.evaluate("window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });")
                await page.evaluate("document.getElementById('log').scrollTo({ top: document.getElementById('log').scrollHeight, behavior: 'smooth' });")
                print(f"  ... waited {i}s (scrolling down)")

        print("Ensuring scroll to bottom to showcase generated image & video player...")
        for _ in range(3):
            await page.evaluate("window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });")
            await page.evaluate("document.getElementById('log').scrollTo({ top: document.getElementById('log').scrollHeight, behavior: 'smooth' });")
            await asyncio.sleep(2)

        print("Finished recording session. Closing page, context & browser...")
        video_obj = page.video
        await page.close()
        await context.close()
        await browser.close()

        video_path = await video_obj.path()
        target_video = os.path.join(ARTIFACTS_DIR, "support_pulse_demo.webm")
        print(f"Playwright flushed video path: {video_path}")
        if video_path and os.path.exists(video_path):
            shutil.copyfile(video_path, target_video)
            print(f"Successfully recorded demo video to: {target_video}")
            print(f"Video size: {os.path.getsize(target_video)} bytes")

if __name__ == "__main__":
    asyncio.run(record_demo())
