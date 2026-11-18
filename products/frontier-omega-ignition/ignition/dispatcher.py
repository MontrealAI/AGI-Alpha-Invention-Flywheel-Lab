"""Bound concurrent work; keep waiting tickets in the mission's private SQLite store."""
from __future__ import annotations

import logging
import sqlite3
import threading
import time
import uuid
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

from .store import Conflict, canonical, event


class Dispatcher:
    def __init__(self, workers=4):
        if type(workers) is not int or workers < 1:
            raise ValueError("A positive worker count is required")
        self.workers = workers
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ignition-run")
        self.epoch = uuid.uuid4().hex
        self.stores = OrderedDict()
        self.active = set()
        self.condition = threading.Condition()
        self.closed = False
        self.thread = threading.Thread(target=self._schedule, name="ignition-dispatch", daemon=True)
        self.thread.start()

    def _register(self, ctrl):
        with self.condition:
            if self.closed:
                raise Conflict("The worker is shutting down; the mission remains in its workspace")
            self.stores[ctrl.store.db] = ctrl
            self.condition.notify_all()

    def enqueue(self, ctrl, run_id, version, *, retry=False):
        store = ctrl.store
        with store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            s = store._get(db, run_id)
            if s["version"] != version:
                raise Conflict("This mission has a newer revision")
            if s["operation"]["state"] != "active":
                return
            if retry and s["status"] == "blocked":
                event(s, s["stage"], "Operator requested a retry within the existing authority", "queued")
                db.execute("UPDATE revisions SET data=? WHERE id=? AND version=?", (canonical(s), run_id, version))
            if s["status"] not in {"queued", "running"}:
                return
            self._ticket(db, run_id, version)
        self._register(ctrl)

    def _ticket(self, db, run_id, version):
        db.execute("""INSERT INTO dispatch_queue(id,version,epoch,token,ready_at) VALUES(?,?,?,?,0)
                   ON CONFLICT(id,version) DO UPDATE SET epoch=excluded.epoch,
                   token=excluded.token, ready_at=0""", (run_id, version, self.epoch, uuid.uuid4().hex))

    def recover(self, ctrl):
        # A crash between creation/intervention and notification leaves an authoritative queued revision.
        with ctrl.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            for run_id, version in db.execute("""SELECT r.id,r.version FROM revisions r
                JOIN (SELECT id, MAX(version) AS version FROM revisions GROUP BY id) h
                ON r.id=h.id AND r.version=h.version
                WHERE json_extract(r.data,'$.status') IN ('queued','running')
                AND COALESCE(json_extract(r.data,'$.operation.state'),'active')='active'"""):
                self._ticket(db, run_id, version)
            db.execute("DELETE FROM dispatch_queue WHERE epoch<>?", (self.epoch,))
        self._register(ctrl)

    def _schedule(self):
        while True:
            with self.condition:
                if self.closed:
                    return
                if len(self.active) >= self.workers or not self.stores:
                    self.condition.wait(timeout=1)
                    continue
                stores = tuple(self.stores.items())
            dispatched = False
            for path, ctrl in stores:
                try:
                    with ctrl.store.connection() as db:
                        rows = db.execute("""SELECT id, version, token FROM dispatch_queue
                            WHERE epoch=? AND ready_at<=? ORDER BY rowid LIMIT ?""",
                            (self.epoch, time.time(), self.workers + 1)).fetchall()
                    with self.condition:
                        if self.closed:
                            return
                        if len(self.active) >= self.workers:
                            break
                        for run_id, version, token in rows:
                            key = (path, run_id, version)
                            if key in self.active:
                                continue
                            self.active.add(key)
                            self.stores.move_to_end(path)
                            self.pool.submit(self._execute, ctrl, key, token)
                            dispatched = True
                            break
                except sqlite3.Error:
                    logging.error("Mission queue storage unavailable; scheduling will retry")
            if not dispatched:
                with self.condition:
                    if not self.closed:
                        self.condition.wait(timeout=1)

    def _execute(self, ctrl, key, token):
        _, run_id, version = key
        retry = False
        try:
            ctrl.advance(run_id, version, pending_only=True)
        except Conflict:
            # Cancellation, stale source and concurrent local workers are distinct.
            try:
                head = ctrl.store.get(run_id)
                retry = (head["version"] == version and head["operation"]["state"] == "active"
                         and head["status"] in {"queued", "running"} and not ctrl.obsolete(head))
            except Exception:
                retry = True
        except Exception:
            # Controller persists a blocked state on unexpected execution failures. A
            # storage failure may precede that checkpoint; retain the ticket in that case.
            logging.error("Mission worker failed; check private mission state and storage")
            retry = True
        finally:
            try:
                with ctrl.store.connection() as db:
                    args = (run_id, version, self.epoch, token)
                    if retry:
                        db.execute("UPDATE dispatch_queue SET ready_at=? WHERE id=? AND version=? AND epoch=? AND token=?",
                                   (time.time() + 5, *args))
                    else:
                        db.execute("DELETE FROM dispatch_queue WHERE id=? AND version=? AND epoch=? AND token=?", args)
            except sqlite3.Error:
                logging.error("Mission ticket checkpoint unavailable; recovery will recheck mission state")
            finally:
                with self.condition:
                    self.active.discard(key)
                    self.condition.notify_all()

    def close(self):
        with self.condition:
            self.closed = True
            self.condition.notify_all()
        self.thread.join()
        self.pool.shutdown(wait=True)
