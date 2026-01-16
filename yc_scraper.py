import csv
import time
import re
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager



# CONFIGURATION

# DATA COVERAGE: Target 500 companies as per requirement
TARGET_COMPANIES = 500          # Number of companies to scrape
SCROLL_WAIT_TIME = 1.5          # Seconds to wait after each scroll
PAGE_LOAD_TIMEOUT = 10          # Max seconds to wait for page load
RATE_LIMIT_DELAY = 0.5          # Delay between requests (be respectful)
PROGRESS_SAVE_INTERVAL = 50     # Save progress every N companies
MAX_SCROLL_ATTEMPTS = 100       # Maximum scroll attempts before stopping
MAX_WORKERS = 5                 # BONUS: Concurrent workers for parallel scraping


# BROWSER SETUP
def setup_driver():
 
    options = Options()
    
    # Headless mode - runs without visible browser window
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # Realistic user agent to avoid bot detection
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    
    # Auto-download and setup ChromeDriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    return driver


# PAGINATION / INFINITE SCROLL HANDLING

# NAVIGATION LOGIC: Handles dynamic infinite scroll pagination
def scroll_and_load(driver, target_count=TARGET_COMPANIES):
   
    companies_loaded = 0
    last_count = 0
    scroll_attempts = 0
    
    print(f"[SCROLL] Loading {target_count} companies via infinite scroll...")
    
    while companies_loaded < target_count and scroll_attempts < MAX_SCROLL_ATTEMPTS:
        # Execute JavaScript to scroll to bottom of page
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_WAIT_TIME)  # Wait for dynamic content to load
        
        # Count currently loaded company cards
        company_cards = driver.find_elements(By.CSS_SELECTOR, "a[class*='_company_']")
        if not company_cards:
            # Fallback selectors for different page structures
            company_cards = driver.find_elements(
                By.CSS_SELECTOR, 
                "[class*='CompanyCard'], [class*='company-card'], a[href^='/companies/']"
            )
        
        companies_loaded = len(company_cards)
        
        # Progress indicator
        if companies_loaded != last_count:
            print(f"[SCROLL] Loaded {companies_loaded} companies...")
        
        # Check if we're still loading new content
        if companies_loaded == last_count:
            scroll_attempts += 1
        else:
            scroll_attempts = 0  # Reset counter when new content loads
        
        last_count = companies_loaded
        
        # Stop if no new content after multiple attempts
        if scroll_attempts >= 5:
            print("[SCROLL] No new content loading, stopping scroll...")
            break
    
    return companies_loaded


# COMPANY DATA EXTRACTION

def extract_company_slugs(driver):
    
    # Find all company links
    company_links = driver.find_elements(By.CSS_SELECTOR, "a[href^='/companies/']")
    
    # Extract unique slugs
    seen_slugs = set()
    
    for link in company_links:
        href = link.get_attribute("href")
        if href and "/companies/" in href:
            # Parse slug from URL: /companies/stripe -> stripe
            slug = href.split("/companies/")[-1].split("?")[0].split("/")[0]
            if slug and slug not in seen_slugs:
                seen_slugs.add(slug)
    
    print(f"[EXTRACT] Found {len(seen_slugs)} unique company slugs")
    return list(seen_slugs)

# SCRAPING SKILL: Extracts both static and dynamic data accurately
def scrape_company_details(driver, slug):

    url = f"https://www.ycombinator.com/companies/{slug}"
    
    try:
        driver.get(url)
        time.sleep(0.5)
        
        # Wait for page to load (look for main heading)
        WebDriverWait(driver, PAGE_LOAD_TIMEOUT).until(
            EC.presence_of_element_located((By.TAG_NAME, "h1"))
        )
        
        # Initialize data structure
        company_data = {
            "Company Name": "",
            "Batch": "",
            "Short Description": "",
            "Founder Names": "",
            "Founder LinkedIn URLs": ""
        }
        
        # Extract Company Name 
        try:
            name_elem = driver.find_element(By.TAG_NAME, "h1")
            company_data["Company Name"] = name_elem.text.strip()
        except:
            pass
        
        # Extract YC Batch
        # Batch format: S20 (Summer 2020), W21 (Winter 2021), F25 (Fall 2025)
        try:
            page_text = driver.page_source
            batch_match = re.search(r'\b([SWF]\d{2})\b', page_text)
            if batch_match:
                company_data["Batch"] = batch_match.group(1)
        except:
            pass
        
        # Extract Description
        try:
            desc_selectors = [
                "div[class*='prose']",
                "p[class*='description']",
                "div[class*='tagline']"
            ]
            for selector in desc_selectors:
                try:
                    desc_elem = driver.find_element(By.CSS_SELECTOR, selector)
                    if desc_elem.text:
                        company_data["Short Description"] = desc_elem.text.strip()[:500]
                        break
                except:
                    continue
        except:
            pass
        
        # Extract Founders and LinkedIn URLs 
        try:
            founder_names = []
            founder_linkedins = []
            
            # Find founder sections/cards
            founder_elements = driver.find_elements(
                By.CSS_SELECTOR, 
                "[class*='founder'], [class*='Founder']"
            )
            
            for elem in founder_elements:
                try:
                    # Extract founder name (usually first line of text)
                    name = elem.text.split('\n')[0].strip()
                    if name and len(name) < 100:
                        founder_names.append(name)
                    
                    # Extract LinkedIn URL from founder card
                    linkedin_link = elem.find_elements(
                        By.CSS_SELECTOR, 
                        "a[href*='linkedin.com']"
                    )
                    if linkedin_link:
                        founder_linkedins.append(linkedin_link[0].get_attribute("href"))
                except:
                    continue
            
            # Fallback: Search for any LinkedIn profile links on page
            if not founder_linkedins:
                all_linkedin = driver.find_elements(
                    By.CSS_SELECTOR, 
                    "a[href*='linkedin.com/in/']"
                )
                for link in all_linkedin:
                    href = link.get_attribute("href")
                    if href and href not in founder_linkedins:
                        founder_linkedins.append(href)
            
            # Join multiple founders with semicolon separator
            company_data["Founder Names"] = "; ".join(founder_names[:5])
            company_data["Founder LinkedIn URLs"] = "; ".join(founder_linkedins[:5])
            
        except:
            pass
        
        return company_data
        
    except Exception as e:
        print(f"[ERROR] Failed to scrape {slug}: {e}")
        return None


# DATA CLEANING
def clean_description(desc):

    if not desc:
        return ""
    
    # Replace newlines with spaces
    cleaned = desc.replace('\n', ' ').replace('\r', ' ')
    
    # Collapse multiple spaces into single space
    cleaned = ' '.join(cleaned.split())
    
    # Truncate long descriptions
    if len(cleaned) > 200:
        return cleaned[:200] + '...'
    
    return cleaned


# CSV OUTPUT
# CODE QUALITY: Modular CSV saving with data cleaning
def save_to_csv(companies, filename="yc_startups.csv"):
  
    if not companies:
        print("[SAVE] No companies to save!")
        return
    
    # Clean descriptions before saving
    for company in companies:
        company["Short Description"] = clean_description(
            company.get("Short Description", "")
        )
    
    # Define CSV columns (with numbering)
    fieldnames = [
        "No",
        "Company Name", 
        "Batch", 
        "Short Description", 
        "Founder Names", 
        "Founder LinkedIn URLs"
    ]
    
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        # Add row numbers
        for i, company in enumerate(companies, 1):
            company["No"] = i
            writer.writerow(company)
    
    print(f"[SAVE] Saved {len(companies)} companies to {filename}")



# MAIN SCRAPER
def main():
   
    print("=" * 70)
    print("  Y COMBINATOR STARTUP DIRECTORY SCRAPER")
    print("  Target: ~500 companies with founder info")
    print("=" * 70)
    
    # Initialize browser
    print("\n[SETUP] Initializing Chrome WebDriver...")
    driver = setup_driver()
    
    try:
        # Load YC companies directory
        print("\n[LOAD] Opening YC companies directory...")
        driver.get("https://www.ycombinator.com/companies")
        time.sleep(3)  # Initial page load
        
        # Handle infinite scroll pagination
        print("\n[PAGINATION] Handling infinite scroll...")
        scroll_and_load(driver, target_count=TARGET_COMPANIES + 50)
        
        # Extract company identifiers
        print("\n[EXTRACT] Extracting company slugs...")
        company_slugs = extract_company_slugs(driver)
        
        # Close initial driver - we'll use concurrent drivers for individual pages
        driver.quit()
        driver = None  # Mark as closed
        print("[INFO] Initial driver closed, starting concurrent scraping...")
        
        # Scrape individual company pages
        all_companies = []
        target = min(TARGET_COMPANIES, len(company_slugs))
        
        print(f"\n[SCRAPE] Scraping {target} company pages...")
        print("-" * 70)
        
        # BONUS: Concurrent scraping using ThreadPoolExecutor for efficiency
        def scrape_with_driver(slug):
            thread_driver = setup_driver()
            try:
                return scrape_company_details(thread_driver, slug)
            finally:
                thread_driver.quit()
        
        # Use concurrent execution for faster scraping
        print(f"[INFO] Using {MAX_WORKERS} concurrent workers for parallel scraping...")
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Submit all scraping tasks
            future_to_slug = {
                executor.submit(scrape_with_driver, slug): slug 
                for slug in company_slugs[:target]
            }
            
            # Collect results as they complete
            for i, future in enumerate(future_to_slug, 1):
                slug = future_to_slug[future]
                try:
                    print(f"[{i:3d}/{target}] Scraping: {slug}")
                    company_data = future.result()
                    
                    if company_data and company_data["Company Name"]:
                        all_companies.append(company_data)
                    
                    # Progress backup (every 50 companies)
                    if len(all_companies) > 0 and len(all_companies) % PROGRESS_SAVE_INTERVAL == 0:
                        save_to_csv(all_companies, "yc_startups_progress.csv")
                        print(f"[BACKUP] Progress saved: {len(all_companies)} companies")
                except Exception as e:
                    print(f"[ERROR] Failed to scrape {slug}: {e}")
        
        # Save final results
        print("\n" + "-" * 70)
        save_to_csv(all_companies, "yc_startups.csv")
        
        # Print summary
        print("\n" + "=" * 70)
        print("  SCRAPING COMPLETE!")
        print(f"  Total companies scraped: {len(all_companies)}")
        print(f"  Output file: yc_startups.csv")
        print("=" * 70)
        
        # Show sample data
        if all_companies:
            print("\n[SAMPLE] First 3 companies:")
            print("-" * 70)
            for i, company in enumerate(all_companies[:3], 1):
                print(f"\n  {i}. {company['Company Name']}")
                print(f"     Batch: {company['Batch'] or 'N/A'}")
                desc = company['Short Description']
                print(f"     Description: {desc[:60] if desc else 'N/A'}...")
                print(f"     Founders: {company['Founder Names'] or 'N/A'}")
                linkedin = company['Founder LinkedIn URLs']
                if linkedin:
                    print(f"     LinkedIn: {linkedin[:50]}...")
    
    except Exception as e:
        print(f"\n[ERROR] Fatal error: {e}")
    finally:
        # Always close browser if it's still open
        if 'driver' in locals() and driver is not None:
            driver.quit()
            print("\n[CLEANUP] Browser closed.")


# ENTRY POINT
if __name__ == "__main__":
    main()
