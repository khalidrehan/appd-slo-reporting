import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from datetime import datetime, timedelta
import urllib3
import json
import time
import matplotlib.pyplot as plt
import io
import base64
import os

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURATION SECTION ---

# AppDynamics Connection
CONTROLLER_URL = "https://your-controller.example.com/controller" # REPLACE THIS
ACCOUNT_NAME = "customer1" # Replace if different
CLIENT_NAME = "api_client_user" # Replace with your API Client Name

# SECURITY BEST PRACTICE: 
# Load sensitive secrets from Environment Variables, never hardcode them in public repos.
CLIENT_SECRET = os.getenv("APPD_CLIENT_SECRET", "YOUR_CLIENT_SECRET_HERE") 

# Reporting Configuration
DAYS_TO_REPORT = 7 # Used for the "Last Week" calculation

# SLO Configuration
SLO_AVAILABILITY_TARGET = 99.0  
SLO_LATENCY_TARGET = 1000       

# Time-Based Availability Config (Tier mapping)
# Wildcard '*' is used to match all tiers in the application
TIME_BASED_CONFIG = {
    "EST":      {"tier": "*", "threshold": 2},
    "IDM":      {"tier": "*", "threshold": 2},
    "DON":      {"tier": "*", "threshold": 2},
    "COM":      {"tier": "*", "threshold": 2},
    "Camunda":  {"tier": "*", "threshold": 1},
    "Keycloak": {"tier": "*", "threshold": 1},
}
TARGET_APPS = list(TIME_BASED_CONFIG.keys())

# Email Settings
SMTP_SERVER = "smtp.office365.com"
SMTP_PORT = 587
SMTP_USER = os.getenv("SMTP_USER", "alerts@example.com")
SMTP_PASS = os.getenv("SMTP_PASS", "YOUR_SMTP_PASSWORD")
EMAIL_TO = "admin@example.com" # Can be a comma-separated string for multiple recipients
EMAIL_SUBJECT = f"AppD SLO Report (Daily & Weekly) - {datetime.now().strftime('%Y-%m-%d')}"

# -----------------------------

def get_token():
    url = f"{CONTROLLER_URL}/api/oauth/access_token"
    data = {'grant_type': 'client_credentials', 'client_id': f"{CLIENT_NAME}@{ACCOUNT_NAME}", 'client_secret': CLIENT_SECRET}
    try:
        r = requests.post(url, data=data, verify=False)
        r.raise_for_status()
        return r.json()['access_token']
    except Exception as e:
        print(f"[!] Auth Failed: {e}")
        return None

def fetch_metric_data(app, metric_path, token, start_ms, end_ms, rollup=True):
    """Fetch metric data for a specific time window."""
    url = f"{CONTROLLER_URL}/rest/applications/{app}/metric-data"
    params = {
        'metric-path': metric_path,
        'time-range-type': 'BETWEEN_TIMES',
        'start-time': start_ms,
        'end-time': end_ms,
        'output': 'JSON',
        'rollup': 'true' if rollup else 'false'
    }
    headers = {'Authorization': f'Bearer {token}'}
    try:
        r = requests.get(url, params=params, headers=headers, verify=False)
        if r.status_code == 200:
            return r.json()
    except: pass
    return []

def get_metric_sum(app, metric_path, token, start_ms, end_ms):
    data = fetch_metric_data(app, metric_path, token, start_ms, end_ms, rollup=True)
    if data and data[0].get('metricValues'):
        values = data[0]['metricValues']
        total_sum = sum(v.get('sum', 0) for v in values)
        return total_sum
    return 0

def get_metric_avg(app, metric_path, token, start_ms, end_ms):
    data = fetch_metric_data(app, metric_path, token, start_ms, end_ms, rollup=True)
    if data and data[0].get('metricValues'):
        values = [v.get('value', 0) for v in data[0]['metricValues']]
        if values:
            return int(sum(values) / len(values))
    return 0

def get_detailed_tier_availability(app, tier_pattern, threshold, token, start_ms, end_ms, duration_days=1):
    metric_path = f"Application Infrastructure Performance|{tier_pattern}|Agent|App|Availability"
    use_rollup = duration_days > 1
    
    # This returns a list of metrics (one per Tier found matching the pattern)
    data = fetch_metric_data(app, metric_path, token, start_ms, end_ms, rollup=use_rollup)
    
    if not data:
        return 0, 0, "No Data"

    total_nodes_all_tiers = 0
    tier_count = len(data)
    failed_tiers = 0
    
    # Check each tier individually against the threshold
    for tier_metric in data:
        if not tier_metric.get('metricValues'):
            # No data for this specific tier in this time range
            continue
            
        values = tier_metric['metricValues']
        
        if use_rollup:
            # Average node count over the period
            vals = [v.get('value', 0) for v in values]
            avg_val = sum(vals) / len(vals) if vals else 0
            node_val = avg_val # Keep float for sum, round later
        else:
            # Absolute minimum (Daily view)
            vals = [v.get('value', 0) for v in values]
            node_val = min(vals) if vals else 0
            
        total_nodes_all_tiers += node_val
        
        # Check threshold for this specific tier
        # We use a slightly lenient check for averages (e.g., 1.9 vs 2.0)
        if round(node_val, 1) < threshold:
            failed_tiers += 1

    final_status = "FAIL" if failed_tiers > 0 else "PASS"
    
    # Return integer of total nodes for clean display
    return int(round(total_nodes_all_tiers)), tier_count, final_status

def analyze_period(start_ms, end_ms, label, token, duration_days=1):
    """Analyzes a specific time window."""
    
    print(f"[*] Analyzing {label}...")
    
    results = []
    
    for app in TARGET_APPS:
        # Fetch Metrics
        total_calls = get_metric_sum(app, "Overall Application Performance|Calls per Minute", token, start_ms, end_ms)
        total_errors = get_metric_sum(app, "Overall Application Performance|Errors per Minute", token, start_ms, end_ms)
        avg_latency = get_metric_avg(app, "Overall Application Performance|Average Response Time (ms)", token, start_ms, end_ms)
        
        # Calculations
        if total_calls > 0:
            error_rate = (total_errors / total_calls) * 100
            availability = 100.0 - error_rate
            total_minutes = (end_ms - start_ms) / 1000 / 60
            avg_calls_per_min = total_calls / total_minutes if total_minutes > 0 else 0
        else:
            error_rate = 0.0
            availability = 100.0 if total_errors == 0 else 0.0
            avg_calls_per_min = 0.0

        # Error Budget
        allowed_failure_rate = (100.0 - SLO_AVAILABILITY_TARGET) / 100.0
        total_budget_errors = int(total_calls * allowed_failure_rate)
        budget_remaining = total_budget_errors - total_errors
        budget_pct = (budget_remaining / total_budget_errors) * 100 if total_budget_errors > 0 else 100.0
        
        # Time-Based Avail (New Logic)
        config = TIME_BASED_CONFIG[app]
        total_nodes, tier_count, time_status = get_detailed_tier_availability(
            app, config['tier'], config['threshold'], token, start_ms, end_ms, duration_days
        )
        
        # CSS Logic
        avail_css = "pass" if availability >= SLO_AVAILABILITY_TARGET else "fail"
        lat_css = "pass" if avg_latency <= SLO_LATENCY_TARGET else "fail"
        err_css = "fail" if error_rate > (100.0 - SLO_AVAILABILITY_TARGET) else "pass"
        time_css = "pass" if time_status == "PASS" else "fail"
        
        if budget_remaining < 0: budget_css = "fail"
        elif budget_pct < 20: budget_css = "warn"
        else: budget_css = "pass"

        results.append({
            "name": app,
            "calls": total_calls,
            "avg_calls_min": round(avg_calls_per_min, 1),
            "error_pct": round(error_rate, 3),
            "availability": round(availability, 3),
            "latency": avg_latency,
            "budget_rem": budget_remaining,
            "budget_tot": total_budget_errors,
            "budget_pct": round(budget_pct, 1),
            "min_agents": total_nodes, # Now an integer sum of all tiers
            "tier_count": tier_count,
            "threshold": config['threshold'],
            "time_status": time_status,
            
            # Styles
            "avail_css": avail_css,
            "lat_css": lat_css,
            "err_css": err_css,
            "budget_css": budget_css,
            "time_css": time_css
        })
        
    return {"date": label, "data": results}

def generate_graphs(trend_data):
    """Generates base64 encoded PNG graphs from trend data."""
    print("[*] Generating Graphs...")
    
    # Prepare data structure for plotting
    dates = [d['date'] for d in trend_data]
    apps = TARGET_APPS
    
    # Metric extractors
    metrics = {
        "Error Budget Remaining": lambda x: x['budget_rem'],
        "Request-Based Availability (%)": lambda x: x['availability'],
        "Total Node Count": lambda x: x['min_agents']
    }
    
    graph_images = {}
    
    # Color map for consistency
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2']
    
    for title, extractor in metrics.items():
        plt.figure(figsize=(10, 5))
        
        for i, app in enumerate(apps):
            # Extract y-values for this app across all dates
            y_values = []
            for day_data in trend_data:
                # Find the app data in this day's results
                app_row = next((row for row in day_data['data'] if row['name'] == app), None)
                y_values.append(extractor(app_row) if app_row else 0)
            
            plt.plot(dates, y_values, marker='o', label=app, color=colors[i % len(colors)], linewidth=2)
        
        plt.title(f"{title} - Last 7 Days")
        plt.xlabel("Date")
        plt.ylabel(title.replace(" (%)", ""))
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.legend()
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # Save to buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        graph_images[title] = img_str
        plt.close()
        
    return graph_images

def send_email(daily_data, weekly_data, graph_images):
    print("[*] Generating HTML Report...")
    
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; color: #333; }}
            h2 {{ color: #2c3e50; padding-bottom: 5px; }}
            .summary {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px; font-size: 0.9em; }}
            
            table {{ border-collapse: collapse; width: 100%; margin-bottom: 25px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
            
            th {{ background-color: #2c3e50; color: white; padding: 10px; text-align: center; font-size: 0.9em; }}
            
            td {{ border: 1px solid #ddd; padding: 8px; text-align: center; font-size: 0.9em; }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
            
            .pass {{ color: #27ae60; font-weight: bold; }}
            .warn {{ color: #d35400; font-weight: bold; }}
            .fail {{ color: #c0392b; font-weight: bold; }}
            
            .date-header {{ font-size: 1.1em; font-weight: bold; margin-top: 20px; margin-bottom: 5px; color: #2980b9; }}
            .graph-container {{ margin-top: 30px; text-align: center; }}
            .graph-container img {{ max-width: 100%; border: 1px solid #ddd; margin-bottom: 20px; }}
        </style>
    </head>
    <body>
        <h2>📊 AppDynamics SLO Report</h2>
        <div class="summary">
            <strong>Scope:</strong> Last 24 Hours & Last {DAYS_TO_REPORT} Days<br>
            <strong>SLO Targets:</strong> {SLO_AVAILABILITY_TARGET}% Avail | &lt;{SLO_LATENCY_TARGET}ms Latency
        </div>
    """
    
    # Helper to render a table
    def render_table(report_data):
        table_html = f"""
        <div class="date-header">{report_data['date']}</div>
        <table>
            <tr>
                <th style="text-align:left;">App</th>
                <th>Calls/Min</th>
                <th>Error %</th>
                <th>Req Avail %</th>
                <th>Latency</th>
                <th>Error Budget</th>
                <th>Nodes (Tot / Tiers)</th>
                <th>Ref Thresh</th>
                <th>Status</th>
            </tr>
        """
        for row in report_data['data']:
            sign = "+" if row['budget_rem'] >= 0 else ""
            budget_str = f"{sign}{row['budget_rem']:,} ({row['budget_pct']}%)"
            
            # Formatted Node string: "6 (Tiers: 3)"
            nodes_str = f"{row['min_agents']} (Tiers: {row['tier_count']})"
            thresh_str = f"{row['threshold']}"
            
            table_html += f"""
            <tr>
                <td style="text-align:left; font-weight:bold;">{row['name']}</td>
                <td>{row['avg_calls_min']:,}</td>
                <td class="{row['err_css']}">{row['error_pct']}%</td>
                <td class="{row['avail_css']}">{row['availability']}%</td>
                <td class="{row['lat_css']}">{row['latency']} ms</td>
                <td class="{row['budget_css']}" style="font-size:0.85em;">{budget_str}</td>
                <td class="{row['time_css']}">{nodes_str}</td>
                <td style="font-size:0.85em; color:#777;">{thresh_str}</td>
                <td class="{row['time_css']}">{row['time_status']}</td>
            </tr>
            """
        table_html += "</table>"
        return table_html

    # Append Tables
    html_content += render_table(daily_data)
    html_content += render_table(weekly_data)
    
    # Append Graphs
    html_content += "<h2>📈 Weekly Trends</h2>"
    
    graph_titles = ["Error Budget Remaining", "Request-Based Availability (%)", "Total Node Count"]
    for title in graph_titles:
        if title in graph_images:
            html_content += f"""
            <div class="graph-container">
                <h3>{title}</h3>
                <img src="data:image/png;base64,{graph_images[title]}" alt="{title}">
            </div>
            """

    html_content += """
        <p style="font-size: 12px; color: #999;">Generated by AppD SLO Reporter.</p>
    </body>
    </html>
    """

    msg = MIMEMultipart()
    msg['From'] = SMTP_USER
    msg['To'] = EMAIL_TO
    msg['Subject'] = EMAIL_SUBJECT
    msg.attach(MIMEText(html_content, 'html'))

    try:
        print(f"[*] Connecting to SMTP ({SMTP_SERVER})...")
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        print(f"[+] Report sent successfully to {EMAIL_TO}")
    except Exception as e:
        print(f"[!] SMTP Error: {e}")

if __name__ == "__main__":
    token = get_token()
    if token:
        now = datetime.now()
        ms_end = int(now.timestamp() * 1000)
        
        # 1. Analyze Last 24 Hours
        start_24h = now - timedelta(days=1)
        ms_start_24h = int(start_24h.timestamp() * 1000)
        daily_report = analyze_period(ms_start_24h, ms_end, "Last 24 Hours", token, duration_days=1)
        
        # 2. Analyze Last 7 Days (Aggregate Table)
        start_7d = now - timedelta(days=DAYS_TO_REPORT)
        ms_start_7d = int(start_7d.timestamp() * 1000)
        weekly_report = analyze_period(ms_start_7d, ms_end, f"Last {DAYS_TO_REPORT} Days (Weekly)", token, duration_days=DAYS_TO_REPORT)
        
        # 3. Generate Trend Data for Graphs (Daily points for last 7 days)
        trend_data = []
        for i in range(DAYS_TO_REPORT):
            # Calculate day window (going back)
            # We want day 0 to be "Today/Yesterday" and day 6 to be 7 days ago
            # Actually easier to go chronological
            day_offset = DAYS_TO_REPORT - 1 - i
            d_end = now - timedelta(days=day_offset)
            d_start = d_end - timedelta(days=1)
            
            ms_d_start = int(d_start.timestamp() * 1000)
            ms_d_end = int(d_end.timestamp() * 1000)
            date_label = d_end.strftime('%m-%d')
            
            day_stats = analyze_period(ms_d_start, ms_d_end, date_label, token, duration_days=1)
            trend_data.append(day_stats)

        # 4. Generate Graphs
        graph_images = generate_graphs(trend_data)
        
        # 5. Send
        send_email(daily_report, weekly_report, graph_images)