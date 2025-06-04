#!/bin/bash
set -e

echo "Network Intelligence Monitor Health Check"
echo "========================================"

# Check API health
echo -n "API Health... "
if curl -sf "http://localhost:5000/health" > /dev/null; then
    echo "✓ PASS"
else
    echo "✗ FAIL"
    exit 1
fi

# Check metrics endpoint
echo -n "Metrics Endpoint... "
if curl -sf "http://localhost:8000/metrics" > /dev/null; then
    echo "✓ PASS"
else
    echo "✗ FAIL"
    exit 1
fi

echo "All health checks passed!"
