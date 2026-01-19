📊 AppDynamics SLO & Availability Reporter

An automated Python tool that generates and emails Service Level Objective (SLO) and Availability reports for applications monitored by Cisco AppDynamics.

This script connects to the AppDynamics Controller API, calculates key SLIs (Availability, Latency, Error Budget, Node Health), and delivers a consolidated HTML report with trend graphs directly to your inbox.

🚀 Key Features

Automated Reporting: No need to log in to the Controller; get critical metrics via email.

Dual-View Analysis:

Tactical (Last 24 Hours): Detailed table for immediate daily health checks.

Strategic (Last 7 Days): Aggregated table showing weekly trends.

SLO Tracking:

Availability: Monitors if request success rates meet the 99.0% target.

Latency: Checks if average response time is under 1000ms.

Error Budget: Calculates the "burn rate" of allowed errors.

Infrastructure Health: Monitors if the required minimum number of active nodes/agents are online for critical tiers.

Visual Trends: Includes embedded graphs for Error Budget, Availability, and Node Counts over the last week.

🛠️ Prerequisites

Python 3.x

AppDynamics Controller with API Access (Client ID & Secret).

SMTP Server access for sending emails.

Dependencies

pip install -r requirements.txt


(Note: If requirements.txt is missing, you need: requests, matplotlib)

📥 Installation

Clone this repository:

git clone [https://github.com/khalidrehan/appd-slo-reporting.git](https://github.com/khalidrehan/appd-slo-reporting.git)
cd appd-slo-reporting


Install required Python libraries:

pip install -r requirements.txt


⚙️ Configuration

Open appd_slo_reporter.py and configure the following variables in the CONFIGURATION SECTION:

AppDynamics Connection:

CONTROLLER_URL: Your Controller URL (e.g., https://your-controller.com/controller).

ACCOUNT_NAME: Your AppDynamics Account Name.

CLIENT_NAME: Your API Client Name.

CLIENT_SECRET: Use Environment Variables (Recommended) or update securely.

Reporting Targets:

TIME_BASED_CONFIG: Dictionary mapping App Names to their specific Tier Name (or * wildcard) and the minimum required node count.

Email Settings:

SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASS.

EMAIL_TO: Comma-separated string of recipient emails.

🏃 Usage

Run the script manually:

python3 appd_slo_reporter.py


Automation (Cron)

To run this report daily at 8:00 AM:

Open crontab:

crontab -e


Add the line:

0 8 * * * /usr/bin/python3 /path/to/appd-slo-reporting/appd_slo_reporter.py


🔐 Security Note

Never commit your CLIENT_SECRET or SMTP passwords directly to a public repository. Use environment variables (os.getenv) or a secrets manager.