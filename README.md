# daikin_d3net

## Overview
Home Assistant Daikin DIII-Net Modbus Integration.

Home Assistant custom component to integrate with the Daikin DTA116A51 DIII-Net/Modbus Adapter.

Developed against a VRV IV-S system, DTA116A51 and Modbus RTU/TCP gateway. Currently only supports communication over Modbus TCP. No current support for hot water functions.

Enumerates units attached to DIII-Net bus, provides Climate entities for each.

## Communication Specification

Communication details are based on the [Daikin Design Guide Modbus Interface DIII](https://www.daikin-ce.com/content/dam/document-library/Installer-reference-guide/ac/vrv/ekmbdxb/EKMBDXB_Design%20guide_4PEN642495-1A_English.pdf).

## Screens

![Integration](/images/integration.png)

![Device List](/images/devices.png)

![Device Details](/images/device.png)

## Hardware

[Example DIY hardware implementation](hardware.md)