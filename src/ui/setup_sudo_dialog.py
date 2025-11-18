#!/usr/bin/env python3
"""Dialog for setting up passwordless sudo on remote systems."""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QGroupBox,
    QMessageBox, QProgressDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from controllers.ssh_freq_controller import SSHFrequencyController


class SetupThread(QThread):
    """Thread for running sudo setup without blocking UI."""
    
    finished = pyqtSignal(bool, str)  # success, message
    
    def __init__(self, host: str, port: int, user: str, password: str):
        super().__init__()
        self.host = host
        self.port = port
        self.user = user
        self.password = password
    
    def run(self):
        """Execute sudo setup."""
        success, message = SSHFrequencyController.setup_passwordless_sudo(
            self.host, self.port, self.user, self.password
        )
        self.finished.emit(success, message)


class SetupSudoDialog(QDialog):
    """Dialog to setup passwordless sudo on remote system."""
    
    def __init__(self, host: str, port: int, user: str, parent=None):
        super().__init__(parent)
        self.host = host
        self.port = port
        self.user = user
        self.setup_thread = None
        
        self.setWindowTitle("Setup Frequency Control")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        self._init_ui()
    
    def _init_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout()
        
        # Info section
        info_label = QLabel(
            "<b>Setup Passwordless Sudo</b><br><br>"
            "To enable frequency control, we need to configure passwordless sudo "
            "on the remote system.<br><br>"
            "This is a <b>one-time setup</b>. Your password will only be used to "
            "create the sudo configuration and will <b>not be stored</b>."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Password input
        form_layout = QFormLayout()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Enter your sudo password")
        self.password_input.returnPressed.connect(self.setup_sudo)
        form_layout.addRow("Sudo Password:", self.password_input)
        layout.addLayout(form_layout)
        
        # Show what will be configured
        details_group = QGroupBox("Configuration Details")
        details_layout = QVBoxLayout()
        
        details_info = QLabel(
            f"The following configuration will be created on <b>{self.host}</b>:"
        )
        details_layout.addWidget(details_info)
        
        details_text = QTextEdit()
        details_text.setReadOnly(True)
        details_text.setMaximumHeight(120)
        details_text.setStyleSheet("font-family: monospace; font-size: 9pt;")
        details_text.setPlainText(
            f"File: /etc/sudoers.d/monitor-tool\n\n"
            f"{self.user} ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/devices/system/cpu/*/cpufreq/*\n"
            f"{self.user} ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/drm/card*/device/tile*/gt*/freq*/*\n"
            f"{self.user} ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/drm/card*/gt_*_freq_mhz"
        )
        details_layout.addWidget(details_text)
        
        security_note = QLabel(
            "ℹ️  This only allows modifying frequency settings, not full sudo access."
        )
        security_note.setStyleSheet("color: #666;")
        details_layout.addWidget(security_note)
        
        details_group.setLayout(details_layout)
        layout.addWidget(details_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.setup_btn = QPushButton("Setup Now")
        self.setup_btn.clicked.connect(self.setup_sudo)
        self.setup_btn.setDefault(True)
        
        self.skip_btn = QPushButton("Skip (Read-only Mode)")
        self.skip_btn.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.setup_btn)
        button_layout.addWidget(self.skip_btn)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def setup_sudo(self):
        """Execute sudo setup."""
        password = self.password_input.text()
        
        if not password:
            QMessageBox.warning(
                self, 
                "No Password", 
                "Please enter your sudo password."
            )
            return
        
        # Disable inputs during setup
        self.password_input.setEnabled(False)
        self.setup_btn.setEnabled(False)
        self.skip_btn.setEnabled(False)
        
        # Show progress dialog
        self.progress = QProgressDialog(
            "Setting up passwordless sudo...\nThis may take a few seconds.",
            None,
            0, 0,
            self
        )
        self.progress.setWindowTitle("Setup in Progress")
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.setCancelButton(None)
        self.progress.show()
        
        # Run setup in background thread
        self.setup_thread = SetupThread(
            self.host, self.port, self.user, password
        )
        self.setup_thread.finished.connect(self.on_setup_complete)
        self.setup_thread.start()
    
    def on_setup_complete(self, success: bool, message: str):
        """Handle setup completion.
        
        Args:
            success: Whether setup succeeded
            message: Status message
        """
        # Close progress dialog
        if hasattr(self, 'progress'):
            self.progress.close()
        
        # Re-enable inputs
        self.password_input.setEnabled(True)
        self.setup_btn.setEnabled(True)
        self.skip_btn.setEnabled(True)
        
        if success:
            QMessageBox.information(
                self,
                "Setup Complete",
                f"✅ {message}\n\n"
                "Frequency control is now enabled.\n"
                "You can now adjust CPU governor and frequency settings."
            )
            self.accept()  # Close dialog with success
        else:
            QMessageBox.critical(
                self,
                "Setup Failed",
                f"❌ {message}\n\n"
                "Please check:\n"
                "• Password is correct\n"
                "• User has sudo privileges\n"
                "• Network connection is stable\n\n"
                "You can try again or skip to use read-only mode."
            )
            # Clear password for retry
            self.password_input.clear()
            self.password_input.setFocus()
