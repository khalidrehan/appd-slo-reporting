# AppDynamics SLO & Availability Reporter

A Python-based observability tool that bridges the gap between raw AppDynamics metrics and actionable business intelligence.

This tool automatically connects to the AppDynamics Controller API to calculate key Service Level Indicators (Availability, Latency, Error Budgets), assesses Infrastructure Health (Node counts), and delivers a consolidated, visually rich HTML report directly to your inbox.

## 🚀 Key Features

* **Automated Reporting:** Eliminates the need to log in to the Controller by delivering critical health metrics via email daily.
* **Dual-View Analysis:**
    * **Tactical:** Detailed breakdown of the last 24 hours for immediate troubleshooting.
    * **Strategic:** Aggregated 7-day view to identify long-term trends and stability issues.
* **SLO Tracking:**
    * **Availability:** Validates if request success rates meet the 99.0% target.
    * **Latency:** Checks if average response times stay under the 1000ms threshold.
    * **Error Budget:** Calculates the "burn rate" of allowed errors to prevent SLA violations.
* **Infrastructure Health:** Monitors specific application tiers to ensure the required minimum number of active nodes are online.
* **Visual Trends:** Generates and embeds PNG charts using `matplotlib` to visualize Error Budget, Availability, and Node Counts over time.

## 🛠️ Prerequisites

* Python 3.6+
* AppDynamics Controller Access (API Client ID & Secret)
* SMTP Server Access (Office365 or similar)

### Dependencies

```bash
pip install requests matplotlib
