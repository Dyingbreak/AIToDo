import re
import sys
import os
import json
import uuid
import requests
import platform
from datetime import datetime, timedelta

from PyQt5.QtCore import Qt, QPoint, QThread, pyqtSignal, QTimer, QSize, QDate
from PyQt5.QtGui import QFont, QColor, QIcon, QPixmap, QPainter, QPainterPath, QLinearGradient, QBrush
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QListWidget, QListWidgetItem, QMenu,
    QSystemTrayIcon, QMessageBox, QDialog,
    QLabel, QComboBox, QSlider, QFrame, QGraphicsDropShadowEffect,
    QFormLayout, QCheckBox, QTextEdit, QDateEdit, QAction
)

TASKS_FILE = "tasks.json"
CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "theme_style": "简约主题",
    "dark_mode": False,
    "opacity": 0.92,
    "ai_base_url": "https://api.openai.com/v1",
    "ai_api_key": "",
    "ai_model": "gpt-4o-mini",
    "always_on_top": False,
    "window_x": None,
    "window_y": None
}

THEMES = {
    "简约主题": {
        "light": {
            "window_bg": "rgba(248,248,248,255)",
            "card_bg": "rgba(255,255,255,255)",
            "panel_bg": "rgba(255,255,255,255)",
            "input_bg": "rgba(250,250,250,255)",
            "text": "#222222",
            "subtext": "#666666",
            "border": "rgba(0,0,0,8)",
            "shadow": "rgba(0,0,0,25)",
            "button_bg": "#F4F4F4",
            "button_hover": "#EDEDED",
            "menu_bg": "rgba(255,255,255,255)",
            "menu_hover": "rgba(0,122,255,14)",
            "blue": "#2563EB",
            "blue_hover": "#3B82F6",
            "green": "#22C55E",
            "red": "#EF4444",
            "yellow": "#F59E0B",
            "accent": "#6366F1"
        },
        "dark": {
            "window_bg": "rgba(18,18,18,255)",
            "card_bg": "rgba(28,28,28,255)",
            "panel_bg": "rgba(35,35,35,255)",
            "input_bg": "rgba(45,45,45,255)",
            "text": "#F3F4F6",
            "subtext": "#9CA3AF",
            "border": "rgba(255,255,255,10)",
            "shadow": "rgba(0,0,0,75)",
            "button_bg": "#2D2D2D",
            "button_hover": "#383838",
            "menu_bg": "rgba(28,28,28,255)",
            "menu_hover": "rgba(96,165,250,22)",
            "blue": "#60A5FA",
            "blue_hover": "#93C5FD",
            "green": "#4ADE80",
            "red": "#F87171",
            "yellow": "#FBBF24",
            "accent": "#A78BFA"
        }
    },
    "巴洛克艺术主题": {
        "light": {
            "window_bg": "rgba(246,240,227,255)",
            "card_bg": "rgba(255,250,240,255)",
            "panel_bg": "rgba(252,244,229,255)",
            "input_bg": "rgba(255,255,248,255)",
            "text": "#4A2C1A",
            "subtext": "#7C5A48",
            "border": "rgba(128,80,40,20)",
            "shadow": "rgba(80,45,20,35)",
            "button_bg": "#EFE2CB",
            "button_hover": "#E6D2B1",
            "menu_bg": "rgba(255,249,240,255)",
            "menu_hover": "rgba(160,110,45,18)",
            "blue": "#8B5E34",
            "blue_hover": "#A06A39",
            "green": "#6B8E23",
            "red": "#B23A48",
            "yellow": "#C9A227",
            "accent": "#9A6B3D"
        },
        "dark": {
            "window_bg": "rgba(28,20,14,255)",
            "card_bg": "rgba(42,31,22,255)",
            "panel_bg": "rgba(53,39,28,255)",
            "input_bg": "rgba(64,47,34,255)",
            "text": "#F7E8D0",
            "subtext": "#D1B79B",
            "border": "rgba(255,220,180,10)",
            "shadow": "rgba(0,0,0,80)",
            "button_bg": "#5A402B",
            "button_hover": "#6B4A31",
            "menu_bg": "rgba(40,29,21,255)",
            "menu_hover": "rgba(201,162,39,18)",
            "blue": "#C9A227",
            "blue_hover": "#E0B94D",
            "green": "#8CB369",
            "red": "#D76A6A",
            "yellow": "#E0B94D",
            "accent": "#C79A5A"
        }
    }
}

TASK_PREVIEW_LEN = 25


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def task_preview(text, n=TASK_PREVIEW_LEN):
    return text if len(text) <= n else text[:n] + "..."


def parse_datetime_text(text):
    if not text:
        return None

    text = str(text).strip()

    for fmt in ("%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            pass

    m = re.match(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})\s*(\d{1,2}):(\d{2})", text)
    if m:
        y, mo, d, hh, mm = map(int, m.groups())
        return datetime(y, mo, d, hh, mm)

    now = datetime.now()
    day_offset = 0
    if "今天" in text:
        day_offset = 0
    elif "明天" in text:
        day_offset = 1
    elif "后天" in text:
        day_offset = 2
    elif "大后天" in text:
        day_offset = 3

    base_date = now + timedelta(days=day_offset)
    hour = None
    minute = 0

    m = re.search(r"(\d{1,2})[:：](\d{2})", text)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2))

    if hour is None:
        m = re.search(r"(\d{1,2})\s*点\s*(半|(\d{1,2})分?)?", text)
        if m:
            hour = int(m.group(1))
            if m.group(2) == "半":
                minute = 30
            elif m.group(3):
                minute = int(m.group(3))

    if hour is not None:
        if ("下午" in text or "晚上" in text or "夜里" in text) and hour < 12:
            hour += 12
        elif "中午" in text:
            if hour == 0 or hour == 12:
                hour = 12
            elif hour < 12:
                hour += 12
        return datetime(base_date.year, base_date.month, base_date.day, hour, minute)

    if "中午" in text:
        return datetime(base_date.year, base_date.month, base_date.day, 12, 0)
    if "上午" in text:
        return datetime(base_date.year, base_date.month, base_date.day, 9, 0)
    if "下午" in text:
        return datetime(base_date.year, base_date.month, base_date.day, 15, 0)
    if "晚上" in text or "夜里" in text or "今晚" in text:
        return datetime(base_date.year, base_date.month, base_date.day, 20, 0)

    return None


class SmoothMenu(QMenu):
    def __init__(self, title=None, parent=None):
        if title:
            super().__init__(title, parent)
        else:
            super().__init__(parent)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 45))
        self.setGraphicsEffect(shadow)


# 自定义QListWidget，实现点击空白处取消选中
class TaskListWidget(QListWidget):
    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())
        if not item:
            self.clearSelection()
        super().mousePressEvent(event)


class AIWorker(QThread):
    success = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, text, config):
        super().__init__()
        self.text = text
        self.config = config

    def run(self):
        resp = None
        try:
            headers = {
                "Authorization": f"Bearer {self.config.get('ai_api_key', '')}",
                "Content-Type": "application/json"
            }

            prompt = f"""
                你是一个待办事项助手，负责把用户的自然语言指令转换为严格 JSON。

                你必须遵守以下规则：
                1. 只输出 JSON，不能输出解释、备注、markdown、代码块
                2. JSON 必须使用以下字段：
                   - action
                   - task
                   - reminder
                   - priority
                3. 不要使用 content、title、reminder_time 等其他字段名
                4. priority 只能是：高 / 中 / 低
                5. reminder 尽量输出为标准格式：YYYY-MM-DD HH:MM
                6. 如果用户说的是“明天中午、后天晚上、今天下午3点”这类时间，可以直接转换
                7. 如果无法准确转换时间，请根据常识返回推算过后的时间，当前时间为{now_str()}
                8. 如果用户没说优先级，默认低
                9. 如果用户没明确说任务名，也尽量从句子中提取出核心任务

                支持的 action：
                - add：添加任务，最常用的action
                - delete：删除任务
                - delete_done：删除所有已完成任务
                - clear_all：清空所有任务
                - update_priority：修改任务优先级
                - set_reminder：对特定的任务已存在任务进行提醒
                - complete：标记完成
                - uncomplete：取消完成

                用户输入：
                {self.text}
"""

            payload = {
                "model": self.config.get("ai_model", "gpt-4o-mini"),
                "messages": [
                    {"role": "system", "content": "你必须只输出严格 JSON，不要输出任何额外文字。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1
            }

            url = self.config.get("ai_base_url", "").rstrip("/") + "/chat/completions"
            resp = requests.post(url, headers=headers, json=payload, timeout=20)
            resp.raise_for_status()

            resp_json = resp.json()
            content = resp_json["choices"][0]["message"]["content"].strip()
            content = content.replace("```json", "").replace("```", "").strip()

            self.success.emit(json.loads(content))

        except Exception as e:
            err = str(e)
            if resp is not None:
                err += f"\n响应内容：{resp.text}"
            self.error.emit(err)


class EditTaskDialog(QDialog):
    def __init__(self, task, parent=None, theme=None):
        super().__init__(parent)
        self.task = task
        self.theme = theme or {}
        self.drag_position = None

        self.setWindowTitle("任务详情")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # 增加整体窗体尺寸以容纳阴影
        self.setFixedSize(310, 210)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        self.mainFrame = QFrame(self)
        self.mainFrame.setObjectName("mainFrame")
        main_layout.addWidget(self.mainFrame)

        shadow = QGraphicsDropShadowEffect(self.mainFrame)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 50))
        self.mainFrame.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self.mainFrame)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self.text_edit = QTextEdit()
        self.text_edit.setText(task.get("task", ""))
        self.text_edit.setFixedHeight(60)
        self.text_edit.setPlaceholderText("请输入任务内容")
        layout.addWidget(self.text_edit)

        reminder_row = QHBoxLayout()
        reminder_row.setSpacing(8)

        self.reminder_enable = QCheckBox("提醒")

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setFixedHeight(28)

        self.time_edit = QLineEdit()
        self.time_edit.setPlaceholderText("HH:mm")
        self.time_edit.setFixedHeight(28)

        reminder_row.addWidget(self.reminder_enable)
        reminder_row.addWidget(self.date_edit, 3)
        reminder_row.addWidget(self.time_edit, 2)
        layout.addLayout(reminder_row)

        reminder_text = task.get("reminder")
        dt = parse_datetime_text(reminder_text) if reminder_text else None
        if not dt:
            dt = datetime.now()

        self.date_edit.setDate(QDate(dt.year, dt.month, dt.day))
        self.time_edit.setText(dt.strftime("%H:%M"))

        self.reminder_enable.setChecked(bool(task.get("reminder")))
        self.date_edit.setEnabled(self.reminder_enable.isChecked())
        self.time_edit.setEnabled(self.reminder_enable.isChecked())

        self.reminder_enable.toggled.connect(self.date_edit.setEnabled)
        self.reminder_enable.toggled.connect(self.time_edit.setEnabled)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        priority_label = QLabel("优先级:")
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["高", "中", "低"])
        self.priority_combo.setCurrentText(task.get("priority", "低"))
        self.priority_combo.setFixedWidth(60)
        self.priority_combo.setFixedHeight(28)

        bottom_row.addWidget(priority_label)
        bottom_row.addWidget(self.priority_combo)
        bottom_row.addStretch()

        self.cancel_btn = QPushButton("取消")
        self.save_btn = QPushButton("保存")
        self.cancel_btn.setFixedSize(50, 26)
        self.save_btn.setFixedSize(50, 26)
        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self.accept)

        bottom_row.addWidget(self.save_btn)
        bottom_row.addWidget(self.cancel_btn)

        layout.addLayout(bottom_row)

        self.apply_style()

    def get_reminder_text(self):
        if not self.reminder_enable.isChecked():
            return None
        date_str = self.date_edit.date().toString("yyyy-MM-dd")
        time_str = self.time_edit.text().strip()
        if not re.match(r"^\d{2}:\d{2}$", time_str):
            time_str = datetime.now().strftime("%H:%M")
        return f"{date_str} {time_str}"

    def apply_style(self):
        theme = self.theme
        self.setStyleSheet(f"""
            QDialog {{
                background: transparent;
            }}
            QFrame#mainFrame {{
                background-color: {theme.get("card_bg", "rgba(242, 242, 247, 255)")};
                border: 1px solid {theme.get("border", "rgba(200,200,200,160)")};
                border-radius: 16px;
            }}
            QLabel {{
                color: {theme.get("text", "#1C1C1E")};
                font-size: 12px;
                background: transparent;
            }}
            QCheckBox {{
                color: {theme.get("text", "#1C1C1E")};
                font-size: 12px;
                spacing: 6px;
                background: transparent;
            }}
            QTextEdit, QLineEdit, QDateEdit, QComboBox {{
                background-color: {theme.get("input_bg", "rgba(255,255,255,255)")};
                color: {theme.get("text", "#1C1C1E")};
                border: 1px solid {theme.get("border", "rgba(209,209,214,180)")};
                border-radius: 8px;
                padding: 4px 6px;
                font-size: 12px;
                selection-background-color: {theme.get("blue", "#007AFF")};
                selection-color: #FFFFFF;
            }}
            QComboBox::drop-down {{
                width: 18px;
                border: none;
                background: transparent;
            }}
            QPushButton {{
                border-radius: 10px;
                padding: 2px 6px;
                font-size: 12px;
                font-weight: bold;
                background-color: {theme.get("button_bg", "#F4F4F4")};
                color: {theme.get("text", "#1C1C1E")};
                border: 1px solid {theme.get("border", "rgba(200,200,200,160)")};
            }}
            QPushButton:hover {{
                opacity: 0.9;
                background-color: {theme.get("button_hover", "#EDEDED")};
            }}
            QPushButton:disabled {{
                color: #C7C7CC;
            }}
            QDateEdit::drop-down {{
                width: 0px;
                border: none;
            }}
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self.drag_position:
            self.move(event.globalPos() - self.drag_position)
            event.accept()


class SettingsDialog(QDialog):
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.config = config or {}
        self.drag_position = None

        self.setFixedSize(340, 210)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)

        self.bg_frame = QFrame(self)
        self.bg_frame.setObjectName("bg_frame")
        main_layout.addWidget(self.bg_frame)

        form = QFormLayout(self.bg_frame)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(10)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(list(THEMES.keys()))
        self.theme_combo.setCurrentText(self.config.get("theme_style", "简约主题"))
        form.addRow("主题", self.theme_combo)

        mode_opacity_layout = QHBoxLayout()
        mode_opacity_layout.setContentsMargins(0, 0, 0, 0)

        self.dark_check = QCheckBox("深色")
        self.dark_check.setChecked(self.config.get("dark_mode", False))

        opacity_label = QLabel("透明度")
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(50, 100)
        self.opacity_slider.setValue(int(self.config.get("opacity", 0.92) * 100))

        mode_opacity_layout.addWidget(self.dark_check)
        mode_opacity_layout.addSpacing(10)
        mode_opacity_layout.addWidget(opacity_label)
        mode_opacity_layout.addWidget(self.opacity_slider)
        form.addRow("模式", mode_opacity_layout)

        self.url_input = QLineEdit(self.config.get("ai_base_url", "https://api.chatanywhere.tech/v1"))
        self.key_input = QLineEdit(self.config.get("ai_api_key", ""))
        self.key_input.setEchoMode(QLineEdit.Password)
        form.addRow("API URL", self.url_input)
        form.addRow("API Key", self.key_input)

        model_btn_layout = QHBoxLayout()
        model_btn_layout.setContentsMargins(0, 0, 0, 0)

        self.model_input = QLineEdit(self.config.get("ai_model", "gpt-4o-mini"))
        self.model_input.setFixedWidth(140)

        self.save_btn = QPushButton()
        self.save_btn.setObjectName("save_btn")
        self.save_btn.setFixedSize(22, 22)
        self.save_btn.setToolTip("保存")
        self.save_btn.clicked.connect(self.save)

        self.close_btn = QPushButton()
        self.close_btn.setObjectName("close_btn")
        self.close_btn.setFixedSize(22, 22)
        self.close_btn.setToolTip("关闭")
        self.close_btn.clicked.connect(self.reject)

        model_btn_layout.addWidget(self.model_input)
        model_btn_layout.addStretch()
        model_btn_layout.addWidget(self.save_btn)
        model_btn_layout.addWidget(self.close_btn)

        form.addRow("Model", model_btn_layout)

        self.apply_style()

    def apply_style(self):
        theme = self.get_theme()
        self.setStyleSheet(f"""
            QDialog {{
                background: transparent;
            }}
            * {{ outline: none; font-size: 12px; }}
            QFrame#bg_frame {{
                background-color: {theme.get("card_bg", "#ffffff")};
                border: 1px solid {theme.get("border", "#dcdcdc")};
                border-radius: 16px;
            }}
            QLabel {{
                color: {theme.get("text", "#333333")};
                background: transparent;
            }}
            QLineEdit, QComboBox {{
                background-color: {theme.get("input_bg", "#f4f4f4")};
                color: {theme.get("text", "#333333")};
                border: 1px solid {theme.get("border", "#dcdcdc")};
                border-radius: 8px;
                padding: 4px 6px;
            }}
            QCheckBox {{
                color: {theme.get("text", "#333333")};
                spacing: 6px;
            }}
            QSlider::groove:horizontal {{
                height: 8px;
                background: rgba(127,127,127,50);
                border-radius: 4px;
            }}
            QSlider::sub-page:horizontal {{
                background: {theme.get("blue", "#0078D7")};
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                width: 16px;
                height: 16px;
                margin: -4px 0;
                border-radius: 8px;
                background: #ffffff;
                border: 1px solid {theme.get("border", "#dcdcdc")};
            }}
            QSlider::handle:horizontal:hover {{
                background: #f4f4f4;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid {theme.get("border", "#dcdcdc")};
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
                background: transparent;
            }}
            QComboBox QAbstractItemView {{
                background-color: {theme.get("menu_bg", theme.get("input_bg", "#ffffff"))};
                color: {theme.get("text", "#333333")};
                selection-background-color: {theme.get("menu_hover", theme.get("blue", "#0078D7"))};
                border: 1px solid {theme.get("border", "#dcdcdc")};
                border-radius: 6px;
                outline: none;
            }}
            QPushButton#save_btn {{
                background-color: #28a745;
                border: none;
                border-radius: 11px;
            }}
            QPushButton#save_btn:hover {{ background-color: #218838; }}
            QPushButton#close_btn {{
                background-color: #dc3545;
                border: none;
                border-radius: 11px;
            }}
            QPushButton#close_btn:hover {{ background-color: #c82333; }}
        """)

    def get_theme(self):
        style = self.config.get("theme_style", "简约主题")
        dark = self.config.get("dark_mode", False)
        return THEMES.get(style, THEMES["简约主题"])["dark" if dark else "light"]

    def save(self):
        self.config["theme_style"] = self.theme_combo.currentText()
        self.config["dark_mode"] = self.dark_check.isChecked()
        self.config["opacity"] = self.opacity_slider.value() / 100.0
        self.config["ai_base_url"] = self.url_input.text().strip()
        self.config["ai_api_key"] = self.key_input.text().strip()
        self.config["ai_model"] = self.model_input.text().strip()
        self.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self.drag_position:
            self.move(event.globalPos() - self.drag_position)
            event.accept()


class TaskItemWidget(QWidget):
    def __init__(self, task, theme):
        super().__init__()
        self.task = task
        self.theme = theme
        self.init_ui()

    def init_ui(self):
        self.setMinimumHeight(50)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(0)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)

        pr = self.task.get("priority", "低")
        pr_colors = {"高": "#FF3B30", "中": "#FF9500", "低": "#34C759"}
        color = pr_colors.get(pr, "#34C759")

        self.pr_label = QLabel("●")
        self.pr_label.setStyleSheet(f"color: {color}; font-size: 13px; background: transparent;")
        self.pr_label.setFixedWidth(14)

        title_text = task_preview(self.task.get("task", ""))
        self.title = QLabel(title_text)
        self.title.setWordWrap(False)
        self.title.setFont(QFont("Microsoft YaHei", 10))
        self.title.setMinimumHeight(20)
        self.title.setToolTip(self.task.get("task", ""))

        # 根据主题颜色自动调整字体颜色
        title_style = f"color: {self.theme.get('text', '#000000')}; background: transparent;"
        if self.task.get("done", False):
            title_style += " text-decoration: line-through; opacity: 0.5;"
        self.title.setStyleSheet(title_style)

        top.addWidget(self.pr_label)
        top.addWidget(self.title)
        top.addStretch()

        # 修改为高分辨率的完成标志，并取消粗体以兼容系统默认彩色Emoji渲染
        self.status = QLabel("✅" if self.task.get("done", False) else "")
        self.status.setStyleSheet(f"color: {self.theme.get('text', '#000000')}; background: transparent;")
        self.status.setFont(QFont("Microsoft YaHei", 11))
        top.addWidget(self.status)
        layout.addLayout(top)

        sub_parts = []
        if self.task.get("reminder"):
            sub_parts.append(f"⏰ {self.task['reminder']}")
        if self.task.get("created_at"):
            sub_parts.append(f"🕒 {self.task['created_at']}")

        self.sub = QLabel("   ".join(sub_parts))
        # 针对子标题适配深色模式
        self.sub.setStyleSheet(f"color: {self.theme.get('subtext', '#444444')}; background: transparent;")
        self.sub.setFont(QFont("Microsoft YaHei", 8))
        self.sub.setWordWrap(False)
        self.sub.setToolTip("   ".join(sub_parts))

        bottom = QHBoxLayout()
        bottom.setContentsMargins(20, 0, 0, 0)
        bottom.addWidget(self.sub)
        layout.addLayout(bottom)


class StickyTodoApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.tasks = []
        self.config = DEFAULT_CONFIG.copy()
        self.old_pos = None
        self.ai_worker = None
        self.shake_timer = None
        self.shake_origin = None
        self.shake_count = 0

        self.load_config()
        self.load_tasks()
        self.init_ui()
        self.restore_window_position()
        self.init_tray()
        self.apply_window_flags()
        self.apply_theme()

        self.remind_timer = QTimer(self)
        self.remind_timer.timeout.connect(self.check_reminders)
        self.remind_timer.start(30000)

    def init_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.resize(320, 520)

        self.root = QWidget()
        self.root.setObjectName("root")
        self.setCentralWidget(self.root)

        main = QVBoxLayout(self.root)
        main.setContentsMargins(8, 8, 8, 8)
        main.setSpacing(0)

        self.card = QFrame()
        self.card.setObjectName("card")
        main.addWidget(self.card)

        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 45))
        self.card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(8)

        header = QHBoxLayout()
        self.title = QLabel("📝 AIToDo")
        self.title.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))

        self.pin_btn = QPushButton(" ")
        self.pin_btn.setFixedSize(16, 16)
        self.pin_btn.setToolTip("置顶")
        self.pin_btn.clicked.connect(self.toggle_always_on_top)

        self.settings_btn = QPushButton(" ")
        self.settings_btn.setFixedSize(16, 16)
        self.settings_btn.setToolTip("设置")
        self.settings_btn.clicked.connect(self.open_settings)

        self.close_btn = QPushButton(" ")
        self.close_btn.setFixedSize(16, 16)
        self.close_btn.setToolTip("最小化到托盘")
        self.close_btn.clicked.connect(self.hide_to_tray)  # 修改为最小化到托盘

        header.addWidget(self.title)
        header.addStretch()
        header.addWidget(self.pin_btn)
        header.addWidget(self.settings_btn)
        header.addWidget(self.close_btn)
        card_layout.addLayout(header)

        # 换用我们重写的TaskListWidget
        self.list_widget = TaskListWidget()
        self.list_widget.setSpacing(6)
        self.list_widget.setFrameShape(QFrame.NoFrame)
        self.list_widget.itemDoubleClicked.connect(self.edit_task)
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)
        self.list_widget.setMouseTracking(True)
        self.list_widget.setSelectionMode(QListWidget.SingleSelection)
        self.list_widget.setDragDropMode(QListWidget.InternalMove)
        self.list_widget.setDefaultDropAction(Qt.MoveAction)
        self.list_widget.setDragEnabled(True)
        self.list_widget.setAcceptDrops(True)
        self.list_widget.setDropIndicatorShown(True)
        self.list_widget.model().rowsMoved.connect(self.on_tasks_reordered)
        card_layout.addWidget(self.list_widget, 1)

        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("输入任务，回车添加或AI解析…")
        self.input_box.returnPressed.connect(self.add_manual_task)
        card_layout.addWidget(self.input_box)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.add_btn = QPushButton("添加")
        self.add_btn.setMinimumHeight(36)
        self.add_btn.setFont(QFont("Microsoft YaHei", 9, QFont.Bold))
        self.add_btn.clicked.connect(self.add_manual_task)

        self.ai_btn = QPushButton("AI DO")
        self.ai_btn.setMinimumHeight(36)
        self.ai_btn.setFont(QFont("Microsoft YaHei", 9, QFont.Bold))
        self.ai_btn.clicked.connect(self.add_ai_task)

        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.ai_btn)
        card_layout.addLayout(btn_row)

    def on_tasks_reordered(self):
        new_tasks = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            task = self.get_task_by_item(item)
            if task:
                new_tasks.append(task)
        if len(new_tasks) == len(self.tasks):
            self.tasks = new_tasks
            self.save_tasks()

    def make_emoji_icon(self, emoji="📝", size=64):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        font = QFont()
        font.setPointSize(int(size * 0.65))
        painter.setFont(font)
        painter.setPen(QColor("#2C3E50"))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, emoji)
        painter.end()
        return QIcon(pixmap)

    def init_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = None
            print("系统不支持托盘图标")
            return

        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.make_emoji_icon("📝"))
        self.tray.setToolTip("AIToDo")

        menu = SmoothMenu(parent=self)
        menu.setStyleSheet(self._menu_style())
        show_act = QAction("显示", self)
        show_act.triggered.connect(self.show_normal)
        quit_act = QAction("退出", self)
        quit_act.triggered.connect(self.close_app)

        menu.addAction(show_act)
        menu.addAction(quit_act)
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.setContextMenu(menu)
        self.tray.show()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_normal()

    def show_normal(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def hide_to_tray(self):
        self.save_window_position()
        self.hide()
        if self.tray:
            self.tray.showMessage("AIToDo", "程序已最小化到托盘", QSystemTrayIcon.Information, 1500)

    def toggle_always_on_top(self):
        self.config["always_on_top"] = not self.config.get("always_on_top", False)
        self.save_config()
        self.apply_window_flags()

    def apply_window_flags(self):
        flags = Qt.FramelessWindowHint | Qt.Tool
        if self.config.get("always_on_top", False):
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    def current_theme(self):
        style = self.config.get("theme_style", "简约主题")
        dark = self.config.get("dark_mode", False)
        return THEMES.get(style, THEMES["简约主题"])["dark" if dark else "light"]

    def restore_window_position(self):
        x = self.config.get("window_x")
        y = self.config.get("window_y")
        if x is not None and y is not None:
            self.move(int(x), int(y))
        else:
            screen = QApplication.primaryScreen().availableGeometry()
            x = (screen.width() - self.width()) // 2
            y = (screen.height() - self.height()) // 2
            self.move(x, y)

    def save_window_position(self):
        pos = self.pos()
        self.config["window_x"] = pos.x()
        self.config["window_y"] = pos.y()
        self.save_config()

    def _menu_style(self):
        theme = self.current_theme()
        return f"""
            QMenu {{
                background-color: {theme["menu_bg"]};
                color: {theme["text"]};
                border: 1px solid {theme["border"]};
                border-radius: 10px;
                padding: 4px;
                margin: 6px;
            }}
            QMenu::item {{
                padding: 6px 24px 6px 12px;
                border-radius: 6px;
                margin: 2px;
                font-size: 12px;
            }}
            QMenu::item:selected {{
                background-color: {theme["menu_hover"]};
            }}
            QMenu::separator {{
                height: 1px;
                background: {theme["border"]};
                margin: 4px 6px;
            }}
            QMenu::indicator {{
                width: 0px;
                height: 0px;
            }}
        """

    def apply_theme(self):
        theme = self.current_theme()
        self.setWindowOpacity(self.config.get("opacity", 0.92))

        self.setStyleSheet(f"""
            QMainWindow, QWidget#root {{
                background: transparent;
                border: none;
                font-family: 'Microsoft YaHei';
            }}
            QFrame#card {{
                background-color: {theme["card_bg"]};
                border: none;
                border-radius: 16px;
            }}
            QLabel {{
                color: {theme["text"]};
                background: transparent;
                font-family: 'Microsoft YaHei';
            }}
            QLineEdit {{
                background-color: {theme["input_bg"]};
                color: {theme["text"]};
                border: 1px solid {theme["border"]};
                border-radius: 14px;
                padding: 8px 12px;
                font-size: 11px;
                font-family: 'Microsoft YaHei';
            }}
            QLineEdit:focus {{
                border: 1px solid {theme["blue"]};
            }}
            QListWidget {{
                background: transparent;
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                border: none;
                margin: 0px;
                border-radius: 12px;
            }}
            QListWidget::item:selected {{
                background: rgba(0,122,255,25);
                border: 1px solid rgba(0,122,255,40);
            }}
            QListWidget::item:hover {{
                background: rgba(0,122,255,15);
                border-radius: 12px;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                margin: 4px 2px 4px 2px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(120,120,120,100);
                min-height: 24px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(120,120,120,160);
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
        """)

        self.pin_btn.setStyleSheet("QPushButton{background:#FF9500;border:none;border-radius:8px;}")
        self.settings_btn.setStyleSheet(f"QPushButton{{background:{theme['blue']};border:none;border-radius:8px;}}")
        self.close_btn.setStyleSheet("QPushButton{background:#FF3B30;border:none;border-radius:8px;}")

        self.add_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255,255,255,0.96),
                    stop:1 {theme["button_bg"]});
                color: {theme["blue"]};
                border: 1px solid rgba(0,122,255,20);
                border-radius: 14px;
                padding: 6px 0px;
                font-weight: bold;
                font-family: 'Microsoft YaHei';
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255,255,255,1),
                    stop:1 {theme["button_hover"]});
            }}
            QPushButton:pressed {{
                padding-top: 8px;
                padding-bottom: 4px;
            }}
        """)
        self.ai_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {theme["blue_hover"]},
                    stop:1 {theme["blue"]});
                color: white;
                border: none;
                border-radius: 14px;
                padding: 6px 0px;
                font-weight: bold;
                font-family: 'Microsoft YaHei';
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {theme["blue"]},
                    stop:1 {theme["blue_hover"]});
            }}
            QPushButton:pressed {{
                padding-top: 8px;
                padding-bottom: 4px;
            }}
        """)

        self.refresh_list()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                self.config.update(json.load(f))

    def save_config(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def load_tasks(self):
        if os.path.exists(TASKS_FILE):
            with open(TASKS_FILE, "r", encoding="utf-8") as f:
                self.tasks = json.load(f)
        for t in self.tasks:
            t.setdefault("id", str(uuid.uuid4()))
            t.setdefault("priority", "低")
            t.setdefault("reminder", None)
            t.setdefault("done", False)
            t.setdefault("created_at", now_str())
            t.setdefault("_notified", False)

    def save_tasks(self):
        with open(TASKS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.tasks, f, ensure_ascii=False, indent=2)

    def refresh_list(self):
        self.list_widget.clear()
        theme = self.current_theme()
        for task in self.tasks:
            item = QListWidgetItem()
            item.setSizeHint(QSize(100, 56))
            item.setData(Qt.UserRole, task.get("id"))
            widget = TaskItemWidget(task, theme)
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

    def new_task_obj(self, text, priority="低", reminder=None):
        return {
            "id": str(uuid.uuid4()),
            "task": text,
            "priority": priority,
            "reminder": reminder,
            "done": False,
            "created_at": now_str(),
            "_notified": False
        }

    def add_manual_task(self):
        text = self.input_box.text().strip()
        if not text:
            return
        self.tasks.append(self.new_task_obj(text))
        self.input_box.clear()
        self.save_tasks()
        self.refresh_list()

    def add_ai_task(self):
        text = self.input_box.text().strip()
        if not text:
            return
        self.input_box.clear()
        if not self.config.get("ai_api_key"):
            QMessageBox.warning(self, "提示", "请先在设置中填写 AI API Key")
            return

        self.input_box.setEnabled(False)
        self.ai_btn.setEnabled(False)
        self.ai_btn.setText("AI 处理中…")

        self.ai_worker = AIWorker(text, self.config)
        self.ai_worker.success.connect(self.on_ai_result)
        self.ai_worker.error.connect(self.on_ai_error)
        self.ai_worker.start()

    def on_ai_error(self, msg):
        self.input_box.setEnabled(True)
        self.ai_btn.setEnabled(True)
        self.ai_btn.setText("AI DO")
        QMessageBox.critical(self, "AI 请求失败", msg)

    def parse_reminder_time(self, text):
        dt = parse_datetime_text(text)
        if dt:
            return dt.strftime("%Y-%m-%d %H:%M")
        return str(text).strip()

    def on_ai_result(self, data):
        self.input_box.setEnabled(True)
        self.ai_btn.setEnabled(True)
        self.ai_btn.setText("AI DO")
        try:
            action = data.get("action", "")
            task = data.get("task") or data.get("content") or data.get("title") or ""
            reminder = data.get("reminder") or data.get("reminder_time") or ""
            priority = data.get("priority", "低")
            if priority not in ["高", "中", "低"]:
                priority = "低"

            if action == "add":
                if not task:
                    QMessageBox.warning(self, "提示", "任务内容为空，无法添加")
                    return
                reminder_time = self.parse_reminder_time(reminder) if reminder else ""
                self.tasks.append({
                    "id": str(uuid.uuid4()),
                    "task": task,
                    "done": False,
                    "priority": priority,
                    "reminder": reminder_time,
                    "created_at": now_str(),
                    "_notified": False
                })
                self.save_tasks()
                self.refresh_list()

            elif action == "delete":
                matched = self.find_task_by_keyword(task)
                if not matched:
                    QMessageBox.warning(self, "提示", f"未找到任务：{task}")
                    return
                for t in matched:
                    if t in self.tasks:
                        self.tasks.remove(t)
                self.save_tasks()
                self.refresh_list()

            elif action == "delete_done":
                self.tasks = [t for t in self.tasks if not t.get("done", False)]
                self.save_tasks()
                self.refresh_list()

            elif action == "clear_all":
                self.tasks = []
                self.save_tasks()
                self.refresh_list()

            elif action == "update_priority":
                matched = self.find_task_by_keyword(task)
                if not matched:
                    QMessageBox.warning(self, "提示", f"未找到任务：{task}")
                    return
                for t in matched:
                    t["priority"] = priority
                self.save_tasks()
                self.refresh_list()

            elif action == "set_reminder":
                matched = self.find_task_by_keyword(task)
                if not reminder:
                    QMessageBox.warning(self, "提示", "提醒时间为空，无法设置")
                    return
                reminder_time = self.parse_reminder_time(reminder)
                if matched:
                    for t in matched:
                        t["reminder"] = reminder_time
                        t["_notified"] = False
                    self.save_tasks()
                    self.refresh_list()
                else:
                    new_task = {
                        "id": str(uuid.uuid4()),
                        "task": task,
                        "priority": priority,
                        "reminder": reminder_time,
                        "done": False,
                        "created_at": now_str(),
                        "_notified": False
                    }
                    self.tasks.append(new_task)
                    self.save_tasks()
                    self.refresh_list()

            elif action == "complete":
                matched = self.find_task_by_keyword(task)
                if not matched:
                    QMessageBox.warning(self, "提示", f"未找到任务：{task}")
                    return
                for t in matched:
                    t["done"] = True
                self.save_tasks()
                self.refresh_list()

            elif action == "uncomplete":
                matched = self.find_task_by_keyword(task)
                if not matched:
                    QMessageBox.warning(self, "提示", f"未找到任务：{task}")
                    return
                for t in matched:
                    t["done"] = False
                self.save_tasks()
                self.refresh_list()

            else:
                QMessageBox.warning(self, "提示", f"未知操作：{action}")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"处理 AI 结果失败：\n{str(e)}")

    def find_task_by_keyword(self, keyword):
        if not keyword:
            return []
        keyword = keyword.strip().lower()
        results = []
        for t in self.tasks:
            task_text = t.get("task", "").strip().lower()
            if task_text == keyword or keyword in task_text or task_text in keyword:
                results.append(t)
        return results

    def get_task_by_item(self, item):
        task_id = item.data(Qt.UserRole)
        for t in self.tasks:
            if t.get("id") == task_id:
                return t
        return None

    def edit_task(self, item):
        task = self.get_task_by_item(item)
        if not task:
            return
        dialog = EditTaskDialog(task, self, self.current_theme())
        if dialog.exec_() == QDialog.Accepted:
            new_text = dialog.text_edit.toPlainText().strip()
            if new_text:
                task["task"] = new_text
                task["priority"] = dialog.priority_combo.currentText()
                task["reminder"] = dialog.get_reminder_text()
                if task.get("reminder"):
                    task["_notified"] = False
                task.setdefault("created_at", now_str())
                task.setdefault("done", False)
                task.setdefault("id", str(uuid.uuid4()))
                self.save_tasks()
                self.refresh_list()

    def show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        task = self.get_task_by_item(item)
        if not task:
            return

        menu = SmoothMenu(parent=self)
        menu.setStyleSheet(self._menu_style())

        done_act = QAction("标记完成/未完成", self)
        delete_act = QAction("删除", self)

        pr_menu = SmoothMenu("修改优先级", self)
        pr_menu.setStyleSheet(self._menu_style())

        pr_high = QAction("高", self)
        pr_mid = QAction("中", self)
        pr_low = QAction("低", self)

        pr_menu.addAction(pr_high)
        pr_menu.addAction(pr_mid)
        pr_menu.addAction(pr_low)

        clear_reminder_act = QAction("清除提醒", self)

        menu.addAction(done_act)
        menu.addMenu(pr_menu)
        menu.addAction(clear_reminder_act)
        menu.addSeparator()
        menu.addAction(delete_act)

        act = menu.exec_(self.list_widget.mapToGlobal(pos))

        if act == done_act:
            task["done"] = not task.get("done", False)
        elif act == delete_act:
            self.tasks = [t for t in self.tasks if t["id"] != task["id"]]
        elif act == pr_high:
            task["priority"] = "高"
        elif act == pr_mid:
            task["priority"] = "中"
        elif act == pr_low:
            task["priority"] = "低"
        elif act == clear_reminder_act:
            task["reminder"] = None
            task["_notified"] = False

        self.save_tasks()
        self.refresh_list()

    def start_shake(self, duration_ms=5000, amplitude=3, interval_ms=100):
        if self.shake_timer and self.shake_timer.isActive():
            return

        self.shake_origin = self.pos()
        self.shake_count = 0

        self.shake_timer = QTimer(self)
        self.shake_timer.timeout.connect(lambda: self._do_shake(amplitude, duration_ms, interval_ms))
        self.shake_timer.start(interval_ms)

    def _do_shake(self, amplitude, duration_ms, interval_ms):
        self.shake_count += 1
        offset_x = amplitude if self.shake_count % 2 == 0 else -amplitude
        offset_y = amplitude // 2 if self.shake_count % 3 == 0 else 0
        self.move(self.shake_origin + QPoint(offset_x, offset_y))

        if self.shake_count * interval_ms >= duration_ms:
            self.shake_timer.stop()
            self.move(self.shake_origin)

    def check_reminders(self):
        now = datetime.now()
        triggered = False

        for task in self.tasks:
            reminder = task.get("reminder")
            if not reminder or task.get("_notified", False):
                continue

            try:
                dt = datetime.strptime(reminder, "%Y-%m-%d %H:%M")
            except Exception:
                continue

            if dt <= now < dt + timedelta(minutes=1):
                if self.tray:
                    self.tray.showMessage(
                        "任务提醒",
                        f"需要开始任务：{task.get('task', '')}",
                        QSystemTrayIcon.Information,
                        8000
                    )
                task["_notified"] = True
                triggered = True

        if triggered:
            self.save_tasks()
            # 增加判断：只有当窗口不在隐藏(最小化到托盘)状态时，才进行强制弹窗和晃动
            if not self.isHidden():
                self.show_normal()
                self.raise_()
                self.activateWindow()
                self.start_shake(duration_ms=5000, amplitude=6, interval_ms=30)

    def open_settings(self):
        dlg = SettingsDialog(self, self.config)
        if dlg.exec_():
            self.save_config()
            self.apply_window_flags()
            self.apply_theme()

    def close_app(self):
        try:
            self.save_window_position()
            if self.tray:
                self.tray.hide()
        except Exception:
            pass
        QApplication.quit()

    def closeEvent(self, event):
        self.save_window_position()
        if self.tray:
            self.tray.hide()
        event.accept()

    def mousePressEvent(self, event):
        # 用户点击主窗体其他地方，取消列表内容的选中状态
        self.list_widget.clearSelection()
        if event.button() == Qt.LeftButton and event.pos().y() < 50:
            self.old_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if self.old_pos is not None and event.buttons() & Qt.LeftButton:
            delta = event.globalPos() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self.old_pos = None
        self.save_window_position()


if __name__ == "__main__":
    # 注册AppUserModelID，保证Windows能够正确接收通知弹出右下角系统级别弹窗
    if platform.system() == "Windows":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AIToDo")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setFont(QFont("Microsoft YaHei", 9))
    w = StickyTodoApp()
    if w.config.get("always_on_top", False):
        w.apply_window_flags()
    w.show()
    sys.exit(app.exec_())
