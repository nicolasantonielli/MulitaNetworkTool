"""Emit use-case events using explicit, safe parameter allowlists."""
from functools import wraps
from inspect import signature
from threading import RLock
from uuid import uuid4

from mulita.core.events import OperationEvent
from mulita.core.models import PingSummary
from mulita.core.parsing.ping import read_ping_line
from mulita.core.parsing.discovery import parse_discovery_line


def operation(action, *fields, context=None, when=None):
    """Observe a synchronous use case, without capturing arbitrary arguments/errors."""
    def decorate(method):
        spec = signature(method)

        @wraps(method)
        def call(self, *args, **kwargs):
            if when is not None and not when(self):
                return method(self, *args, **kwargs)
            bound = spec.bind(self, *args, **kwargs)
            bound.apply_defaults()
            parameters = {name: bound.arguments[name] for name in fields}
            if context:
                parameters.update(context(self))
            identifier = uuid4().hex
            self.emit_event(OperationEvent(action, 'started', parameters, operation_id=identifier))
            try:
                result = method(self, *args, **kwargs)
            except Exception:
                self.emit_event(OperationEvent(action, 'failed', parameters, operation_id=identifier))
                raise
            if context:
                parameters.update(context(self))
            self.emit_event(OperationEvent(action, 'completed', parameters, result, identifier))
            return result
        return call
    return decorate


class StreamResult:
    """Small per-operation accumulator; never retains complete ping output."""
    def __init__(self, action):
        self.action = action
        self.pending = ''
        self.summary = PingSummary()
        self.replies = 0
        self.hosts = {}

    def feed(self, text):
        if self.action not in ('ping', 'discovery'):
            return
        self.pending += text.replace('\r', '')
        while '\n' in self.pending:
            line, self.pending = self.pending.split('\n', 1)
            self.line(line)
        # Malformed output must not grow without bound.
        self.pending = self.pending[-65536:]

    def line(self, line):
        if self.action == 'ping':
            reply, self.summary = read_ping_line(line, self.summary)
            if reply is not None and reply.status == 'ok':
                self.replies += 1
        elif self.action == 'discovery':
            host = parse_discovery_line(line)
            if host is not None:
                self.hosts[host.ip] = host

    def finish(self, service, returned):
        self.line(self.pending)
        self.pending = ''
        if self.action == 'ping':
            return {'summary': self.summary, 'replies': self.replies}
        if self.action == 'discovery':
            return tuple(self.hosts.values())
        if self.action == 'tls':
            return service.findings
        if self.action == 'nmap':
            return service.outcome
        return returned


def session(action, *fields):
    """Observe completion at the service callback, even with no UI callbacks."""
    def decorate(method):
        spec = signature(method)

        @wraps(method)
        def call(self, *args, **kwargs):
            bound = spec.bind(self, *args, **kwargs)
            bound.apply_defaults()
            parameters = {name: bound.arguments[name] for name in fields}
            # Nmap's prepared object includes paths and command arguments. Only
            # the selected targets belong in the journal.
            if action == 'nmap':
                compiled = bound.arguments['prepared'].compiled
                parameters['target'] = ' '.join(compiled.args[-compiled.target_count:]) if compiled.target_count else ''
            identifier = uuid4().hex
            accumulator = StreamResult(action)
            output, exited = bound.arguments['on_output'], bound.arguments['on_exit']
            lock = RLock()
            launching, done, returned, pending_exit = True, False, None, []
            stopped = [False]
            key = parameters.get('kind', action)
            active = self.__dict__.setdefault('_event_sessions', {})
            # Do not replace the observer of an already running operation if
            # the underlying service rejects a second start.
            token = (identifier, parameters, stopped, action)
            if key not in active:
                active[key] = token

            def receive(text):
                with lock:
                    accumulator.feed(text)
                if output:
                    output(text)

            def finish(code):
                nonlocal done
                with lock:
                    if done:
                        return
                    if launching:
                        pending_exit.append(code)
                        return
                    done = True
                    result = accumulator.finish(self, returned)
                    details = {**parameters, 'exit_code': code, 'stopped': stopped[0]}
                    if active.get(key) is token:
                        active.pop(key)
                    self.emit_event(OperationEvent(action, 'completed', details, result, identifier))
                if exited:
                    exited(code)

            bound.arguments['on_output'] = receive
            bound.arguments['on_exit'] = finish
            self.emit_event(OperationEvent(action, 'started', parameters, operation_id=identifier))
            try:
                returned = method(*bound.args, **bound.kwargs)
            except Exception:
                with lock:
                    done = True
                    if active.get(key) is token:
                        active.pop(key)
                self.emit_event(OperationEvent(action, 'failed', parameters, operation_id=identifier))
                raise
            with lock:
                launching = False
                if pending_exit:
                    finish(pending_exit[0])
            return returned
        return call
    return decorate


def stop_events(service, key=None):
    for session_key, (identifier, parameters, stopped, action) in tuple(
            getattr(service, '_event_sessions', {}).items()):
        if (key is None or key == session_key) and not stopped[0]:
            stopped[0] = True
            service.emit_event(OperationEvent(action, 'stop', parameters, operation_id=identifier))
