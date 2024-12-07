# Hardware

## Modbus TCP -> Modbus RTU Gateway

To communicate with the DTA116A51 I have used a [Waveshare RS232/485 TO WIFI POE ETH (B)](https://www.waveshare.com/wiki/RS232/485_TO_WIFI_POE_ETH_(B)) interface which provides a Wifi or Ethernet Modbus TCP gateway to the DTA116A51's RS485 interface.

The Waveshare interface must be configured in Modbus TCP<=>Modbus RTU mode.

![Waveshare mode](/images/waveshare.png)

## Mounting

The DTA116A51, Waveshare and power supply are mounted in a case near one of the indoor units

![Hardware Mounting](/images/hardware.png)

## Wiring

Daikin documentation states that

- the DTA116A51 should be connected to the outdoor unit on the F1F2 to minimise outages due to the indoor bus.
- the F1F2 bus should not branch, but should chain from device to device.

As I have added the DTA116A51 to an existing installed system I wanted to avoid changing the system's wiring configuration. I found that I could piggyback attach the DTA116A51 to an existing indoor unit's F1F2 connection on the indoor F1F2 bus, branching it on a short cable, and the gateway and system have been performing reliably for a number of months.