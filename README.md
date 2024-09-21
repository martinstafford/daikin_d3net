# daikin_d3net
Home Assistant Daikin DIII-Net Modbus Integration

Home Assistant custom component to integrate with the Daikin DTA116A51 DIII-Net/Modbus Adapter.

Early stage development against a VRV IV-S system, DTA116A51 and Modbus RTU/TCP gateway. Currently only supporting communication over Modbus TCP.

Enumerates units attached to DIII-Net bus, provides Climate entities for each.