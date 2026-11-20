#!/bin/python3

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
import fcntl
import os
import time

print("What is the device path for the depth camera?")
DEPTH_DEV = input() #"/dev/video4"

UVC_SET_CUR = 0x01
UVC_GET_CUR = 0x81
UVC_PU_HUE_CONTROL = 0x06
UVCIOC_CTRL_QUERY = 0xC0107521


class uvc_xu_control_query(ctypes.Structure):
    _fields_ = [
        ("unit", ctypes.c_uint8),
        ("selector", ctypes.c_uint8),
        ("query", ctypes.c_uint8),
        ("size", ctypes.c_uint16),
        ("data", ctypes.POINTER(ctypes.c_uint8)),
    ]


END_COMMANDS = [
    (UVC_SET_CUR, [0x86, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_GET_CUR, [0x86, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x1A, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x1B, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (UVC_SET_CUR, [0x12, 0x4B, 0x00, 0x00, 0x00, 0x00, 0x00]),
]


def send_xu(fd: int, query: int, payload: list[int]) -> None:
    buf = (ctypes.c_uint8 * 7)(*payload)
    ctrl = uvc_xu_control_query(
        unit=UVC_PU_HUE_CONTROL,
        selector=2,
        query=query,
        size=7,
        data=buf,
    )
    fcntl.ioctl(fd, UVCIOC_CTRL_QUERY, ctrl)


def main() -> None:
    fd = os.open(DEPTH_DEV, os.O_RDWR | os.O_NONBLOCK)
    try:
        for query, payload in END_COMMANDS:
            send_xu(fd, query, payload)
            time.sleep(0.01)
        print("DS325 emitter deactivated.")
    finally:
        os.close(fd)


if __name__ == "__main__":
    main()
