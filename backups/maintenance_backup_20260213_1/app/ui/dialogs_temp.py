
# BranchStepDialog - Temporary simple implementation
class BranchStepDialog(BaseDialog):
    def __init__(self, step: StepData, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Branch Step")
        self.resize(500, 300)
        self._step = step
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.edName = QLineEdit(step.name)
        form.addRow("Name:", self.edName)
        
        label = QLabel("Branch steps allow conditional execution based on multiple images.\nThis is a simplified dialog. More features coming soon.")
        label.setWordWrap(True)
        form.addRow(label)
        
        layout.addLayout(form)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def get_step_data(self):
        self._step.name = self.edName.text()
        return self._step
