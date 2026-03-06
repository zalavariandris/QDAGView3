import pytest
import os
import sys
sys.path.insert(0, os.getcwd())
from examples.expression_flow.expression_model import ExpressionsModel


def test_inserting_nodes():
    model = ExpressionsModel()
    model.insertNodes(0, ["Node1", "Node2"])
    assert model.rowCount() == 2, f"Expected 2 nodes, got {model.rowCount()}"
    assert model.index(0, 0).data() == "Node1"
    assert model.index(1, 0).data() == "Node2"

def test_inlets_and_outlets():
    model = ExpressionsModel()
    model.insertNodes(0, ["Node1"])
    node_index = model.index(0, 0)
    assert model.rowCount(node_index) == 0, f"Expected 0 inlets/outlets, got {model.rowCount(node_index)}"

if __name__ == "__main__":
    test_inserting_nodes()
    # pytest.main([__file__])