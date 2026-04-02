# HomeAssistant - Denkovi
Custom component for [Denkovi](http://denkovi.com) relay modules in Home Assistant.

Currently tested with [smartDEN IoT Internet / Ethernet 16 Relay Module - DIN Rail BOX](http://denkovi.com/smartden-lan-ethernet-16-relay-module-din-rail-box)

## Installation
Copy the folder `denkovi` and all its contents into your `custom_components` folder.

## Setup
1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Denkovi**
3. Enter the URL of your relay module (e.g. `http://10.0.30.15`) and the password
4. The integration connects to your device and shows the available relays
5. Select which relays you want to use and give them custom names
6. Done! The selected relays appear as switches in Home Assistant

To change which relays are active or rename them later, go to the integration's **Configure** options.

> **Note:** This version (3.x) uses a UI-based config flow. Remove any old `switch: platform: denkovi` entries from your `configuration.yaml` — they are no longer needed.

