#!/bin/bash
# Script to apply CPU power limits for AMD Ryzen 7640HS
echo "Applying power limits..."

# 1. Set Power Profiles Daemon to power-saver
if command -v powerprofilesctl > /dev/null; then
    sudo powerprofilesctl set power-saver
    echo "Set power-saver profile."
fi

# 2. Limit Max Frequency to 3.2GHz (conservative)
if command -v cpupower > /dev/null; then
    sudo cpupower frequency-set -u 3200MHz
    echo "Limited max frequency to 3.2GHz."
fi

# 3. Set EPP to power
for epp in /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference; do
    if [ -f "$epp" ]; then
        echo "power" | sudo tee "$epp" > /dev/null
    fi
done
echo "Set EPP to 'power'."

# 4. Disable Boost (Optional, but very effective)
if [ -f /sys/devices/system/cpu/cpufreq/boost ]; then
    echo "0" | sudo tee /sys/devices/system/cpu/cpufreq/boost > /dev/null
    echo "Disabled frequency boost."
fi

echo "CPU power limits applied."
