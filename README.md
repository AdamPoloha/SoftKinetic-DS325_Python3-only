# SoftKinetic DepthSense 325 (DS325) Standalone Python Driver (No SDK!)

Standalone Linux Python scripts for controlling the **SoftKinetic DepthSense 325 (DS325)** Time-of-Flight (ToF) depth camera (`2113:0145`) directly via Linux UVC Extension Unit (`UVCIOC_CTRL_QUERY`) ioctls, without requiring the proprietary DepthSense SDK or compiled OpenNI2 C++ binaries.

## Source & Attribution

The UVC Extension Unit initialisation/shutdown command sequences and `640x240` `YUYV` depth/IR frame unpacking logic in these scripts are ported from the open-source C++ OpenNI2 driver:

* **Source Repository:** [SIProp/openni2ds325](https://github.com)
* **Original Copyright:** Copyright (C) 2012 PrimeSense Ltd. and Copyright (C) 2014 SIProp.org
* **License:** Apache License 2.0 (see `LICENSE` and `NOTICE`)

---

## Scripts Overview

| Script | Purpose | Imported Libraries |
| :--- | :--- | :--- |
| **`activate.py`** | Sends the 82-packet UVC Extension Unit initialization sequence to the depth V4L2 device node to configure sensor registers and turn on the 850 nm IR emitter (useful before/during viewing the raw stream in tools like VLC). | **Standard library:** `ctypes`, `fcntl`, `os`, `time` *(no third-party packages required)* |
| **`deactivate.py`** | Sends the 5-packet UVC Extension Unit shutdown sequence to cleanly power down the 850 nm IR emitter when finished. | **Standard library:** `ctypes`, `fcntl`, `os`, `time` *(no third-party packages required)* |
| **`stream.py`** | Full standalone capture pipeline: starts V4L2 streaming, sends the 82-packet initialization sequence, unpacks the interleaved `640x240` `YUYV` stream into `320x240` Depth and IR maps, displays Depth, IR, and RGB feeds in OpenCV windows, and deactivates the emitter on exit (`ESC`). | **Standard library:** `ctypes`, `fcntl`, `os`<br>**Third-party:** `numpy`, `opencv-python` (`cv2`) |

---

## Camera Video Nodes & Output Modes

Modern Linux kernels expose four `/dev/video*` nodes for the DS325 (two capture nodes and two V4L2 metadata nodes). Assuming a built-in laptop webcam occupies `/dev/video0` and `/dev/video1`, the DS325 maps as follows:

| Device Node (Example) | Interface Role | Best Video Output Mode | What VLC Shows |
| :--- | :--- | :--- | :--- |
| **`/dev/video2`** | RGB Color Capture | **`MJPG` (Motion-JPEG)**<br>• `1280x720` @ `30 fps` | Normal live color webcam video. |
| **`/dev/video3`** | RGB Metadata Node | *(Metadata only — no video frames)* | Nothing (fails to open / no video stream). |
| **`/dev/video4`** | ToF Depth + IR Capture | **`YUYV` (YUYV 4:2:2)**<br>• `640x240` @ `60 fps` | **Solid bright green** until `activate.py` turns on the IR emitter (because zeroed bytes in a `YUYV` buffer decode to `Y=0, U=0, V=0` green). Once activated, VLC displays a live green/magenta ToF phase pattern. |
| **`/dev/video5`** | Depth Metadata Node | *(Metadata only — no video frames)* | Nothing (fails to open / no video stream). |

---

## How the `640x240` `YUYV` Stream Splits into Depth & IR (`320x240`)

Although the Depth/IR interface advertises a `640x240` `YUYV` format (2 bytes per pixel = `1,280` bytes per row, `307,200` bytes per frame), it is actually a container for two **`320x240`** 16-bit channels packed in interleaved 32-byte blocks:

1. **Block Structure (32 bytes = 16 `YUYV` pixels -> 8 output pixels):**
   * **First 16 bytes (8 pairs of `(ir, flag1)`):** The even bytes hold the 8-bit **IR intensity** (`0–255`), and the odd bytes hold `flag1` (short-range/status flags).
   * **Next 16 bytes (8 pairs of `(dep, flag2)`):** The even bytes hold the 8-bit **raw depth/phase value** (`0–255`), and the odd bytes hold `flag2` (range-band/contour flags).
2. **Channel Decoding (`stream.py`):**
   * **IR Stream (`320x240`, `uint8`):** Extracted directly from the `ir` bytes in the first half of each 32-byte block, showing 850 nm infrared reflectivity.
   * **Depth Stream (`320x240`, `uint16`):** Combined from `(dep, flag1, flag2)` across range bands (`0x0100`–`0x0200` short range, `0x0300`–`0x0600` mid range, `0x0700`–`0x07FF` long range, and `>= 0x0800` for out-of-range pixels).

---

## Usage

### Standalone Live Viewer (`stream.py`)
```bash
python3 stream.py
```
* Opens **DS325 Depth** (color-mapped `320x240`), **DS325 IR** (`320x240`), and **DS325 RGB** (`1280x720`).
* Press **`ESC`** to close the windows and automatically deactivate the IR emitter.

### Viewing Raw Stream in VLC (`activate.py` & `deactivate.py`)
1. Open the depth video device in VLC to start V4L2 streaming (it will initially show solid green):
   ```bash
   vlc v4l2:///dev/video4
   ```
2. Turn on the 850 nm emitter:
   ```bash
   python3 activate.py
   ```
3. When finished, power down the emitter:
   ```bash
   python3 deactivate.py
   ```

### Standalone Live Viewer (MacOS)
libuvc needs to be installed.
```bash
python3 stream_mac.py
```
* Opens **DS325 Depth** (color-mapped `320x240`), **DS325 IR** (`320x240`), and **DS325 RGB** (`1280x720`).
* Press **`ESC` or `q`** to close the windows and automatically deactivate the IR emitter.
