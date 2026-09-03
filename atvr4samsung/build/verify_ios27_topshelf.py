#!/usr/bin/env python3
"""Container-level regression for the iOS 27 Top Shelf startup request."""

from __future__ import annotations

from atvr4samsung.companion.server import BridgeCompanionService


service = BridgeCompanionService.__new__(BridgeCompanionService)
responses = []
service.send_response = lambda request, content: responses.append((request, content))

request = {
    "_i": "FetchCurrentTopShelfItemsEvent",
    "_x": 1,
    "_t": 2,
    "_c": {},
}
service.handle_fetchcurrenttopshelfitemsevent(request)

assert responses == [(request, {})]
print("iOS 27 Top Shelf compatibility check passed")
