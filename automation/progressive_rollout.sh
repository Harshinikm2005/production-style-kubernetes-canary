#!/bin/bash

# ============================================================
# INTELLIGENT PROGRESSIVE CANARY ROLLOUT
# ============================================================

NAMESPACE="canary-demo"
VIRTUAL_SERVICE="canary-routing"

ANALYZER="$HOME/production-canary/automation/canary_analyzer.py"

# ============================================================
# CHANGE TRAFFIC
# ============================================================

set_traffic() {

    STABLE=$1
    CANARY=$2

    echo ""
    echo "=========================================="
    echo "Updating Canary Traffic"
    echo "=========================================="
    echo "Stable : ${STABLE}%"
    echo "Canary : ${CANARY}%"
    echo "=========================================="

    kubectl patch virtualservice "$VIRTUAL_SERVICE" \
        -n "$NAMESPACE" \
        --type=json \
        -p="[
          {\"op\":\"replace\",\"path\":\"/spec/http/0/route/0/weight\",\"value\":${STABLE}},
          {\"op\":\"replace\",\"path\":\"/spec/http/0/route/1/weight\",\"value\":${CANARY}}
        ]"

    if [ $? -ne 0 ]; then
        echo ""
        echo "ERROR: Failed to update traffic."
        exit 1
    fi

    echo ""
    echo "Traffic update successful."

    # Give Istio and Prometheus time to collect traffic
    echo ""
    echo "Waiting for metrics..."
    sleep 20
}


# ============================================================
# ANALYZE CANARY
# ============================================================

analyze_canary() {

    echo ""
    echo "=========================================="
    echo "       CANARY HEALTH ANALYSIS"
    echo "=========================================="

    python3 "$ANALYZER"

    RESULT=$?

    if [ $RESULT -ne 0 ]; then

        echo ""
        echo "=========================================="
        echo "       CANARY ANALYSIS FAILED"
        echo "=========================================="

        echo "Stopping rollout."

        exit 1
    fi
}


# ============================================================
# STAGE 1
# ============================================================

echo ""
echo "=========================================="
echo "        STAGE 1: INITIAL CANARY"
echo "=========================================="

echo "Stable : 80%"
echo "Canary : 20%"

set_traffic 80 20

analyze_canary


# ============================================================
# STAGE 2
# ============================================================

echo ""
echo "=========================================="
echo "        STAGE 2: HALF TRAFFIC"
echo "=========================================="

echo "Stable : 50%"
echo "Canary : 50%"

set_traffic 50 50

analyze_canary


# ============================================================
# STAGE 3
# ============================================================

echo ""
echo "=========================================="
echo "        STAGE 3: MAJORITY CANARY"
echo "=========================================="

echo "Stable : 20%"
echo "Canary : 80%"

set_traffic 20 80

analyze_canary


# ============================================================
# STAGE 4
# ============================================================

echo ""
echo "=========================================="
echo "        STAGE 4: FULL CANARY"
echo "=========================================="

echo "Stable : 0%"
echo "Canary : 100%"

set_traffic 0 100

analyze_canary


# ============================================================
# COMPLETED
# ============================================================

echo ""
echo "=========================================="
echo "       CANARY ROLLOUT COMPLETED"
echo "=========================================="

echo "Stable : 0%"
echo "Canary : 100%"

echo ""
echo "All health checks passed."
echo "Production traffic is now running"
echo "100% on the canary version."

echo "=========================================="
