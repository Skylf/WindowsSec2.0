"""
coding:utf-8
file: UI/FaceModuleUI/integrityDialog.py

@author: LF
@contact:

github:true@https://github.com/Skylf/WindowsSec2.0

creatTime:20260819
lateCodedTime:20260819
"""

# 文件完整性校验弹窗
# ====================
# 启动时校验项目文件完整性, 校验失败时弹出此对话框, 阻止进入软件。
# 由 main.py 在校验失败时调用 showIntegrityErrorDialog()。

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QFrame, QWidget, QScrollArea
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon


def showIntegrityErrorDialog(result: dict, parent=None) -> bool:
    """
    显示完整性校验失败弹窗
    :param result: IntegrityChecker.verify() 的返回结果, data 包含 added/missing/modified
    :param parent: 父窗口
    :return: 用户是否点击了"仍然启动"(True=坚持启动, False=退出)
    """
    dialog = IntegrityErrorDialog(result, parent)
    return dialog.exec() == QDialog.DialogCode.Accepted


class IntegrityErrorDialog(QDialog):
    """
    文件完整性校验失败弹窗
    ======================
    显示: 警告图标 + 标题 + 错误摘要 + 详细文件列表 + 退出/仍然启动按钮
    """

    def __init__(self, result: dict, parent=None):
        super().__init__(parent)
        self._result = result
        self.setWindowTitle("文件完整性校验失败")
        self.setFixedSize(560, 420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setStyleSheet(self._getStyle())

        self._buildUI()

    def _getStyle(self) -> str:
        """弹窗样式"""
        return """
            QDialog {
                background-color: #0D1117;
                border: 1px solid #30363D;
                border-radius: 8px;
            }
            QLabel#titleLabel {
                color: #F85149;
                font-size: 18px;
                font-weight: bold;
            }
            QLabel#infoLabel {
                color: #8B949E;
                font-size: 13px;
            }
            QLabel#sectionLabel {
                color: #C9D1D9;
                font-size: 13px;
                font-weight: bold;
                margin-top: 6px;
            }
            QTextEdit {
                background-color: #161B22;
                border: 1px solid #30363D;
                border-radius: 4px;
                color: #C9D1D9;
                font-size: 12px;
                font-family: Consolas, monospace;
            }
            QPushButton#exitBtn {
                background-color: #DA3633;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton#exitBtn:hover {
                background-color: #F85149;
            }
            QPushButton#forceBtn {
                background-color: #21262D;
                color: #8B949E;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 8px 24px;
                font-size: 13px;
            }
            QPushButton#forceBtn:hover {
                background-color: #30363D;
                color: #F85149;
            }
        """

    def _buildUI(self):
        """构建弹窗 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        data = self._result.get("data", {})

        # 标题
        title = QLabel("⚠  文件完整性校验失败")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        # 说明
        info = QLabel("检测到项目文件已被篡改或缺失，为保障系统安全，建议立即退出。")
        info.setObjectName("infoLabel")
        info.setWordWrap(True)
        layout.addWidget(info)

        # 摘要
        added = data.get("added", [])
        missing = data.get("missing", [])
        modified = data.get("modified", [])
        ok = data.get("ok", [])

        summary = QLabel(f"新增文件: {len(added)} | 缺失文件: {len(missing)} | 篡改文件: {len(modified)} | 正常文件: {len(ok)}")
        summary.setObjectName("infoLabel")
        summary.setStyleSheet("color: #F0883E; font-weight: bold;")
        layout.addWidget(summary)

        # 详细列表
        detailText = ""
        if missing:
            detailText += "── 缺失文件 ──\n"
            for f in missing:
                detailText += f"  ✗ {f}\n"
        if modified:
            detailText += "\n── 被篡改文件 ──\n"
            for f in modified:
                detailText += f"  ✗ {f}\n"
        if added:
            detailText += "\n── 新增文件 ──\n"
            for f in added:
                detailText += f"  + {f}\n"

        if detailText:
            detailLabel = QLabel("异常文件详情:")
            detailLabel.setObjectName("sectionLabel")
            layout.addWidget(detailLabel)

            detailView = QTextEdit()
            detailView.setReadOnly(True)
            detailView.setPlainText(detailText)
            detailView.setMaximumHeight(180)
            layout.addWidget(detailView)

        layout.addStretch(1)

        # 按钮
        btnRow = QHBoxLayout()
        btnRow.addStretch(1)

        forceBtn = QPushButton("仍然启动(不推荐)")
        forceBtn.setObjectName("forceBtn")
        forceBtn.clicked.connect(self.accept)  # accept = 仍然启动
        btnRow.addWidget(forceBtn)

        exitBtn = QPushButton("退出并修复")
        exitBtn.setObjectName("exitBtn")
        exitBtn.clicked.connect(self.reject)  # reject = 退出
        btnRow.addWidget(exitBtn)

        layout.addLayout(btnRow)