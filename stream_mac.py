#!/usr/bin/env python3

# ----------------------------------------------------------------------------
# Derived from OpenNI 2.x / openni2ds325 (DepthDS325Stream.cpp, DS325Stream.cpp)
# Original Copyright (C) 2012 PrimeSense Ltd.
# Original Copyright (C) 2014 SIProp.org http://www.siprop.org/
#
# Modified / ported to standalone Python (2026) by Adam Poloha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ----------------------------------------------------------------------------

import ctypes
import ctypes.util
import queue
import sys
import cv2
import numpy as np

# Load libuvc on macOS (Homebrew Apple Silicon or Intel paths)
lib_path = (
    ctypes.util.find_library("uvc")
    or "/opt/homebrew/lib/libuvc.dylib"
    or "/usr/local/lib/libuvc.dylib"
)
libuvc = ctypes.CDLL(lib_path)

UVC_SET_CUR = 0x01
UVC_GET_CUR = 0x81
UVC_PU_HUE_CONTROL = 0x06
UVC_FRAME_FORMAT_YUYV = 3


class uvc_device_descriptor(ctypes.Structure):
    _fields_ = [
        ("idVendor", ctypes.c_uint16),
        ("idProduct", ctypes.c_uint16),
        ("bcdUVC", ctypes.c_uint16),
        ("serialNumber", ctypes.c_char_p),
        ("manufacturer", ctypes.c_char_p),
        ("product", ctypes.c_char_p),
    ]


class uvc_stream_ctrl(ctypes.Structure):
    _fields_ = [
        ("bmHint", ctypes.c_uint16),
        ("bFormatIndex", ctypes.c_uint8),
        ("bFrameIndex", ctypes.c_uint8),
        ("dwFrameInterval", ctypes.c_uint32),
        ("wKeyFrameRate", ctypes.c_uint16),
        ("wPFrameRate", ctypes.c_uint16),
        ("wCompQuality", ctypes.c_uint16),
        ("wCompWindowSize", ctypes.c_uint16),
        ("wDelay", ctypes.c_uint16),
        ("dwMaxVideoFrameSize", ctypes.c_uint32),
        ("dwMaxPayloadTransferSize", ctypes.c_uint32),
        ("dwClockFrequency", ctypes.c_uint32),
        ("bmFramingInfo", ctypes.c_uint8),
        ("bPreferredVersion", ctypes.c_uint8),
        ("bMinVersion", ctypes.c_uint8),
        ("bMaxVersion", ctypes.c_uint8),
        ("bInterfaceNumber", ctypes.c_uint8),
    ]


class uvc_frame(ctypes.Structure):
    _fields_ = [
        ("data", ctypes.POINTER(ctypes.c_uint8)),
        ("data_bytes", ctypes.c_size_t),
        ("width", ctypes.c_uint32),
        ("height", ctypes.c_uint32),
        ("frame_format", ctypes.c_int),
        ("step", ctypes.c_size_t),
        ("sequence", ctypes.c_uint32),
        ("capture_time_sec", ctypes.c_long),
        ("capture_time_usec", ctypes.c_long),
        ("source", ctypes.c_void_p),
        ("library_owns_data", ctypes.c_uint8),
        ("metadata", ctypes.c_void_p),
        ("metadata_bytes", ctypes.c_size_t),
    ]


UVC_FRAME_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.POINTER(uvc_frame), ctypes.c_void_p)

libuvc.uvc_init.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
libuvc.uvc_init.restype = ctypes.c_int

libuvc.uvc_get_device_list.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)),
]
libuvc.uvc_get_device_list.restype = ctypes.c_int

libuvc.uvc_get_device_descriptor.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.POINTER(uvc_device_descriptor)),
]
libuvc.uvc_get_device_descriptor.restype = ctypes.c_int

libuvc.uvc_free_device_descriptor.argtypes = [ctypes.POINTER(uvc_device_descriptor)]
libuvc.uvc_free_device_list.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_uint8]

libuvc.uvc_open.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
libuvc.uvc_open.restype = ctypes.c_int

libuvc.uvc_get_stream_ctrl_format_size.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(uvc_stream_ctrl),
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
]
libuvc.uvc_get_stream_ctrl_format_size.restype = ctypes.c_int

libuvc.uvc_start_streaming.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(uvc_stream_ctrl),
    UVC_FRAME_CALLBACK,
    ctypes.c_void_p,
    ctypes.c_uint8,
]
libuvc.uvc_start_streaming.restype = ctypes.c_int

libuvc.uvc_set_ctrl.argtypes = [
    ctypes.c_void_p,
    ctypes.c_uint8,
    ctypes.c_uint8,
    ctypes.c_void_p,
    ctypes.c_int,
]
libuvc.uvc_set_ctrl.restype = ctypes.c_int

libuvc.uvc_get_ctrl.argtypes = [
    ctypes.c_void_p,
    ctypes.c_uint8,
    ctypes.c_uint8,
    ctypes.c_void_p,
    ctypes.c_int,
    ctypes.c_int,
]
libuvc.uvc_get_ctrl.restype = ctypes.c_int

libuvc.uvc_stop_streaming.argtypes = [ctypes.c_void_p]
libuvc.uvc_close.argtypes = [ctypes.c_void_p]
libuvc.uvc_exit.argtypes = [ctypes.c_void_p]



INIT_COMMANDS = [
    (UVC_SET_CUR, [0x86, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_GET_CUR, [0x86, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x86, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_GET_CUR, [0x86, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x86, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_GET_CUR, [0x86, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x86, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_GET_CUR, [0x86, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x86, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_GET_CUR, [0x86, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x92, 0x21, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_GET_CUR, [0x92, 0x21, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x1A, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x1B, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x13, 0x00, 0x04, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x14, 0x00, 0x00, 0x2C, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x15, 0x00, 0x01, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x16, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x17, 0x00, 0xEF, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x18, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x19, 0x00, 0x3F, 0x01, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x1A, 0x00, 0x00, 0x04, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x1B, 0x00, 0x00, 0x01, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x1B, 0x00, 0x00, 0x05, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x1B, 0x00, 0x00, 0x0D, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x1C, 0x00, 0x05, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x20, 0x00, 0xB0, 0x04, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x27, 0x00, 0x06, 0x01, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x28, 0x00, 0x4D, 0x01, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x29, 0x00, 0xF0, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x2A, 0x00, 0x4D, 0x01, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x30, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x31, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x32, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x3C, 0x00, 0x2F, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x3D, 0x00, 0xE7, 0x03, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x3E, 0x00, 0x0F, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x3F, 0x00, 0x0F, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x40, 0x00, 0xE8, 0x03, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x43, 0x00, 0x09, 0x01, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x1E, 0x00, 0x09, 0x82, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x1D, 0x00, 0x19, 0x01, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x44, 0x00, 0x1E, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x1B, 0x00, 0x00, 0x0D, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x1B, 0x00, 0x00, 0x4D, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x45, 0x00, 0x01, 0x01, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x46, 0x00, 0x02, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x47, 0x00, 0x32, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x2F, 0x00, 0x60, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x00, 0x00, 0x0C, 0x0C, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x01, 0x00, 0x0C, 0x0C, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x2F, 0x00, 0x60, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x04, 0x00, 0x30, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x05, 0x00, 0x60, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x06, 0x00, 0x90, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x07, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x09, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x0A, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x0B, 0x00, 0x60, 0xEA, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x0C, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x0D, 0x00, 0x40, 0x47, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x0E, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x0F, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x10, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x11, 0x00, 0xE0, 0x01, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x12, 0x00, 0x04, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x1A, 0x00, 0x00, 0x14, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x33, 0x00, 0xF0, 0x70, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x4A, 0x00, 0x02, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x1A, 0x00, 0x80, 0x14, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x1A, 0x00, 0xC0, 0x14, 0x00, 0x00]),
    (UVC_SET_CUR, [0x92, 0x21, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_GET_CUR, [0x92, 0x21, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x92, 0x35, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_GET_CUR, [0x92, 0x35, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x92, 0x36, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_GET_CUR, [0x92, 0x36, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x92, 0x35, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_GET_CUR, [0x92, 0x35, 0x00, 0x00, 0x00, 0x00, 0x00]),
]

END_COMMANDS = [
    (UVC_SET_CUR, [0x86, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_GET_CUR, [0x86, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x1A, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x1B, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x4B, 0x00, 0x00, 0x00, 0x00, 0x00]),
]

def send_xu(devh: ctypes.c_void_p, query: int, payload: list[int]) -> None:
    buf = (ctypes.c_uint8 * 7)(*payload)
    if query == UVC_SET_CUR:
        res = libuvc.uvc_set_ctrl(devh, UVC_PU_HUE_CONTROL, 2, buf, 7)
    else:
        res = libuvc.uvc_get_ctrl(devh, UVC_PU_HUE_CONTROL, 2, buf, 7, query)
    if res < 0:
        print(f"Warning: XU command {payload[0]:#04x} returned {res}")


def unpack_ds325_frame(raw_yuyv: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    blocks = raw_yuyv.reshape(-1, 16, 2)
    ir = blocks[:, :8, 0].ravel()
    flag1 = blocks[:, :8, 1].ravel()
    dep = blocks[:, 8:, 0].ravel()
    flag2 = blocks[:, 8:, 1].ravel()

    d = np.full(ir.shape, 0x0D00, dtype=np.uint16)
    dep16 = dep.astype(np.uint16)
    f1_16 = flag1.astype(np.uint16)

    m_out_long = (flag1 == 0x00) & (flag2 == 0x00)
    d[m_out_long] = 0x0F00 | dep16[m_out_long]

    m_long = (flag1 == 0xFF) & (flag2 == 0x00)
    d[m_long] = np.where(dep < 0xF0, 0x0700 | dep16, 0x07FF)[m_long]

    m_mid = (flag1 == 0xFF) & (flag2 == 0xFF)
    mid_hi = np.where(
        dep > 0xC0,
        0x0600,
        np.where(
            dep > 0x80,
            0x0500,
            np.where(dep > 0x40, 0x0400, 0x0300),
        ),
    ).astype(np.uint16)
    d[m_mid] = (mid_hi | dep16)[m_mid]

    m_out_range = (flag1 == 0x00) & (flag2 == 0xFF) & (dep >= 0xF0)
    d[m_out_range] = 0x0E00 | dep16[m_out_range]

    assigned = m_out_long | m_long | m_mid | m_out_range
    m_short = (~assigned) & (flag1 < 0x08)
    f1_adj = np.where(f1_16 <= 4, f1_16, f1_16 - 4)
    hi_short = np.where(f1_16 <= 4, 0x0200, 0x0100).astype(np.uint16)
    scaled_dep = (
        (255 - (255 * (dep16 + 255 * f1_adj) // 0x3FF))
        .astype(np.uint8)
        .astype(np.uint16)
    )
    d[m_short] = (hi_short | scaled_dep)[m_short]

    m_out_short = (~assigned) & (flag1 >= 0x08)
    d[m_out_short] = dep16[m_out_short]

    return d.reshape(240, 320), ir.reshape(240, 320)

UVC_FRAME_FORMAT_YUYV = 3
UVC_FRAME_FORMAT_MJPEG = 7

def main() -> None:
    ctx = ctypes.c_void_p()
    if libuvc.uvc_init(ctypes.byref(ctx), None) < 0:
        sys.exit("Failed to initialize libuvc")

    dev_list = ctypes.POINTER(ctypes.c_void_p)()
    if libuvc.uvc_get_device_list(ctx, ctypes.byref(dev_list)) < 0:
        sys.exit("Failed to get UVC device list")

    ds_idx = None
    idx = 0
    while dev_list[idx]:
        desc = ctypes.POINTER(uvc_device_descriptor)()
        if libuvc.uvc_get_device_descriptor(dev_list[idx], ctypes.byref(desc)) == 0:
            vid, pid = desc.contents.idVendor, desc.contents.idProduct
            prod = desc.contents.product.decode(errors="ignore") if desc.contents.product else "Unknown"
            print(f"[{idx}] VID:PID = {vid:#06x}:{pid:#06x} ({prod})")
            if vid == 0x2113 and pid == 0x0145:
                ds_idx = idx
            libuvc.uvc_free_device_descriptor(desc)
        idx += 1

    if ds_idx is None:
        sys.exit("DepthSense 325 (0x2113:0x0145) not found.")

    devh = ctypes.c_void_p()
    res = libuvc.uvc_open(dev_list[ds_idx], ctypes.byref(devh))
    if res < 0:
        sys.exit(f"uvc_open failed with error {res} (run with: sudo .venv/bin/python stream.py)")

    # 1. Negotiate Depth/IR stream (640x240 YUYV @ 60Hz)
    ctrl_depth = uvc_stream_ctrl()
    if libuvc.uvc_get_stream_ctrl_format_size(
        devh, ctypes.byref(ctrl_depth), UVC_FRAME_FORMAT_YUYV, 640, 240, 60
    ) < 0:
        sys.exit("Failed to negotiate 640x240 @ 60Hz Depth/IR stream")

    # 2. Negotiate RGB stream (1280x720 MJPEG @ 30Hz)
    ctrl_rgb = uvc_stream_ctrl()
    has_rgb = (
        libuvc.uvc_get_stream_ctrl_format_size(
            devh, ctypes.byref(ctrl_rgb), UVC_FRAME_FORMAT_MJPEG, 1280, 720, 30
        )
        == 0
    )

    depth_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=2)
    rgb_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=2)

    @UVC_FRAME_CALLBACK
    def depth_callback(frame_ptr, _user_ptr):
        frame = frame_ptr.contents
        if frame.data_bytes == 640 * 240 * 2:
            buf = np.ctypeslib.as_array(frame.data, shape=(frame.data_bytes,)).copy()
            if depth_queue.full():
                try:
                    depth_queue.get_nowait()
                except queue.Empty:
                    pass
            depth_queue.put_nowait(buf)

    @UVC_FRAME_CALLBACK
    def rgb_callback(frame_ptr, _user_ptr):
        frame = frame_ptr.contents
        if frame.data_bytes > 0:
            buf = np.ctypeslib.as_array(frame.data, shape=(frame.data_bytes,)).copy()
            if rgb_queue.full():
                try:
                    rgb_queue.get_nowait()
                except queue.Empty:
                    pass
            rgb_queue.put_nowait(buf)

    if libuvc.uvc_start_streaming(devh, ctypes.byref(ctrl_depth), depth_callback, None, 0) < 0:
        sys.exit("Failed to start Depth/IR streaming")

    rgb_streaming = False
    if has_rgb:
        res_rgb = libuvc.uvc_start_streaming(devh, ctypes.byref(ctrl_rgb), rgb_callback, None, 0)
        if res_rgb == 0:
            rgb_streaming = True
            print("RGB stream started (MJPEG 1280x720 @ 30Hz)")
        else:
            print(f"Warning: RGB stream failed to start (error {res_rgb})")
    else:
        print("Warning: Could not negotiate 1280x720 @ 30Hz MJPEG RGB format")

    print("Streaming Depth/IR @ 60Hz and RGB @ 30Hz... Press 'q' or ESC to quit.")
    cmd_idx = 0

    try:
        while True:
            try:
                raw_yuyv = depth_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            # Send XU init commands one per frame once depth streaming is actively flowing
            if cmd_idx < len(INIT_COMMANDS):
                q, p = INIT_COMMANDS[cmd_idx]
                send_xu(devh, q, p)
                cmd_idx += 1

            depth_u16, ir_u8 = unpack_ds325_frame(raw_yuyv)
            valid_depth = np.where(depth_u16 < 0x0800, depth_u16, 0)
            depth_vis = cv2.normalize(valid_depth, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
            depth_color = cv2.applyColorMap(depth_vis, cv2.COLORMAP_JET)

            cv2.imshow("DS325 Depth", depth_color)
            cv2.imshow("DS325 IR", ir_u8)

            if rgb_streaming:
                try:
                    raw_rgb = rgb_queue.get_nowait()
                    bgr_img = cv2.imdecode(raw_rgb, cv2.IMREAD_COLOR)
                    if bgr_img is not None:
                        cv2.imshow("DS325 RGB", bgr_img)
                except queue.Empty:
                    pass

            if (cv2.waitKey(1) & 0xFF) in (27, ord('q')):
                break
    finally:
        for q, p in END_COMMANDS:
            try:
                send_xu(devh, q, p)
            except Exception:
                pass
        libuvc.uvc_stop_streaming(devh)
        libuvc.uvc_close(devh)
        libuvc.uvc_free_device_list(dev_list, 1)
        libuvc.uvc_exit(ctx)
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
