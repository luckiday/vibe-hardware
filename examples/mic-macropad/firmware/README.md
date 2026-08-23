# firmware — stub

Not started. The contract it will consume already exists and is validated by
`plm_check.py`: [`../pcb/pinmap.yaml`](../pcb/pinmap.yaml) carries every
signal↔GPIO assignment, the I2S bus, and the reason each pin was chosen.

What a first firmware has to do: three GPIO key reads with internal pull-ups
(all three are RTC-capable, so deep-sleep wake works), one I2S input stream
from the ICS-43434 (24-bit, left channel — `LR` is tied low on the board),
one status LED, and USB-serial-JTAG for flashing and the log.
