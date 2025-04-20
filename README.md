# daikin_d3net

## Overview
Home Assistant Daikin DIII-Net Modbus Integration.

Home Assistant custom component to integrate with the Daikin DTA116A51 DIII-Net/Modbus Adapter.

Developed against a VRV IV-S system, DTA116A51 and Modbus RTU/TCP gateway. Currently only supports communication over Modbus TCP. No current support for hot water functions. Unfortunately the DCPA01 is not supported and no documentation is available.

Enumerates units attached to DIII-Net bus, provides Climate entities for each.

## Installation
Install with [HACS](https://hacs.xyz), currently as a custom repository by manually adding this repository or with the link below

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=martinstafford&repository=daikin_d3net&category=integration)

OR

Download the [latest release](https://github.com/martinstafford/daikin_d3net/releases) and copy the `daikin_d3net` folder into to your Home Assistant `config/custom_components` folder.

After rebooting Home Assistant, this integration can be configured through the integration setup UI.

## Communication Specification

Communication details are based on the [Daikin Design Guide Modbus Interface DIII](https://www.daikin-ce.com/content/dam/document-library/Installer-reference-guide/ac/vrv/ekmbdxb/EKMBDXB_Design%20guide_4PEN642495-1A_English.pdf).

## Screens

![Integration](/images/integration.png)

![Device List](/images/devices.png)

![Device Details](/images/device.png)

## Hardware

[Example DIY hardware implementation](hardware.md)
