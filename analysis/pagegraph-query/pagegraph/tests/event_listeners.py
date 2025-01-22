from pagegraph.graph.node import HTMLNode
from pagegraph.tests import PageGraphBaseTestClass


class EventListenersTestCase(PageGraphBaseTestClass):
    NAME = 'event_listeners'

    def test_event_listeners(self) -> None:
        event_listeners = self.graph.event_listeners()

        # Now check all listeners
        self.assertEqual(len(event_listeners), 14)

        expected_listeners = [
            {
                "event": "click",
                "element": "DIV",
                "creator": "parser",
                "listener_type": "unknown",
                "inline": True
            }, {
                "event": "load",
                "element": "IFRAME",
                "creator": "parser",
                "listener_type": "unknown",
                "inline": True
            }, {
                "event": "blur",
                "element": "P",
                "creator": "script",
                "listener_type": "inline",
                "inline": False
            }, {
                "event": "mouseover",
                "element": "P",
                "creator": "script",
                "listener_type": "inline",
                "inline": False
            }, {
                "event": "click",
                "element": "P",
                "creator": "script",
                "listener_type": "unknown",
                "inline": True
            }, {
                "event": "click",
                "element": "A",
                "creator": "parser",
                "listener_type": "unknown",
                "inline": True
            }, {
                "event": "error",
                "element": "IMG",
                "creator": "script",
                "listener_type": "inline",
                "inline": False
            }, {
                "event": "load",
                "element": "IMG",
                "creator": "script",
                "listener_type": "inline",
                "inline": False
            },  {
                "event": "load",
                "element": "IMG",
                "creator": "script",
                "listener_type": "unknown",
                "inline": True
            }, {
                "event": "error",
                "element": "IMG",
                "creator": "script",
                "listener_type": "unknown",
                "inline": True
            }, {
                "event": "click",
                "element": "DIV",
                "creator": "script",
                "listener_type": "unknown",
                "inline": True
            }, {
                "event": "click",
                "element": "DIV",
                "creator": "script",
                "listener_type": "unknown",
                "inline": True
            }, {
                "event": "click",
                "element": "A",
                "creator": "script",
                "listener_type": "unknown",
                "inline": True
            }, {
                "event": "mouseover",
                "element": "DIV",
                "creator": "parser",
                "listener_type": "unknown",
                "inline": True
            }, 
        ]

        for idx, listener in enumerate(event_listeners):
            expected_listener = expected_listeners[idx]
            self.assertEqual(listener.event, expected_listener["event"])
            self.assertEqual(listener.element.tag_name(), expected_listener["element"])
            self.assertEqual(listener.creator.node_type(), expected_listener["creator"])
            self.assertEqual(listener.listener.script_type(), expected_listener["listener_type"])
            self.assertEqual(listener.is_inline_event_handler(), expected_listener["inline"])
