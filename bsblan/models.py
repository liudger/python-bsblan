"""Models for BSB-Lan."""

from typing import List, Tuple, Union

import attr


@attr.s(auto_attribs=True, frozen=True)
class Sync:
    """Object holding sync state in BSBlan."""

    send: bool
    receive: bool

    @staticmethod
    def from_dict(data):
        """Return Sync object from BSBLan API response."""
        sync = data.get("udpn", {})
        return Sync(send=sync.get("send", False), receive=sync.get("recv", False))


@attr.s(auto_attribs=True, frozen=True)
class Info:
    """Object holding information from BSBLan."""

    build_type: str
    mac_address: str
    name: str
    uptime: int
    version_id: str
    version: str

    @staticmethod
    def from_dict(data: dict):
        """Return Info object from BSBLan API response."""
        return Info(
            architecture=data.get("arch", "Unknown"),
            arduino_core_version=data.get("core", "Unknown").replace("_", "."),
            brand=data.get("brand", "WLED"),
            build_type=data.get("btype", "Unknown"),
            effect_count=data.get("fxcount", 0),
            free_heap=data.get("freeheap", 0),
            live=data.get("live", False),
            mac_address=data.get("mac", ""),
            name=data.get("name", "WLED Light"),
            pallet_count=data.get("palcount", 0),
            product=data.get("product", "DIY Light"),
            udp_port=data.get("udpport", 0),
            uptime=data.get("uptime", 0),
            version_id=data.get("vid", "Unknown"),
            version=data.get("ver", "Unknown"),
        )


@attr.s(auto_attribs=True, frozen=True)
class State:
    """Object holding the state of WLED."""

    sync: Sync
    on: bool
    preset: int
    playlist: int

    @property
    def playlist_active(self):
        """Return if a playlist is currently active."""
        return self.playlist == -1

    @property
    def preset_active(self):
        """Return if a preset is currently active."""
        return self.preset == -1

    @staticmethod
    def from_dict(data):
        """Return State object from WLED API response."""

        return State(
            sync=Sync.from_dict(data),
            on=data.get("on", False),
            brightness=data.get("bri", 1),
            transition=data.get("transition", 0),
            preset=data.get("ps", -1),
            playlist=data.get("pl", -1),
        )


@attr.s(auto_attribs=True, frozen=True)
class Device:
    """Object holding all information of WLED."""

    info: Info
    state: State

    @staticmethod
    def from_dict(data):
        """Return Device object from WLED API response."""

        return Device(
            info=Info.from_dict(data.get("info", {})),
            state=State.from_dict(data.get("state", {})),
        )
