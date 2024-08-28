import threading
from spotapi import EventManager
from spotapi.types.data import PlayerState
from spotapi._tests.features.session import _MainFixture


def test_event_manager_initialization():
    """Test the initialization of the EventManager class."""
    event_manager = EventManager(login=_MainFixture.login)
    assert event_manager.client == _MainFixture.login.client
    assert isinstance(event_manager._current_state, PlayerState)
    assert isinstance(event_manager.wlock, threading.Lock)
    assert isinstance(event_manager._subscriptions, dict)
    assert event_manager.listener.is_alive()


def test_subscribe():
    """Test the subscribe method."""
    event_manager = EventManager(login=_MainFixture.login)

    @event_manager.subscribe("test_event")
    def test_callback(*args, **kwargs):
        pass

    assert len(event_manager._subscriptions["test_event"]) > 0
    assert test_callback in event_manager._subscriptions["test_event"]


def test_unsubscribe():
    """Test the unsubscribe method."""
    event_manager = EventManager(login=_MainFixture.login)

    @event_manager.subscribe("test_event")
    def test_callback(*args, **kwargs):
        pass

    event_manager.unsubscribe("test_event", test_callback)
    assert test_callback not in event_manager._subscriptions["test_event"]


def test_emit():
    """Test the _emit method."""
    event_manager = EventManager(login=_MainFixture.login)

    event_called = False

    @event_manager.subscribe("test_event")
    def test_callback(*args, **kwargs):
        nonlocal event_called
        event_called = True

    event_manager._emit("test_event", {"data": "test"})
    assert event_called
