"""Compatibility patch for IBKR realtime bars with decimal volume fields.

Some IB Gateway/TWS builds send realtime-bar volume as decimal text, for example
``26.0000000000000000``. The bundled Python ``ibapi`` decoder attempts to parse
that field as ``int`` before user callbacks run, which raises ``ValueError`` and
kills the API reader thread.

This patch is intentionally narrow: it replaces the realtime-bar decoder
method and its message dispatch entry so the volume field is decoded as
``Decimal``. The existing wrappers in this folder already accept non-int volume
values.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


def patch_ibapi_realtime_bar_decimal_volume() -> bool:
    """Patch ``ibapi.decoder.Decoder`` once.

    Returns True when the patch was newly applied, False when the class already
    carried the marker. The dispatch-table handler is refreshed on every call
    because some ibapi versions store the original method object there.
    """

    import ibapi.decoder as decoder

    already_active = getattr(decoder.Decoder, "_propstack_decimal_realtime_bar_patch", False)

    def process_real_time_bar_msg(self: Any, fields: Any) -> None:
        next(fields)
        decoder.decode(int, fields)
        req_id = decoder.decode(int, fields)

        bar = decoder.RealTimeBar()
        bar.time = decoder.decode(int, fields)
        bar.open = decoder.decode(float, fields)
        bar.high = decoder.decode(float, fields)
        bar.low = decoder.decode(float, fields)
        bar.close = decoder.decode(float, fields)
        bar.volume = _decode_decimal(fields)
        bar.wap = decoder.decode(float, fields)
        bar.count = decoder.decode(int, fields)

        self.wrapper.realtimeBar(
            req_id,
            bar.time,
            bar.open,
            bar.high,
            bar.low,
            bar.close,
            bar.volume,
            bar.wap,
            bar.count,
        )

    decoder.Decoder.processRealTimeBarMsg = process_real_time_bar_msg
    _patch_realtime_bar_dispatch(decoder, process_real_time_bar_msg)
    decoder.Decoder._propstack_decimal_realtime_bar_patch = True
    return not already_active


def _patch_realtime_bar_dispatch(decoder: Any, process_real_time_bar_msg: Any) -> None:
    for message_id, handle_info in decoder.Decoder.msgId2handleInfo.items():
        process_method = getattr(handle_info, "processMeth", None)
        method_name = getattr(process_method, "__name__", "")
        if message_id == 50 or method_name in {"processRealTimeBarMsg", "process_real_time_bar_msg"}:
            handle_info.processMeth = process_real_time_bar_msg


def _decode_decimal(fields: Any) -> Decimal:
    raw = next(fields)
    if raw in ("", b"", None):
        return Decimal("0")
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    try:
        return Decimal(str(raw))
    except InvalidOperation:
        return Decimal(str(float(raw)))
