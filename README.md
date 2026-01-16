# YC Startup Web Scraper (Python & Selenium)

This project is a Python-based web scraper designed to collect startup information from the **Y Combinator company directory**.

Since the YC platform loads content dynamically using JavaScript, traditional static scraping tools are not sufficient. This scraper uses **Selenium with a headless Chrome browser** to handle dynamic rendering and infinite scrolling.

---

## 🚀 Features

- Dynamic web scraping using **Python & Selenium**
- Headless Chrome setup with **webdriver-manager**
- Infinite scrolling support to load large datasets
- Extraction of structured startup data into **CSV format**
- Progress-saving mechanism to prevent data loss
- Fallback logic to handle varying page structures

---

## 🛠️ Tech Stack

- Python
- Selenium
- WebDriver Manager
- Chrome (Headless)

---

## 📂 Extracted Data

For each startup, the scraper collects:
- Company name
- Batch year
- Short description
- Founder names
- Founder LinkedIn URLs

---

## ⚙️ Setup & Usage

### 1️⃣ Clone the repository
```bash
git clone https://github.com/KavishkaKodithuwakku/YC-Startup-Web-Scraper-Python-Selenium.git
cd YC-Startup-Web-Scraper-Python-Selenium

