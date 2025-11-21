import pytest
from PyQt5.QtWidgets import QApplication, QTableWidget
from PyQt5.QtCore import Qt
from src.ui.widgets.process_table_widget import ProcessTableWidget
from dataclasses import dataclass

# Mock ProcessInfo for testing
@dataclass
class MockProcessInfo:
    pid: int
    name: str
    cpu_percent: float
    memory_rss: int
    cmdline: str

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app

class TestProcessTableWidget:
    @pytest.fixture
    def widget(self, qapp):
        return ProcessTableWidget()

    def test_initialization(self, widget):
        assert widget.table.columnCount() == 4
        assert widget.table.rowCount() == 0
        headers = [widget.table.horizontalHeaderItem(i).text() for i in range(4)]
        assert headers == ["PID", "Name", "CPU %", "Mem (MB)"]

    def test_update_data_empty(self, widget):
        widget.update_data([])
        assert widget.table.rowCount() == 0

    def test_update_data_with_objects(self, widget):
        processes = [
            MockProcessInfo(1, "proc1", 10.5, 1024*1024*100, "proc1 arg"),
            MockProcessInfo(2, "proc2", 85.0, 1024*1024*200, "proc2 arg")
        ]
        widget.update_data(processes)
        
        assert widget.table.rowCount() == 2
        
        # Check Row 0
        assert widget.table.item(0, 0).text() == "1"
        assert widget.table.item(0, 1).text() == "proc1"
        assert widget.table.item(0, 2).text() == "10.5"
        assert widget.table.item(0, 3).text() == "100.0"
        assert widget.table.item(0, 1).toolTip() == "proc1 arg"
        
        # Check Row 1 (Critical CPU > 80)
        # We can't easily check background color equality directly due to QBrush/QColor complexity,
        # but we can check it's not the default if we implemented logic.
        # In our implementation, >80 is critical (reddish).
        bg_brush = widget.table.item(1, 0).background()
        assert bg_brush.color().red() == 255  # Should be red component

    def test_update_data_with_dicts(self, widget):
        processes = [
            {
                'pid': 3,
                'name': 'proc3',
                'cpu_percent': 55.0,
                'memory_rss': 1024*1024*50,
                'cmdline': 'proc3 arg',
                'severity': 'warning'
            }
        ]
        widget.update_data(processes)
        
        assert widget.table.rowCount() == 1
        assert widget.table.item(0, 0).text() == "3"
        
        # Check warning color (orange-ish)
        bg_brush = widget.table.item(0, 0).background()
        assert bg_brush.color().red() == 255
        assert bg_brush.color().green() == 200
