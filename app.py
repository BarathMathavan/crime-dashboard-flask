import os
import csv
import io
import re
import requests
import json
from flask import Flask, jsonify, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired
from collections import Counter
import Levenshtein
from dateutil.parser import parse as parse_date

# --- CONFIGURATION & FLASK APP ---
# Vercel requires the Flask app instance to be named 'app'
app = Flask(__name__)

# Read secrets from Environment Variables set in Vercel
# Default values are provided for easy local development
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-dev-secret-key-change-me')
GOOGLE_SHEET_URL = os.environ.get('GOOGLE_SHEET_URL')
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'password123')
GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY')

# --- LOGIN MANAGEMENT SETUP ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
users = {ADMIN_USERNAME: {'password': ADMIN_PASSWORD}}

class User(UserMixin):
    def __init__(self, id): self.id = id
@login_manager.user_loader
def load_user(user_id): return User(user_id) if user_id in users else None
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')

# --- IN-MEMORY CACHE (for "warm" serverless functions) ---
crime_data_cache, filter_options_cache, analytics_data_cache = [], {}, {}
data_loaded = False # Flag to check if data has been fetched in this instance

# --- HIERARCHICAL MAPPING & GROUPING CONFIGURATION ---
PS_TO_SUBDIVISION_MAP = {
    "AWPS Thoothukudi": "Thoothukudi Town", "Muthiahpuram": "Thoothukudi Town", "Thazhamuthunagar": "Thoothukudi Town", "Thermalnagar": "Thoothukudi Town", "Thoothukudi Central": "Thoothukudi Town", "Thoothukudi North": "Thoothukudi Town", "Thoothukudi South": "Thoothukudi Town",
    "AWPS Pudukotai Thoothukudi": "Thoothukudi Rural", "Murappanadu": "Thoothukudi Rural", "Pudukottai Thoothukudi": "Thoothukudi Rural", "Puthiamputhur": "Thoothukudi Rural", "SIPCOT Thoothukudi": "Thoothukudi Rural", "Thattparai": "Thoothukudi Rural",
    "AWPS Kadambur": "Maniyachi", "Kadambur": "Maniyachi", "Maniyachi": "Maniyachi", "Naraikinaru": "Maniyachi", "Ottapidaram": "Maniyachi", "Pasuvanthanai": "Maniyachi", "Puliyampatti": "Maniyachi",
    "AWPS Kovilapatti": "Kovilpatti", "Kalugumalai": "Kovilpatti", "Kayathar": "Kovilpatti", "Koppampatti": "Kovilpatti", "Kovilpatti East": "Kovilpatti", "Kovilpatti West": "Kovilpatti", "Nalatinpudur": "Kovilpatti",
    "AWPS Vilathikulam": "Vilathikulam", "Eppodumvendran": "Vilathikulam", "Ettayapuram": "Vilathikulam", "Kadalkudi": "Vilathikulam", "Kulathur": "Vilathikulam", "Masarpatti": "Vilathikulam", "Pudur": "Vilathikulam", "Sankaralingapuram": "Vilathikulam", "Soorankudi": "Vilathikulam", "Tharuvaikulam": "Vilathikulam", "Vilathikulam": "Vilathikulam",
    "Alwarthirunagari": "Srivaikundam", "AWPS Srivaikundam": "Srivaikundam", "Eral": "Srivaikundam", "Kurumbur": "Srivaikundam", "Sawyerpuram": "Srivaikundam", "Sedunganallur": "Srivaikundam", "Serakulam": "Srivaikundam", "Srivaikundam": "Srivaikundam",
    "Arumuganeri": "Tiruchendur", "Authoor": "Tiruchendur", "AWPS Tiruchendur": "Tiruchendur", "Kulasekarapatinam": "Tiruchendur", "Tiruchendur Taluk": "Tiruchendur", "Tiruchendur Temple": "Tiruchendur",
    "AWPS Sathankulam": "Sathankulam", "Meiganapuram": "Sathankulam", "Nazareth": "Sathankulam", "Sathankulam": "Sathankulam", "Thattarmadam": "Sathankulam"
}
MASTER_STATION_LIST = list(PS_TO_SUBDIVISION_MAP.keys())
POLICE_STATION_MAP = { "tut/north": "Thoothukudi North", "tut/south": "Thoothukudi South", "west/kvp": "Kovilpatti West", "east/kvp": "Kovilpatti East", "taluk/tdr": "Tiruchendur Taluk", "temple/tdr": "Tiruchendur Temple", "awps/tut": "AWPS Thoothukudi", "awps/vkm": "AWPS Vilathikulam", "awps/tdr": "AWPS Tiruchendur", "awps/skm": "AWPS Sathankulam", "awps/kvp": "AWPS Kovilapatti", "awps/svm": "AWPS Srivaikundam", "awps/kadambur": "AWPS Kadambur", "sipcot": "SIPCOT Thoothukudi" }
EVENT_TYPE_GROUPS = { "Fighting / Threatening": ["Fighting", "Fight", "Threatening", "Drunken Brawl"], "Family Dispute": ["Family Dispute", "Family Fighting"], "Road Accident": ["Road Accident"], "Fire Accident": ["Fire Accident", "Fire"], "Woman & Child Related": ["Woman and child Related", "Woman Related", "Child Related"], "Theft / Robbery": ["Theft", "Robbery"], "Civil Dispute": ["Civil Dispute", "Encroachment"], "Complaint Against Police": ["Complaint Against Police"], "Prohibition Related": ["Prohibition"], "Others": ["Others", "Disturbance", "Cheating", "Missing Person", "Cyber Crime", "Rescue Works"] }

# --- DATA CLEANING & STANDARDIZATION FUNCTIONS ---
def clean_event_type(messy_type):
    if not messy_type: return "Others"
    messy_type_lower = messy_type.lower()
    for clean_category, keywords in EVENT_TYPE_GROUPS.items():
        for keyword in keywords:
            if keyword.lower() in messy_type_lower: return clean_category
    return "Others"

def find_best_match_levenshtein(key, master_list):
    min_distance, best_match = float('inf'), None
    for master_item in master_list:
        distance = Levenshtein.distance(key, master_item.lower())
        if distance < min_distance: min_distance, best_match = distance, master_item
    if best_match and (1 - (min_distance / max(len(key), len(best_match)))) * 100 >= 80: return best_match
    return None

def standardize_police_station(messy_station):
    if not messy_station: return "Unknown"
    key = messy_station.lower().replace('ps', '').replace('.', '').strip()
    if key in POLICE_STATION_MAP: return POLICE_STATION_MAP[key]
    best_match = find_best_match_levenshtein(key, MASTER_STATION_LIST)
    return best_match if best_match else key.title()

def get_lat_lon(row):
    lat_key, lon_key = next((k for k in row.keys() if 'lat' in k.lower()), None), next((k for k in row.keys() if 'lon' in k.lower() or 'long' in k.lower()), None)
    lat_str, lon_str = (row.get(lat_key), row.get(lon_key)) if lat_key and lon_key else (None, None)
    if not (lat_str and lon_str):
        combined_key = next((k for k in row.keys() if any(w in k.lower() for w in ['location', 'coords'])), None)
        if combined_key and row.get(combined_key) and ',' in row.get(combined_key):
            parts = row.get(combined_key).split(',')
            if len(parts) == 2: lat_str, lon_str = parts[0].strip(), parts[1].strip()
    if not lat_str or not lon_str: return None, None
    try:
        lat, lon = float(lat_str), float(lon_str)
        if 8.0 < lat < 9.5 and 77.5 < lon < 78.5: return lat, lon
        elif 8.0 < lon < 9.5 and 77.5 < lat < 78.5: return lon, lat
        return None, None
    except (ValueError, TypeError): return None, None

def standardize_date(date_string):
    if not date_string: return None
    try: return parse_date(date_string, dayfirst=True).strftime('%Y-%m-%d')
    except (ValueError, TypeError): return None

# --- MAIN DATA PROCESSING FUNCTION ---
def fetch_and_process_data():
    global crime_data_cache, filter_options_cache, analytics_data_cache, data_loaded
    if not GOOGLE_SHEET_URL: print("ERROR: GOOGLE_SHEET_URL environment variable is not set."); return
    print("Attempting to refresh data from Google Sheet...")
    try:
        response = requests.get(GOOGLE_SHEET_URL); response.raise_for_status()
        clean_text = response.text.replace('\x00', ''); csv_file = io.StringIO(clean_text)
        next(csv_file, None); reader = csv.DictReader(csv_file)
        processed_data, final_event_types, final_subdivisions = [], set(), set()
        for row in reader:
            lat, lon = get_lat_lon(row); standard_date = standardize_date(row.get('Date'))
            if lat is None or lon is None or standard_date is None: continue
            cleaned_station = standardize_police_station(row.get('Police Station'))
            subdivision = PS_TO_SUBDIVISION_MAP.get(cleaned_station, "Unknown")
            if subdivision == "Unknown": continue
            cleaned_event_type = clean_event_type(row.get('Event type ', row.get('Event Type')))
            category = 'Rural' if not any(k in subdivision for k in ['Town', 'Thoothukudi Town']) else 'Town'
            clean_row = {'Latitude': lat, 'Longitude': lon, 'Event Type': cleaned_event_type, 'Police Station': cleaned_station, 'Subdivision': subdivision, 'Category': category, 'Date': standard_date, 'Complaint': row.get('Complaint Name & Address& Phone No')}
            processed_data.append(clean_row)
            final_event_types.add(cleaned_event_type); final_subdivisions.add(subdivision)
        
        crime_data_cache = processed_data
        filter_options_cache = { "event_types": sorted(list(final_event_types)), "subdivisions": sorted(list(final_subdivisions)) }
        station_counts = Counter(item['Police Station'] for item in processed_data)
        analytics_data_cache = { "total_cases": len(processed_data), "top_stations": station_counts.most_common(5) } if processed_data else {"total_cases": 0, "top_stations": []}
        data_loaded = True
        print(f"Data refreshed successfully. Loaded {len(crime_data_cache)} records.")
    except Exception as e:
        print(f"An error occurred during data processing: {e}")

def ensure_data_loaded():
    global data_loaded
    if not data_loaded: fetch_and_process_data()

# --- FLASK ROUTES ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        username, password = form.username.data, form.password.data
        if username in users and users[username]['password'] == password:
            login_user(User(username)); return redirect(url_for('dashboard'))
        else: flash('Invalid username or password')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user(); return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    return render_template('index.html', GOOGLE_MAPS_API_KEY=GOOGLE_MAPS_API_KEY)

@app.route('/api/data')
@login_required
def get_crime_data(): ensure_data_loaded(); return jsonify(crime_data_cache)

@app.route('/api/filters')
@login_required
def get_filter_options(): ensure_data_loaded(); return jsonify(filter_options_cache)

@app.route('/api/analytics')
@login_required
def get_analytics_data(): ensure_data_loaded(); return jsonify(analytics_data_cache)

# This block is useful for local testing (`python api/index.py`) but is ignored by Vercel
if __name__ == '__main__':
    # This will run the fetch function once on startup for local dev
    fetch_and_process_data()
    app.run(debug=True, port=5000)