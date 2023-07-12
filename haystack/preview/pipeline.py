from typing import List, Dict, Any, Optional, Callable

from pathlib import Path

from canals.component import ComponentInput, ComponentOutput
from canals.pipeline import (
    Pipeline as CanalsPipeline,
    PipelineError,
    marshal_pipelines as marshal_canals_pipelines,
    unmarshal_pipelines as unmarshal_canals_pipelines,
)
from canals.pipeline.sockets import find_input_sockets

from haystack.preview.document_stores.protocols import Store


class NoSuchStoreError(PipelineError):
    pass


class Pipeline(CanalsPipeline):
    """
    Haystack Pipeline is a thin wrapper over Canals' Pipelines to add support for Stores.
    """

    def __init__(self):
        super().__init__()
        self.stores: Dict[str, Store] = {}

    def add_store(self, name: str, store: Store) -> None:
        """
        Make a store available to all nodes of this pipeline.

        :param name: the name of the store.
        :param store: the store object.
        :returns: None
        """
        self.stores[name] = store

    def list_stores(self) -> List[str]:
        """
        Returns a dictionary with all the stores that are attached to this Pipeline.

        :returns: a dictionary with all the stores attached to this Pipeline.
        """
        return list(self.stores.keys())

    def get_store(self, name: str) -> Store:
        """
        Returns the store associated with the given name.

        :param name: the name of the store
        :returns: the store
        """
        try:
            return self.stores[name]
        except KeyError as e:
            raise NoSuchStoreError(f"No store named '{name}' is connected to this pipeline.") from e

    def run(self, data: Dict[str, ComponentInput], debug: bool = False) -> Dict[str, ComponentOutput]:
        """
        Wrapper on top of Canals Pipeline.run(). Adds the `stores` parameter to all nodes.

        :params data: the inputs to give to the input components of the Pipeline.
        :params parameters: a dictionary with all the parameters of all the components, namespaced by component.
        :params debug: whether to collect and return debug information.
        :returns A dictionary with the outputs of the output components of the Pipeline.
        """
        # Get all nodes in this pipelines instance
        for node_name in self.graph.nodes:
            # Get node inputs
            node = self.graph.nodes[node_name]["instance"]
            input_params = find_input_sockets(node)

            # If the node needs a store, adds the list of stores to its default inputs
            if "stores" in input_params:
                if not hasattr(node, "defaults"):
                    setattr(node, "defaults", {})
                node.defaults["stores"] = self.stores

        # Run the pipeline
        return super().run(data=data, debug=debug)


def load_pipelines(path: Path, _reader: Optional[Callable[..., Any]] = None):
    with open(path, "r", encoding="utf-8") as handle:
        schema = _reader(handle)
    return unmarshal_pipelines(schema=schema)


def save_pipelines(pipelines: Dict[str, Pipeline], path: Path, _writer: Optional[Callable[..., Any]] = None):
    schema = marshal_pipelines(pipelines=pipelines)
    with open(path, "w", encoding="utf-8") as handle:
        _writer(schema, handle)


def unmarshal_pipelines(schema: Dict[str, Any]) -> Dict[str, Pipeline]:
    return unmarshal_canals_pipelines(schema=schema)


def marshal_pipelines(pipelines: Dict[str, Pipeline]) -> Dict[str, Any]:
    marshalled = marshal_canals_pipelines(pipelines=pipelines)
    for pipeline_name, pipeline in pipelines.items():
        # TODO serialize store's init params
        marshaled_stores = {
            store_name: {"type": store.__class__.__name__, "init_parameters": {}}
            for store_name, store in pipeline.stores.items()
        }
        marshalled["pipelines"][pipeline_name]["stores"] = marshaled_stores
    return marshalled
