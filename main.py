import os
import time
import json
import re
from datetime import datetime
from bs4 import BeautifulSoup, Comment 
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from openai import OpenAI
from dotenv import load_dotenv

# --- CONFIGURATION & SETUP ---
load_dotenv() 

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
AI_MODEL = "openai/gpt-oss-20b:free" 
SITE_URL = "https://openrouter.ai/api/v1"

# Bot Configuration
PHONE_NUMBER = os.getenv("SNAPP_PHONE", "09120000000")
DEFAULT_TARGET_NAME = os.getenv("TARGET_PRODUCT_NAME", "iPhone") # Default if manual selection fails
HEADLESS_MODE = True 
START_STEP = int(os.getenv("STEP", "1"))

if not OPENROUTER_API_KEY:
    print("⚠️ WARNING: OPENROUTER_API_KEY is missing in .env file.")

class AINavigator:
    def __init__(self):
        self.client = OpenAI(
            base_url=SITE_URL,
            api_key=OPENROUTER_API_KEY,
        )

    def clean_html(self, raw_html):
        """
        Fixed cleaning logic to avoid AttributeError.
        """
        if not raw_html: return ""
        
        soup = BeautifulSoup(raw_html, 'html.parser')
        
        # 1. Remove non-visual tags
        for tag in soup(['script', 'style', 'svg', 'path', 'noscript', 'meta', 'link', 'iframe', 'footer']):
            tag.decompose()
            
        # 2. Remove comments (Fixed Logic)
        comments = soup.find_all(string=lambda text: isinstance(text, Comment))
        for c in comments:
            c.extract()

        # 3. Simplify attributes
        allowed_attrs = ['id', 'class', 'name', 'type', 'role', 'aria-label', 'placeholder', 'href', 'value']
        for tag in soup.find_all(True):
            attrs = dict(tag.attrs)
            tag.attrs = {key: value for key, value in attrs.items() if key in allowed_attrs}
            
        return str(soup)[:60000]

    def ask_ai(self, prompt, context_html):
        full_prompt = f"""
        You are a web automation assistant. 
        {prompt}
        
        HTML Context:
        {context_html}
        """
        try:
            response = self.client.chat.completions.create(
                model=AI_MODEL,
                messages=[{"role": "user", "content": full_prompt}],
                temperature=0.0, 
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ OpenRouter Error: {e}")
            return None

    def find_selector(self, page, description, html_override=None):
        """
        Finds selector. Supports html_override to look in specific sections.
        """
        print(f"🧠 AI: Analyzing page to find '{description}'...")
        
        try:
            if html_override:
                content = html_override
            else:
                content = page.content()
        except:
            return None
            
        html = self.clean_html(content)
        
        prompt = f"""
        Analyze the HTML. Find the CSS Selector for the element matching this description: "{description}".
        
        Rules:
        1. Return ONLY the CSS selector string. Nothing else. No markdown.
        2. If the element is a button with Persian text, use specific attributes like [class*="..."] or text.
        3. If not found, return "NOT_FOUND".
        """
        
        selector = self.ask_ai(prompt, html)

        # --- LOG AI RESPONSE ---
        if selector:
            print(f"   -> 🤖 AI Response: {selector}")
        # -----------------------

        if selector and "NOT_FOUND" not in selector:
            selector = selector.replace("```css", "").replace("```", "").strip()
            print(f"   -> Selector found: {selector}")
            return selector
        print("   -> Element not found by AI.")
        return None

    def extract_timetable(self, page):
        print("🧠 AI: Extracting timetable data...")
        html = self.clean_html(page.content())
        
        prompt = f"""
        This is a timetable page. Extract a JSON list of products.
        Format: [{{"name": "Product Name", "time": "HH:MM"}}]
        Return ONLY valid JSON.
        """
        
        response = self.ask_ai(prompt, html)

        # --- LOG AI RESPONSE ---
        if response:
            preview = response[:100] + "..." if len(response) > 100 else response
            print(f"   -> 🤖 AI Response (Preview): {preview}")
        # -----------------------

        try:
            if not response: return []
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                return json.loads(match.group())
            return json.loads(response)
        except:
            print(f"   -> Failed to parse JSON. Response was: {response[:100]}...")
            return []

    def extract_campaign_products(self, page):
        """
        Extracts all products from a campaign page into JSON.
        Returns: List of dicts [{'name': '...', 'selector': '...'}]
        """
        print("🧠 AI: Extracting all products from campaign page...")
        html = self.clean_html(page.content())
        
        prompt = """
        Analyze this campaign page HTML. Identify all product cards.
        Return a JSON list where each item has:
        1. "name": The product title/name (in Persian or English).
        2. "selector": A unique CSS selector (e.g. href or specific class) to click specifically on this product card.
        
        Format: [{"name": "iPhone 13", "selector": "a[href*='product-123']"}, ...]
        Return ONLY valid JSON.
        """
        
        response = self.ask_ai(prompt, html)

        # --- LOG AI RESPONSE ---
        if response:
            preview = response[:100] + "..." if len(response) > 100 else response
            print(f"   -> 🤖 AI Response (Preview): {preview}")
        # -----------------------

        try:
            if not response: return []
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                return json.loads(match.group())
            return json.loads(response)
        except:
            print(f"   -> Failed to parse JSON. Response was: {response[:100]}...")
            return []

class SnappBot:
    def __init__(self, input_handler=None, log_handler=None):
        self.ai = AINavigator()
        self.target_time = None
        self.target_product_name = DEFAULT_TARGET_NAME
        self.input_handler = input_handler if input_handler else input
        self.log_handler = log_handler if log_handler else print

    def log(self, message):
        if self.log_handler:
            self.log_handler(message)

    def safe_goto(self, page, url, retries=2):
        """Helper to load pages with retries and better timeouts"""
        for i in range(retries):
            try:
                self.log(f"   -> Loading {url} (Attempt {i+1})...")
                page.goto(url, timeout=90000, wait_until='domcontentloaded') 
                return True
            except PlaywrightTimeout:
                self.log("   -> Timeout! Retrying...")
            except Exception as e:
                self.log(f"   -> Load error: {e}")
        return False

    def run(self):
        with sync_playwright() as p:
            self.log(f"🚀 Launching Browser (Starting from Step {START_STEP})...")
            browser = p.chromium.launch(
                headless=HEADLESS_MODE,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            context_args = {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            if os.path.exists("session.json"):
                self.log("   -> 📂 Loading saved session from session.json")
                context_args["storage_state"] = "session.json"

            context = browser.new_context(**context_args)
            page = context.new_page()

            # --- STEP 1 LOGIC ---
            if START_STEP <= 1:
                self.step_1_timetable(page)
            else:
                self.log("⏩ Skipping Step 1 (Timetable)...")
                if not self.target_time:
                    self.target_time = datetime.now().strftime("%H:%M")
                    self.log(f"   -> Defaulted time to {self.target_time}")

            # --- STEP 2 LOGIC ---
            if START_STEP <= 2:
                self.step_2_login(page)
            else:
                self.log("⏩ Skipping Step 2 (Login)...")

            # --- STEP 3 LOGIC ---
            if START_STEP <= 3:
                self.step_3_purchase(page)

            browser.close()

    def step_1_timetable(self, page):
        self.log("\n--- STEP 1: Reading Timetable ---")
        url = "https://snapppay.ir/timetable/?utm_source=snapppay"
        
        if not self.safe_goto(page, url):
            self.log("❌ Failed to load timetable. Skipping to Step 2 with default time.")
            self.target_time = datetime.now().strftime("%H:%M")
            return

        time.sleep(3) # Short wait for JS
        
        products = self.ai.extract_timetable(page)
        
        if products:
            self.log("\n📋 Found Products in Timetable:")
            self.log("="*40)
            for idx, p in enumerate(products):
                self.log(f"   [{idx + 1}] {p.get('name', 'Unknown')} (Time: {p.get('time', '??')})")
            self.log("="*40)
            
            # Interactive Selection
            while True:
                choice = self.input_handler("\n👉 Enter the number of the product you want to buy (or 'skip' to use default): ")
                if choice.lower() == 'skip':
                    break
                if choice.strip().isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(products):
                        selected = products[idx]
                        self.target_product_name = selected.get('name', DEFAULT_TARGET_NAME)
                        self.target_time = selected.get('time')
                        self.log(f"✅ Target Locked: {self.target_product_name}")
                        self.log(f"⏰ Scheduled Time: {self.target_time}")
                        return
                    else:
                        self.log("❌ Invalid number. Please try again.")
                else:
                    self.log("❌ Please enter a number.")
        else:
            self.log("⚠️ No products found by AI. Defaulting to IMMEDIATE mode.")

        # Default fallback if list empty or skipped
        if not self.target_time:
            self.target_time = datetime.now().strftime("%H:%M")
            self.log(f"⚠️ Using immediate time: {self.target_time}")

    def step_2_login(self, page):
        self.log("\n--- STEP 2: Login Flow ---")
        if not self.safe_goto(page, "https://app.snapp.taxi/login"):
            self.log("❌ Could not load login page.")
            return

        time.sleep(2)

        needs_login = True
        
        # Check if already logged in (redirected or input missing)
        if "login" not in page.url:
            self.log(f"✅ Already logged in (URL: {page.url}).")
            needs_login = False
        else:
            is_login_page = False
            try:
                if page.locator('[aria-label="شمارهٔ موبایل"]').is_visible() or \
                   page.locator("input[type='tel']").is_visible():
                    is_login_page = True
            except:
                pass

            if not is_login_page:
                self.log("✅ Already logged in (Login inputs not found).")
                needs_login = False

        if needs_login:
            # 1. Fill Phone
            try:
                self.log("   -> Trying specific aria-label selector...")
                page.locator('[aria-label="شمارهٔ موبایل"]').fill(PHONE_NUMBER)
                self.log("   -> Clicking submit button...")
                page.locator('[aria-label="ثبت شماره موبایل"]').click()
            except:
                try:
                    self.log("   -> Specific selector failed. Trying generic...")
                    page.locator("input[type='tel']").fill(PHONE_NUMBER)
                    page.keyboard.press("Enter")
                except:
                    self.log("   -> Generic failed. Asking AI...")
                    selector_phone = self.ai.find_selector(page, "The input field for mobile number")
                    if selector_phone:
                        page.locator(selector_phone).first.fill(PHONE_NUMBER)
                        page.keyboard.press("Enter")

            # 2. OTP Entry
            self.log("\n👉 ACTION: Please check SMS.")
            otp_code = self.input_handler("⌨️ Enter OTP code: ")
            
            try:
                self.log(f"   -> Entering {otp_code}...")
                try:
                    self.log("   -> Using specific OTP selector...")
                    page.locator('[data-qa-id="input-otp"]').fill(otp_code)
                except:
                    self.log("   -> Specific OTP selector failed. Typing blindly...")
                    page.keyboard.type(otp_code)

                time.sleep(0.5)
                page.keyboard.press("Enter")
            except Exception as e:
                self.log(f"   -> OTP Entry error: {e}")

            time.sleep(5)

            # Save session
            try:
                page.context.storage_state(path="session.json")
                self.log("   -> 💾 Session saved to session.json")
            except Exception as e:
                self.log(f"   -> ⚠️ Failed to save session: {e}")
        
        # 3. Wait Loop
        if self.target_time:
            self.log(f"⏳ Waiting for Target Time: {self.target_time}...")
            while True:
                current_time = datetime.now().strftime("%H:%M")
                if current_time == self.target_time:
                    self.log("🚨 TIME MATCHED! GO!")
                    break
                time.sleep(1)

    def step_3_purchase(self, page):
        self.log("\n--- STEP 3: Purchase ---")
        
        campaign_urls = [
            "https://pl.snapp.ir/products?section_name=Campaign_Home&referrer=MAIN",
            "https://pl.snapp.ir/products?section_name=Campaign_70&referrer=MAIN"
        ]
        
        product_found = False

        for url in campaign_urls:
            self.log(f"   -> Checking Campaign URL: {url}")
            self.safe_goto(page, url)
            time.sleep(1)

            # 1. EXTRACT ALL PRODUCTS
            products = self.ai.extract_campaign_products(page)
            
            # 2. SAVE FOR DEBUGGING
            debug_filename = "debug_products_step3.json"
            try:
                with open(debug_filename, "w", encoding="utf-8") as f:
                    json.dump(products, f, ensure_ascii=False, indent=2)
                self.log(f"   -> 💾 Saved {len(products)} products to {debug_filename}")
            except Exception as e:
                self.log(f"   -> ⚠️ Failed to save debug file: {e}")

            # 3. SEARCH IN JSON
            self.log(f"   -> Searching for '{self.target_product_name}' in extracted data...")
            target_selector = None
            
            for p in products:
                # Case-insensitive partial match
                if self.target_product_name.lower() in p.get('name', '').lower():
                    self.log(f"   -> 🎯 Match Found: {p['name']}")
                    target_selector = p.get('selector')
                    break
            
            if target_selector:
                try:
                    self.log(f"   -> Clicking product using selector: {target_selector}")
                    page.locator(target_selector).first.click()
                    product_found = True
                    break 
                except Exception as e:
                    self.log(f"   -> Click failed: {e}")
                    # Try fallback force click
                    try:
                        page.locator(target_selector).first.click(force=True)
                        product_found = True
                        break
                    except:
                        pass
            else:
                 self.log("   -> Product match not found in extracted JSON list.")
        
        if not product_found:
            self.log("❌ Product not found in any provided campaign URLs. Check 'debug_products_step3.json' to see what AI found.")
            return

        time.sleep(3)

        # 2. Add to Cart
        selector_add = self.ai.find_selector(page, "The 'Add to Cart' button (Green/Blue button)")
        if selector_add:
            page.locator(selector_add).first.click()
            self.log("✅ Added to cart.")
            time.sleep(2)
        
        # 3. Checkout
        self.log("Bot finished. Payment details would go here.")

if __name__ == "__main__":
    bot = SnappBot()
    bot.run()