"""External read-observation coalescing for an unchanged frozen recorder.

This module is NOT financial authority and is not copied into an existing
account's frozen runtime. The supplied RecordingBridge, NativeBridge, policy and
independent auditor remain unchanged. Only repeated read-only snapshot views
between routed mutations are reused. Final frozen replay still checks every
recorded observation against the actual native prefix.

The wrapper must be the exclusive route for operating advance/spend/deliver.
Direct writes to the underlying native object are unsupported. Ordinary external
native mutations are detected by a cheap revision witness and refused; hostile
same-length in-memory tampering is outside this wrapper's custody guarantee and
remains subject to the unchanged full native/operating audit. No cached balance
can authorize native spending.
"""
from __future__ import annotations

import copy
import threading


class _ReadObservationProxy:
    """Private proxy accepted by the original recorder's five-method interface."""
    def __init__(self, native):
        self.__native = native
        self.__lock = threading.RLock()
        self.__snapshot = None
        self.__revision = None
        self.__failed = False

    def __current(self):
        native = self.__native
        # This retains the original current-source and exclusive-owner checks
        # even for a cached read. It deliberately does not hash account history.
        native.account._assert_current()
        account = native.account._account
        owner = account._owner
        exchange = owner._exchange
        return (id(native.account), id(owner), id(owner.lease), id(exchange),
                len(exchange.actions), exchange.last_day, exchange.ex.db.total_changes,
                native.state['hour'])

    def __check(self):
        if self.__failed:
            raise ValueError('UNROUTED_NATIVE_MUTATION_REQUIRES_NEW_OBSERVER')
        current = self.__current()
        if self.__revision is not None and current != self.__revision:
            self.__snapshot = None
            self.__revision = None
            self.__failed = True
            raise ValueError('UNROUTED_NATIVE_MUTATION_REQUIRES_NEW_OBSERVER')
        return current

    def __invalidate(self):
        self.__snapshot = None
        self.__revision = None

    def snapshot(self):
        with self.__lock:
            before = self.__check()
            if self.__snapshot is None:
                value = self.__native.snapshot()
                after = self.__current()
                if after != before:
                    self.__invalidate()
                    self.__failed = True
                    raise ValueError('NATIVE_STATE_CHANGED_DURING_READ_OBSERVATION')
                self.__snapshot = copy.deepcopy(value)
                self.__revision = after
            return copy.deepcopy(self.__snapshot)

    def order_receipt(self, ident):
        with self.__lock:
            before = self.__check()
            # Receipts may be updated by settlement; never memoize them.
            result = self.__native.order_receipt(ident)
            if self.__current() != before:
                self.__invalidate()
                self.__failed = True
                raise ValueError('ORDER_RECEIPT_MUTATED_NATIVE_STATE')
            return copy.deepcopy(result)

    def __mutate(self, method, *args, **kwargs):
        with self.__lock:
            self.__check()
            self.__invalidate()
            try:
                # Every original funding check, source check, durable intent,
                # native mutation and acceptance rule executes in frozen code.
                return getattr(self.__native, method)(*args, **kwargs)
            finally:
                # Includes rejected actions and interrupted/failed mutations.
                self.__invalidate()

    def advance(self, hour):
        return self.__mutate('advance', hour)

    def spend(self, *args, **kwargs):
        return self.__mutate('spend', *args, **kwargs)

    def deliver(self, order):
        return self.__mutate('deliver', order)


def make_recording_bridge(recording_class, native, trace=None, persist=None):
    """Use an exact supplied recorder class around a fresh uncached read proxy.

    Example: ``make_recording_bridge(frozen.RecordingBridge, native, trace,
    persist)``. A pending call is recovered by that recorder's existing code;
    this new proxy begins with no inherited observation or authority.
    """
    if not isinstance(recording_class, type):
        raise ValueError('EXPLICIT_FROZEN_RECORDING_CLASS_REQUIRED')
    return recording_class(_ReadObservationProxy(native), trace=trace, persist=persist)
