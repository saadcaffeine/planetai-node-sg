# Home Assistant

Publishes this house's own sensors to Home Assistant as entities, grouped under one device per physical
sensor, and the node's latest alert as a text sensor with its level and id as attributes. It uses Home
Assistant's MQTT discovery, retained, so Home Assistant sees them again after a restart.

- **Switch:** `HA_DISCOVERY=1`, in Set up or `.env`. It also needs the MQTT broker (`MQTT_HOST`).
- **What it sends:** the latest value of each of this house's own sensor metrics, and the first line of
  each alert. Public stations around the node are not this house's entities and are left out.
- **What it reads:** nothing back. The node never addresses a device; Home Assistant decides what to do.

It hears the node at two points, `on_readings` after every batch the node stores and `on_alert` with every
alert it sends (`app/packs.py::emit`). Until 22 October 2026 this code lived in the core.
