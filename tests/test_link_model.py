import pytest
from qdagview3.models.link_model import LinkModel
from qdagview3.models.standard_nodes_model import StandardNodesModel

from qtpy.QtCore import QModelIndex, Qt, QAbstractItemModel
from qtpy.QtWidgets import QApplication
from qtpy.QtTest import QSignalSpy
from qtpy.QtCore import Signal

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app

def test_blank_link_model():
    nodes_model = StandardNodesModel()
    link_model = LinkModel(nodes_model)
    assert link_model.rowCount() == 0
    assert link_model.columnCount() == 2
    assert link_model.headerData(0, Qt.Orientation.Horizontal) == "Source"
    assert link_model.headerData(1, Qt.Orientation.Horizontal) == "Target"

def test_replace_nodes_model():
    # setup
    nodes_model = StandardNodesModel()
    nodes_model.insertRows(0, 2)  # Add two nodes
    n1 = nodes_model.index(0, 0)
    n2 = nodes_model.index(1, 0)
    assert n1.isValid()
    assert n2.isValid()

    link_model = LinkModel(nodes_model)
    link_model.add_link(n1, n2)
    assert link_model.rowCount() == 1

    # replace nodes model
    spy = QSignalSpy(link_model.nodesModelChanged)
    new_nodes_model = StandardNodesModel()
    new_nodes_model.insertRows(0, 3)  # Add three nodes
    link_model.setNodesModel(new_nodes_model)
    assert link_model.rowCount() == 0
    assert len(spy) == 1

def test_add_node(qapp):
    nodes_model = StandardNodesModel()
    spy = QSignalSpy(nodes_model.rowsInserted)
    nodes_model.insertRows(0, 2)  # Add two nodes
    n1 = nodes_model.index(0, 0)
    n2 = nodes_model.index(1, 0)
    assert n1.isValid()
    assert n2.isValid()
    assert len(spy) == 1
    assert spy[0] == [QModelIndex(), 0, 1]

def test_add_remove_link(qapp):
    nodes_model = StandardNodesModel()
    nodes_model.insertRows(0, 2)  # Add two nodes
    n1 = nodes_model.index(0, 0)
    n2 = nodes_model.index(1, 0)
    assert n1.isValid()
    assert n2.isValid()
    
    link_model = LinkModel(nodes_model)
    spy_about_to_be_inserted = QSignalSpy(link_model.rowsAboutToBeInserted)
    spy_inserted = QSignalSpy(link_model.rowsInserted)
    spy_about_to_be_removed = QSignalSpy(link_model.rowsAboutToBeRemoved)
    spy_removed = QSignalSpy(link_model.rowsRemoved)

    # add link
    link_model.add_link(n1, n2)
    assert link_model.rowCount() == 1
    assert link_model.data(link_model.index(0, 0), Qt.ItemDataRole.EditRole) == n1
    assert link_model.data(link_model.index(0, 1), Qt.ItemDataRole.EditRole) == n2

    assert len(spy_about_to_be_inserted) == 1
    assert spy_about_to_be_inserted[0] == [QModelIndex(), 0, 0]
    assert len(spy_inserted) == 1
    assert spy_inserted[0] == [QModelIndex(), 0, 0]

    # remove link
    link_model.remove_link(0)
    assert link_model.rowCount() == 0
    assert link_model.index(0, 0).isValid() == False

    assert len(spy_about_to_be_removed) == 1
    assert spy_about_to_be_removed[0] == [QModelIndex(), 0, 0]
    assert len(spy_removed) == 1
    assert spy_removed[0] == [QModelIndex(), 0, 0]

def test_remove_connected_node():
    # setup
    nodes_model = StandardNodesModel()
    nodes_model.insertRows(0, 3)  # Add two nodes
    n1 = nodes_model.index(0, 0)
    n2 = nodes_model.index(1, 0)
    n3 = nodes_model.index(2, 0)

    link_model = LinkModel(nodes_model)
    link_model.add_link(n1, n2)
    link_model.add_link(n2, n3)
    assert link_model.rowCount() == 2

    # test removing a node that has links removes all connected links
    spy_about_to_be_removed = QSignalSpy(link_model.rowsAboutToBeRemoved)
    spy_removed = QSignalSpy(link_model.rowsRemoved)
    nodes_model.removeRow(n2.row())  # Remove the middle node
    assert link_model.rowCount() == 0
    assert len(spy_about_to_be_removed) == 1, f"Expected single signal for removing both links, got {len(spy_about_to_be_removed)}" #Note: these links have a continous indexes, so they should be removed in a single operation. if links had non-continuous indexes, there would be multiple signals.
    assert spy_about_to_be_removed[0] == [QModelIndex(), 0, 1]
    assert len(spy_removed) == 1, f"Expected single signal for removing both links, got {len(spy_removed)}"
    assert spy_removed[0] == [QModelIndex(), 0, 1]

if __name__ == "__main__":
    pytest.main([__file__])