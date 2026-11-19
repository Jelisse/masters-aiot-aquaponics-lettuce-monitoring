import time
from flask import Flask, render_template, jsonify
from threading import Thread
import schedule
import os
from datetime import datetime
from collections import defaultdict

# Project Modules
import plant_monitor
import database_manager

# --- Flask App Setup ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'change-me')
app.config['JSON_SORT_KEYS'] = False

# Global state to hold the latest measurement data for web display
# Structure: {'Group Name': [{'name': 'Lettuce', 'height_cm': 7.4, ...}, 'base64_image': '...']}
LATEST_METRICS = {}
LATEST_DB_SAVE_TIME = "N/A"

def run_vision_and_measurement(group_name, image_path):
    """Runs the segmentation model and updates the global metrics."""
    print(f"-> Starting measurement for {group_name}...")
    
    # 1. Run the segmentation and measurement logic - NOW PASSING GROUP_NAME
    plant_data = plant_monitor.measure_plant_dimensions(group_name, image_path)
    
    # 2. Update the global state for the web page
    if plant_data:
        # Separate image data (which is the same for all plants in the image) 
        # from the individual plant metrics
        base64_img = plant_data[0].pop('base64_image', None) 
        
        LATEST_METRICS[group_name] = {
            'plants': plant_data,
            'image': base64_img
        }
    else:
        print(f"No plants detected in {group_name} or measurement failed.")
        LATEST_METRICS[group_name] = {
            'plants': [],
            # Use the dummy placeholder if actual image failed
            'image': 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII='
        }

def scheduled_job():
    """Runs the full process for all groups and saves to DB every 3 hours."""
    global LATEST_DB_SAVE_TIME
    
    print("\n--- Scheduled Job Triggered ---")
    
    # 1. Measure all groups
    all_group_data = defaultdict(list)
    for group_name, image_path in plant_monitor.SIMULATED_CAMERA_FEEDS.items():
        # Run vision and update latest metrics for display
        # NOTE: This call updates LATEST_METRICS globally
        run_vision_and_measurement(group_name, image_path)
        
        # Extract only the necessary metrics for the database (no image data)
        if group_name in LATEST_METRICS and LATEST_METRICS[group_name]['plants']:
            for plant in LATEST_METRICS[group_name]['plants']:
                all_group_data[group_name].append({
                    'name': plant['name'],
                    'height_cm': plant['height_cm'],
                    'width_cm': plant['width_cm'],
                    'area_cm2': plant.get('area_cm2'),
                    'confidence': plant['confidence']
                })
    
    # 2. Save data to MsSQL
    total_records = 0
    for group_name, plant_list in all_group_data.items():
        total_records += database_manager.save_detection_data(group_name, plant_list)
        
    LATEST_DB_SAVE_TIME = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"--- Job Complete. {total_records} total records inserted. Next run in 3 hours. ---")


# --- Scheduler Setup ---
def run_scheduler():
    """Sets up the scheduler thread."""
    # First, run the job immediately to populate the data for the first page load
    print("Running initial measurement to populate dashboard...")
    
    # Run the initial DB save to log the starting data
    scheduled_job() # scheduled_job runs the measurement and saves to DB immediately

    # Then, schedule the full process (measurement + database save) every 3 hours
    schedule.every(3).hours.do(scheduled_job)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

# --- Flask Routes ---

@app.route('/')
def index():
    """Renders the main dashboard page."""
    groups = plant_monitor.SIMULATED_CAMERA_FEEDS.keys()
    return render_template('index.html', 
                           groups=groups, 
                           latest_save_time=LATEST_DB_SAVE_TIME,
                           current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

@app.route('/api/metrics')
def api_metrics():
    """API endpoint to fetch the latest metrics for the dashboard."""
    # Add the latest save time to the response for the frontend to update
    data_to_send = LATEST_METRICS.copy()
    data_to_send['latest_save_time'] = LATEST_DB_SAVE_TIME
    return jsonify(data_to_send)

@app.before_request
def initialize_application():
    """Runs setup tasks before the first request."""
    if not hasattr(app, 'initialized'):
        # Initialize the database and ensure the table exists
        database_manager.initialize_db()
        
        # Start the background scheduler thread
        thread = Thread(target=run_scheduler)
        thread.daemon = True
        thread.start()
        
        app.initialized = True
        print("Application startup complete.")


if __name__ == '__main__':
    # Flask will automatically run initialize_application before the first request.
    # We run the application on a standard port.
    app.run(debug=True, use_reloader=False, threaded=True)