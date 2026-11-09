"""Observer (SDD 7.13): bus de eventos interno. Un observador que falla no revierte la operación."""
import logging
from flask import has_request_context, request

log = logging.getLogger('licofast.eventos')


class EventBus:
    def __init__(self):
        self._h, self._todos = {}, []

    def subscribe(self, evento, fn):
        self._h.setdefault(evento, []).append(fn)

    def subscribe_all(self, fn):
        self._todos.append(fn)

    def publish(self, evento, **datos):
        if has_request_context():
            datos.setdefault('ip', request.headers.get('X-Forwarded-For', request.remote_addr))
        for fn in self._todos:
            try:
                fn(evento, datos)
            except Exception:
                log.exception('Observador (todos) falló en %s', evento)
        for fn in self._h.get(evento, []):
            try:
                fn(**datos)
            except Exception:
                log.exception('Observador falló en %s', evento)


bus = EventBus()
