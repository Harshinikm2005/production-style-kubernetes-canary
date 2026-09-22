import urllib.request
import urllib.parse
import json
import subprocess
import sys


# ============================================================
# CONFIGURATION
# ============================================================

PROMETHEUS_URL = "http://localhost:9090"

NAMESPACE = "canary-demo"
VIRTUAL_SERVICE = "canary-routing"

ERROR_THRESHOLD = 5.0

# Minimum number of canary requests required
MIN_CANARY_REQUESTS = 5

# Prometheus measurement window
PROMETHEUS_WINDOW = "2m"


# ============================================================
# PROMETHEUS QUERY
# ============================================================

def query_prometheus(query):

    try:

        params = urllib.parse.urlencode({
            "query": query
        })

        url = f"{PROMETHEUS_URL}/api/v1/query?{params}"

        with urllib.request.urlopen(
            url,
            timeout=5
        ) as response:

            data = json.loads(
                response.read().decode()
            )

        if data["status"] != "success":
            print("ERROR: Prometheus query failed")
            return 0.0

        results = data["data"]["result"]

        if not results:
            return 0.0

        value = results[0]["value"][1]

        if value.lower() in [
            "nan",
            "+inf",
            "-inf",
            "inf"
        ]:
            return 0.0

        return float(value)

    except Exception as e:

        print(f"ERROR: Prometheus connection failed: {e}")

        return None


# ============================================================
# CANARY TOTAL REQUESTS
# ============================================================

def get_canary_total_requests():

    query = f"""
    sum(
        increase(
            istio_requests_total{{
                destination_version="canary"
            }}[{PROMETHEUS_WINDOW}]
        )
    )
    """

    return query_prometheus(query)


# ============================================================
# CANARY FAILED REQUESTS
# ============================================================

def get_canary_failed_requests():

    query = f"""
    sum(
        increase(
            istio_requests_total{{
                destination_version="canary",
                response_code=~"5.."
            }}[{PROMETHEUS_WINDOW}]
        )
    )
    """

    return query_prometheus(query)


# ============================================================
# AUTOMATIC ROLLBACK
# ============================================================

def rollback():

    print()
    print("==========================================")
    print("       AUTOMATIC ROLLBACK")
    print("==========================================")

    patch = (
        '[{"op":"replace",'
        '"path":"/spec/http/0/route/0/weight",'
        '"value":100},'
        '{"op":"replace",'
        '"path":"/spec/http/0/route/1/weight",'
        '"value":0}]'
    )

    try:

        result = subprocess.run(
            [
                "kubectl",
                "patch",
                "virtualservice",
                VIRTUAL_SERVICE,
                "-n",
                NAMESPACE,
                "--type=json",
                "-p",
                patch
            ],
            capture_output=True,
            text=True,
            check=True
        )

        print(result.stdout)

        print("------------------------------------------")
        print("Stable traffic : 100%")
        print("Canary traffic : 0%")
        print("------------------------------------------")
        print("ROLLBACK COMPLETED")
        print("==========================================")

    except subprocess.CalledProcessError as e:

        print("ROLLBACK FAILED")
        print(e.stderr)

        sys.exit(2)


# ============================================================
# CANARY ANALYSIS
# ============================================================

def analyze():

    print()
    print("==========================================")
    print("        CANARY HEALTH ANALYZER")
    print("==========================================")

    print(
        f"Error Threshold  : {ERROR_THRESHOLD:.2f}%"
    )

    print(
        f"Minimum Requests : {MIN_CANARY_REQUESTS}"
    )

    print(
        f"Metrics Window   : {PROMETHEUS_WINDOW}"
    )

    print("------------------------------------------")

    # --------------------------------------------------------
    # Get metrics
    # --------------------------------------------------------

    total_requests = get_canary_total_requests()

    failed_requests = get_canary_failed_requests()

    # --------------------------------------------------------
    # Prometheus unavailable
    # --------------------------------------------------------

    if total_requests is None or failed_requests is None:

        print()
        print("Decision : NO_DATA")
        print("Reason   : Prometheus metrics unavailable")
        print("Action   : STOP ROLLOUT")

        return 2

    # --------------------------------------------------------
    # Display metrics
    # --------------------------------------------------------

    print()
    print("Canary Metrics")
    print("------------------------------------------")

    print(
        f"Total Requests  : {total_requests:.0f}"
    )

    print(
        f"Failed Requests : {failed_requests:.0f}"
    )

    # --------------------------------------------------------
    # Not enough traffic
    # --------------------------------------------------------

    if total_requests < MIN_CANARY_REQUESTS:

        print()
        print("Decision : NO_DATA")

        print(
            f"Reason   : Only "
            f"{total_requests:.0f} canary requests"
        )

        print(
            f"Required : {MIN_CANARY_REQUESTS}"
        )

        print("Action   : STOP ROLLOUT")

        return 2

    # --------------------------------------------------------
    # Calculate error rate
    # --------------------------------------------------------

    error_rate = (
        failed_requests /
        total_requests
    ) * 100

    print(
        f"Error Rate      : {error_rate:.2f}%"
    )

    print("------------------------------------------")

    # ========================================================
    # FAILURE DETECTED
    # ========================================================

    if error_rate > ERROR_THRESHOLD:

        print()
        print("Decision : FAIL")

        print(
            f"Reason   : Error rate "
            f"{error_rate:.2f}% exceeds "
            f"{ERROR_THRESHOLD:.2f}%"
        )

        rollback()

        return 1

    # ========================================================
    # CANARY HEALTHY
    # ========================================================

    print()
    print("Decision : PASS")

    print(
        f"Reason   : Error rate "
        f"{error_rate:.2f}% is within threshold"
    )

    print("Action   : Continue rollout")

    print("==========================================")

    return 0


# ============================================================
# PROGRAM ENTRY POINT
# ============================================================

if __name__ == "__main__":

    result = analyze()

    sys.exit(result)
