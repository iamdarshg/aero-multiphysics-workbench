# Pin map: 3 x 2x20 (120 positions)

Direction is from the CONTROL board. `mA/pin` is the design maximum (see REPORT s5).

## H1 - SYSTEM: power in, BEC output, comms, driver digital

| pin | net | dir | mA/pin | class | note |
|---:|---|---|---:|---|---|
| 1 | `BAT_P_1` | in | 120.2 | power | 44.4 V bus -> BEC input |
| 2 | `BAT_P_2` | in | 120.2 | power |  |
| 3 | `BAT_P_3` | in | 120.2 | power |  |
| 4 | `BAT_P_4` | in | 120.2 | power |  |
| 5 | `DGND` | - | 0 | gnd | guard column: 44.4 V -> logic |
| 6 | `DGND` | - | 0 | gnd | guard column |
| 7 | `DGND` | - | 0 | gnd | guard column |
| 8 | `DGND` | - | 0 | gnd | guard column |
| 9 | `+3V3_REF_A` | out | 13 | power | BEC output = DRV8353 VREF + ADC VREF |
| 10 | `DGND` | - | 0 | gnd |  |
| 11 | `+3V3_REF_B` | out | 13 | power | 2nd contact, ratiometric reference |
| 12 | `DGND` | - | 0 | gnd |  |
| 13 | `CAN_H` | io | 70 | comms | CAN-FD 5 Mbit/s |
| 14 | `CAN_L` | io | 70 | comms |  |
| 15 | `DGND` | - | 0 | gnd |  |
| 16 | `DGND` | - | 0 | gnd |  |
| 17 | `SWDIO` | io | 0.5 | comms |  |
| 18 | `SWCLK` | in | 0.5 | comms |  |
| 19 | `NRST` | in | 0.5 | comms |  |
| 20 | `DGND` | - | 0 | gnd |  |
| 21 | `UART_TX` | out | 0.5 | comms | telemetry / log |
| 22 | `UART_RX` | in | 0.5 | comms |  |
| 23 | `DGND` | - | 0 | gnd |  |
| 24 | `DGND` | - | 0 | gnd |  |
| 25 | `DRV_ENABLE` | out | 0.42 | digital | fan-out to 6 x DRV8353 ENABLE |
| 26 | `nFAULT_ALL` | in | 0.33 | digital | 6 open-drain nFAULT, wired-OR |
| 27 | `DGND` | - | 0 | gnd |  |
| 28 | `DGND` | - | 0 | gnd |  |
| 29 | `SPI_SCLK` | out | 0.07 | digital | shared to 6 drivers |
| 30 | `SPI_MOSI` | out | 0.07 | digital |  |
| 31 | `SPI_MISO` | in | 0.07 | digital |  |
| 32 | `DGND` | - | 0 | gnd |  |
| 33 | `nCS_M1` | out | 0.07 | digital |  |
| 34 | `nCS_M2` | out | 0.07 | digital |  |
| 35 | `nCS_M3` | out | 0.07 | digital |  |
| 36 | `nCS_M4` | out | 0.07 | digital |  |
| 37 | `nCS_M5` | out | 0.07 | digital |  |
| 38 | `nCS_M6` | out | 0.07 | digital |  |
| 39 | `nCS_M7` | out | 0.07 | digital | 7th channel spare |
| 40 | `DGND` | - | 0 | gnd |  |

## H2 - PWM: 7 channels x 3 lines + housekeeping analogue

| pin | net | dir | mA/pin | class | note |
|---:|---|---|---:|---|---|
| 1 | `PWM_M1_A` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 2 | `PWM_M1_B` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 3 | `PWM_M1_C` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 4 | `DGND` | - | 0 | gnd | one return per 3 PWM lines |
| 5 | `PWM_M2_A` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 6 | `PWM_M2_B` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 7 | `PWM_M2_C` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 8 | `DGND` | - | 0 | gnd | one return per 3 PWM lines |
| 9 | `PWM_M3_A` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 10 | `PWM_M3_B` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 11 | `PWM_M3_C` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 12 | `DGND` | - | 0 | gnd | one return per 3 PWM lines |
| 13 | `PWM_M4_A` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 14 | `PWM_M4_B` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 15 | `PWM_M4_C` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 16 | `DGND` | - | 0 | gnd | one return per 3 PWM lines |
| 17 | `PWM_M5_A` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 18 | `PWM_M5_B` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 19 | `PWM_M5_C` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 20 | `DGND` | - | 0 | gnd | one return per 3 PWM lines |
| 21 | `PWM_M6_A` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 22 | `PWM_M6_B` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 23 | `PWM_M6_C` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 24 | `DGND` | - | 0 | gnd | one return per 3 PWM lines |
| 25 | `PWM_M7_A` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 26 | `PWM_M7_B` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 27 | `PWM_M7_C` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 28 | `DGND` | - | 0 | gnd | one return per 3 PWM lines |
| 29 | `NTC_M1` | in | 0.1 | analog |  |
| 30 | `DGND` | - | 0 | gnd |  |
| 31 | `NTC_M2` | in | 0.1 | analog |  |
| 32 | `NTC_M3` | in | 0.1 | analog |  |
| 33 | `NTC_M4` | in | 0.1 | analog |  |
| 34 | `DGND` | - | 0 | gnd |  |
| 35 | `NTC_M5` | in | 0.1 | analog |  |
| 36 | `NTC_M6` | in | 0.1 | analog |  |
| 37 | `NTC_M7` | in | 0.1 | analog | 7th channel spare |
| 38 | `BUS_V` | in | 0.01 | analog | 44.4 V divider, one shared bus |
| 39 | `BUS_I_A` | in | 0.01 | analog | INA296A2 output, 1.09 V full scale |
| 40 | `BUS_I_B` | in | 0.01 | analog | 2nd bus shunt, redundant channel |

## H3 - ANALOG: 21 current channels with adjacent returns

| pin | net | dir | mA/pin | class | note |
|---:|---|---|---:|---|---|
| 1 | `CSA_M1_A` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 2 | `AGND` | - | 0 | gnd | adjacent return |
| 3 | `CSA_M1_B` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 4 | `AGND` | - | 0 | gnd | adjacent return |
| 5 | `CSA_M1_C` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 6 | `AGND` | - | 0 | gnd | adjacent return |
| 7 | `CSA_M2_A` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 8 | `AGND` | - | 0 | gnd | adjacent return |
| 9 | `CSA_M2_B` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 10 | `AGND` | - | 0 | gnd | adjacent return |
| 11 | `CSA_M2_C` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 12 | `AGND` | - | 0 | gnd | adjacent return |
| 13 | `CSA_M3_A` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 14 | `AGND` | - | 0 | gnd | adjacent return |
| 15 | `CSA_M3_B` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 16 | `AGND` | - | 0 | gnd | adjacent return |
| 17 | `CSA_M3_C` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 18 | `AGND` | - | 0 | gnd | adjacent return |
| 19 | `CSA_M4_A` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 20 | `AGND` | - | 0 | gnd | adjacent return |
| 21 | `CSA_M4_B` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 22 | `AGND` | - | 0 | gnd | adjacent return |
| 23 | `CSA_M4_C` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 24 | `AGND` | - | 0 | gnd | adjacent return |
| 25 | `CSA_M5_A` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 26 | `AGND` | - | 0 | gnd | adjacent return |
| 27 | `CSA_M5_B` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 28 | `AGND` | - | 0 | gnd | adjacent return |
| 29 | `CSA_M5_C` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 30 | `AGND` | - | 0 | gnd | adjacent return |
| 31 | `CSA_M6_A` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 32 | `AGND` | - | 0 | gnd | adjacent return |
| 33 | `CSA_M6_B` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 34 | `AGND` | - | 0 | gnd | adjacent return |
| 35 | `CSA_M6_C` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 36 | `AGND` | - | 0 | gnd | adjacent return |
| 37 | `CSA_M7_A` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 38 | `AGND` | - | 0 | gnd | adjacent return |
| 39 | `CSA_M7_B` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 40 | `CSA_M7_C` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
