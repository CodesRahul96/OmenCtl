# Step 1: Rebuild DKMS module
sudo dkms build hp-rgb-lighting/1.3.5 && sudo dkms install hp-rgb-lighting/1.3.5 --force

# Step 2: Reload the module
sudo modprobe -r hp_wmi && sudo modprobe hp_wmi

# Step 3: Verify fan target files now exist
ls /sys/devices/platform/hp-wmi/hwmon/hwmon4/

# Step 4: Test max fan mode
sudo systemctl restart hpm-fan
