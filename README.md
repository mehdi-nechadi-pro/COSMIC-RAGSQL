# 🪐 AstroChat - AI Astronomical Observation Assistant

**AstroChat** is an intelligent assistant designed for amateur astronomers. It combines the power of Large Language Models (**Gemini**) with precise astronomical calculations (**Astropy**) to recommend observation targets in real-time, filtered by location, time, and visibility conditions.

The experience is delivered through a modern web interface featuring an interactive planetarium (**VirtualSky**).

---

## ✨ Key Features

* **💬 Natural & Context-Aware Chat:** Ask questions like *"What can I see in Tokyo tonight?"* or *"Show me nebulas visible right now"*. The AI understands temporal contexts (tonight, tomorrow morning) and geographical locations.
* **🔭 Precision Astronomy:**
    * **Real-time Altitude Calculation:** Exact computation of object elevation using spherical trigonometry.
    * **Altitude filtering** (targets must be above the horizon).
    * **Sun position logic** (ensures targets are not suggested during daylight).
* **🗺️ Interactive Starmap (VirtualSky):**
    * 3D projection of recommended targets.
    * "Identity Card" overlay upon clicking a star (Info, Magnitude, Description).
    * Responsive design with an animated Sidebar and toggleable map.
* **📚 Enriched Database:**
    * Full **Messier** (M1-M110) and **Caldwell** (NGC/IC) catalogs.
    * Cross-referenced data via **PyOngc** (OpenNGC) for coordinates (RA/DEC), magnitude, and object type.
    * Descriptions and images fetched via the **Wikipedia API**.
    * Automatic translation of constellation names.

---

## 🏗️ Technical Architecture

The project relies on a three-agent architecture:
1.  **The Orchestrator:** Analyzes the user request (Location, Date, Intent).
2.  **The Astronomer (Text-to-SQL):** Generates SQL queries to filter the celestial database based on physical constraints (LST +/- 6h).
3.  **The Popularizer:** Formulates a natural, educational response for the user.

### Tech Stack
* **Backend:** Python, FastAPI.
* **AI:** Google Gemini 1.5 Flash (via Google AI Studio).
* **Astronomy:** Astropy, PyOngc.
* **Frontend:** HTML5, CSS3 (Glassmorphism), jQuery, VirtualSky.js.

---

## 🛠️ Detailed Implementation Status

### 🗄️ Database Engineering
* **Base Structure:** `Celestial` table populated with fields: `name`, `type`, `constellation`, `ra`, `dec`, `magnitude`, `url`.
* **Data Sources & Filling:**
    * **Messier (M1-M110) & Caldwell:** Implemented JSON mapping for Caldwell objects (CX -> IC/NGC Y) to fetch accurate data via **OpenNGC**.
    * **PyOngc Integration:** Used to retrieve precise RA/Dec, Magnitude, and Type data.
    * **Constellations:** Manual dictionary created for French/English translation.
    * **Wikipedia API:** Automated fetching of images and description URLs.
* **Testing:** Database integrity tests completed.

### 🔭 Astropy & Physics Logic
* **LST & Hour Angle:** Calculates Local Sidereal Time (LST) based on user longitude to derive the Hour Angle (HA).
* **Precise Altitude Calculation:** Uses spherical trigonometry to compute the exact elevation of objects based on the observer's latitude and the object's Equatorial coordinates.
* **Visibility:**
    * **Altitude:** Returns objects only if they are significantly above the horizon (positive altitude).
    * **Sun:** Integrated Sun position checks (Solar Altitude) to prevent daytime suggestions.
* **Dynamic Geolocation:** By default, uses browser geolocation. Can be overridden via prompt (e.g., "in Tokyo"). Handles relative time ("tonight", "this morning").

---

## 🚀 Installation & Setup

### 1. Prerequisites
* Python 3.9+
* A Google AI Studio API Key (Gemini).

### 2. Clone the repository and install dependencies
```bash
git clone [https://github.com/your-username/astrochat.git](https://github.com/your-username/astrochat.git)
cd astrochat
pip install -r requirements.txt