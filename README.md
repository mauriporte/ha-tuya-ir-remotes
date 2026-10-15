# Tuya IR Remotes for Home Assistant

Use the **virtual IR remotes** you created in the Smart Life / Tuya app (on a Tuya IR blaster) from Home Assistant, with the same buttons you already have in the app. You don't need to learn any codes again.

Home Assistant's built-in Tuya integration shows these remotes as devices with no entities. This integration reads them from Tuya's cloud IR API.

## What you get

For each virtual remote on the IR blaster:

- **One button entity per key** (for example `button.audio_volume_up`). Use them on dashboards.
- **One remote entity** (for example `remote.audio`) for automations and scripts:

  ```yaml
  action: remote.send_command
  target:
    entity_id: remote.audio
  data:
    command: Volume Up
    num_repeats: 3
    delay_secs: 0.4
  ```

  `command` is the key name as shown in the app. The remote's `commands` attribute lists them.

Library remotes (picked by brand in the app) and DIY/learned remotes both work.

IR is one-way, so these entities cannot know whether the device is actually on.

## Setup: free Tuya developer project

1. Sign up at [platform.tuya.com](https://platform.tuya.com).
2. **Cloud → Development → Create Cloud Project**. Use industry *Smart Home*, development method *Smart Home*, and the data center of your app account (for example *Central Europe*). When asked for API services, also authorize **IR Control Hub Open Service**.
3. In the project, open **Devices → Link App Account → Add App Account**. Scan the QR code with the Smart Life / Tuya app (Me → scan icon).
4. Copy the **Access ID** and **Access Secret** from the project's Overview tab.
5. Install this integration (HACS custom repository, or copy `custom_components/tuya_ir_remotes`). Restart Home Assistant, then add **Tuya IR Remotes** with the Access ID, the Access Secret and the data center (`eu` = Central Europe, `weu` = Western Europe, `us`, `eus`, `cn`, `in`). The IR blaster is found automatically.

### The trial

The free *IoT Core* plan is a trial that must be extended from time to time: **Cloud → Cloud Services → IoT Core → Extend Trial Period**. If it expires, keys stop being sent and Home Assistant shows a repair issue explaining this. After extending it, reload the integration.

## Limits

- This works through Tuya's cloud, so each key press needs internet and takes about a second.
- The list of keys is read when the integration starts. After you add keys in the app, reload the integration.
