# IBM Racing League: TORCS Corkscrew

A Python AI driver for the TORCS racing simulator. It drives the IBM car around the **Corkscrew** track from a standing start and finishes the lap with **zero damage**.

## Result

| Version | Lap time | Damage |
|---|---|---|
| Original script | Crashes into the wall (DNF) | 1863 |
| **Final (v7)** | **1:55.30** | **0** |

Video of the lap: 
https://youtu.be/slhwJy6P9Ko

## What is in this repo

| File / folder | What it is |
|---|---|
| `snakeoil3_gym_v7.py` | My final AI driver (the one in the video) |
| `original/snakeoil3_gym_ORIGINAL.py` | The unchanged starting script |
| `versions/` | Previous versions from testing |
| `livery/` | The car livery files (unchanged) |

## How to run it

1. Start TORCS (`wtorcs.exe`).
2. Choose **Quick Race**, then **Configure Race**.
3. Select the **Corkscrew** track and the driver **scr_server 1**.
4. Set **Laps** to 1, then click **New Race**.
5. In a terminal, run:

```text
python snakeoil3_gym_v7.py
```

## Enhancements

1. **Corner-aware speed and braking.** The original always aimed for 300 km/h and never braked. The new driver reads the track sensor ahead and slows down before corners.
2. **Speed-sensitive steering.** It steers firmly at low speed and gently at high speed, and pulls back toward the middle of the track more strongly.
3. **Corkscrew settings.** I logged every lap to a CSV file and found exactly where the car lost control. The driver now brakes before the Corkscrew, holds about 42 km/h through it, and limits the throttle there.
4. **Stability.** The throttle is limited while steering, so the rear wheels do not spin out on corner exits. The car lifts off instead of braking hard in a slide.
5. **Safer recovery.** If the car gets stuck, it reverses for a short, limited time and then drives forward again.

## Screenshots
![Original script crash](images/Screenshot%202026-10-08%20140320.png)
*Figure 1: v0 (original script). The car crashes into the wall, damage 1863.*

![v7 final lap](images/Screenshot%202026-10-09%20105507.png)
*Figure 2: v7 (final version). Clean lap, 1:55.30, damage 0.*

## Use of IBM Bob AI

IBM Bob and AI was used throughout the development of the driver. I used IBM Bob AI to analyse the original script, write each version of the driver, and read my lap logs to decide what to change. I tested every version in TORCS, one change at a time, and kept all versions in the repo. The livery and car model dynamics were not changed.

## Notes

- The livery and the car model dynamics were not changed.
- Track: Corkscrew only. Start: standing start.

Made by: Aditya More