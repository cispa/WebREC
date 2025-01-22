from dataclasses import dataclass, field
from typing import cast, Optional, TYPE_CHECKING, Union
from pagegraph.util import is_url_local, brief_version


from pagegraph.serialize import Reportable
from pagegraph.types import EventListenerId
from pagegraph.graph.node import ScriptNode, DOMElementNode, Node
from pagegraph.graph.edge import Edge
from pagegraph.serialize import EventListenerReport

if TYPE_CHECKING:
    from pagegraph.graph.edge import EventListenerEdge


@dataclass
class EventListener(Reportable):
    event_listener_id: EventListenerId
    event: str
    listener: ScriptNode
    element: DOMElementNode
    creator: Union["Node", None] = None

    def to_report(self) -> EventListenerReport:
        event_listener_id = self.event_listener_id
        source = self.source
        element = self.element
        creator = self.creator

    def describe(self) -> str:
        output = f"event listener id={self.event_listener_id}\n"
        output += f"event={self.event}\n"

        output += f"element nid={self.element.pg_id()}\n"
        for attr_name, attr_value in self.element.data().items():
            output += f"- {attr_name}={brief_version(str(attr_value))}\n"

        output += f"creator nid={self.creator.pg_id()}\n"
        for attr_name, attr_value in self.creator.data().items():
            output += f"- {attr_name}={brief_version(str(attr_value))}\n"

        output += f"listener nid={self.listener.pg_id()}\n"
        for attr_name, attr_value in self.listener.data().items():
            output += f"- {attr_name}={brief_version(str(attr_value))}\n"
        return output

    def is_programatically_added_event_handler(self) -> bool:

        # We check if the (script) node that created the event listener
        # is the same as the event listener node. If so, it is added via
        # addEventListener.
        if self.creator == self.listener:
            return True
        
        # This can be the case if a function in an external script (that is not the parent) or inline is called.
        # This can also happen if eval directly is called.
        # This means event listener was created via addEventListener. No unsafe_inline issue
        if self.listener.script_type() != ScriptNode.ScriptType.UNKNOWN:
            return True
        
        return False
        
    def is_inline_event_handler(self) -> bool:
        execute_from_attribute_edges = [
            e for e in self.listener.incoming_edges()
            if e.edge_type() == Edge.Types.EXECUTE_FROM_ATTRIBUTE
        ]
        if len(execute_from_attribute_edges) == 0:
            return False
        return True

    def is_or_was_in_dom(self) -> bool:
        """ Check if the element of the listener was ever added to the DOM """
        if (self.element.domroot_for_serialization() is not None or
            self.element.domroot_custom_by_florian() is not None):
            return True
        return False

def event_listener_for_edge(event_listener_edge: "EventListenerEdge") -> EventListener:
    event_listener_id = event_listener_edge.event_listener_id()
    listener = event_listener_edge.outgoing_node()
    element = event_listener_edge.incoming_node()
    creator = None
    
    # while c := element.incoming_edges():        
    for c in list(element.incoming_edges()):
        creator_edges = [Edge.Types.EVENT_LISTENER_ADD, Edge.Types.ATTRIBUTE_SET]
        if c.edge_type() in creator_edges and c.event_listener_id() == event_listener_id:
            creator = c.incoming_node()

    event_listener = EventListener(
        event_listener_id,
        event_listener_edge.key(),
        listener,
        element,
        creator
    )
    return event_listener
