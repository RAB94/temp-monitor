#!/bin/bash
# test_networkquality.sh - Test script for NetworkQuality integration

echo "=== Testing NetworkQuality Integration ==="

# Test 1: Check if binary exists and is executable
echo "1. Testing NetworkQuality binary..."
if command -v networkquality >/dev/null 2>&1; then
    echo "✓ networkquality binary found: $(which networkquality)"
    echo "Version info:"
    networkquality --version 2>/dev/null || echo "No version info available"
else
    echo "✗ networkquality binary not found in PATH"
    echo "Looking in common locations..."
    for path in /usr/local/bin/networkquality /usr/bin/networkquality ./networkquality; do
        if [ -x "$path" ]; then
            echo "✓ Found at: $path"
            export PATH="$(dirname $path):$PATH"
            break
        fi
    done
fi

# Test 2: Test basic RPM measurement
echo -e "\n2. Testing basic RPM measurement..."
echo "Running: networkquality rpm --test-duration 5000"
networkquality rpm --test-duration 5000 2>&1 | head -20

# Test 3: Test with verbose output to see format
echo -e "\n3. Testing verbose output..."
echo "Running: networkquality rpm --test-duration 3000 --verbose"
networkquality rpm --test-duration 3000 --verbose 2>&1 | head -30

# Test 4: Check if JSON output is supported
echo -e "\n4. Testing for JSON output support..."
if networkquality rpm --help | grep -q "json\|JSON"; then
    echo "✓ JSON output appears to be supported"
    echo "Running: networkquality rpm --test-duration 3000 --json"
    networkquality rpm --test-duration 3000 --json 2>/dev/null || echo "JSON flag not recognized"
else
    echo "ℹ No JSON flag found in help - will parse text output"
fi

# Test 5: Test Python bridge
echo -e "\n5. Testing Python bridge..."
python3 -c "
import sys, os
sys.path.insert(0, '.')
import asyncio
from src.networkquality.bridge import NetworkQualityBinaryBridge

async def test_bridge():
    config = {
        'binary_path': 'networkquality',
        'test_duration': 5000,
        'max_loaded_connections': 4
    }
    bridge = NetworkQualityBinaryBridge(config)
    print('Testing bridge measurement...')
    result = await bridge.measure()
    print(f'Result: {result.to_dict()}')

asyncio.run(test_bridge())
"

echo -e "\n=== Test Complete ==="
